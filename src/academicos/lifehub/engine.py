"""Shell-independent LifeHub platform engine and component runner abstraction."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.engine_lease import EngineLease
from academicos.lifehub.background import BackgroundWasmRunner
from academicos.lifehub.registry import RegisteredComponent, RegisteredExtension
from academicos.lifehub.routing import InterfaceRouter
from academicos.lifehub.service_runtime import SERVICE_JSON_CONTRACT, run_json_service


_ENGINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS lifehub_engine_executions (
    execution_id TEXT PRIMARY KEY,
    component_ref TEXT NOT NULL,
    runner_id TEXT NOT NULL,
    state TEXT NOT NULL,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_lifehub_engine_execution_state
    ON lifehub_engine_executions(state, updated_at DESC);
"""


class ExecutionState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class ComponentDescriptor:
    """An executable component discovered from an otherwise open extension graph."""

    ref: str
    plugin_id: str
    point: str | None
    runner_id: str
    contract: str | None
    provides: tuple[str, ...]
    requires: tuple[str, ...]
    activation: tuple[str, ...]
    config: dict[str, Any]


@dataclass(frozen=True)
class RunnerStart:
    """Result returned by a trusted runner when the engine starts a component."""

    state: ExecutionState
    result: Any = None
    handle: Any = None
    ready: bool = False


@dataclass(frozen=True)
class ExecutionView:
    execution_id: str
    component_ref: str
    runner_id: str
    state: ExecutionState
    started_at: str
    updated_at: str
    result: Any = None
    error: str | None = None
    ready: bool = False


@dataclass
class _Execution:
    execution_id: str
    component: ComponentDescriptor
    state: ExecutionState
    started_at: str
    updated_at: str
    result: Any = None
    handle: Any = None
    error: str | None = None
    ready: bool = False


class ComponentRunner(Protocol):
    """Trusted host adapter for one execution environment."""

    id: str

    def start(self, engine: "LifeHubEngine", component: ComponentDescriptor) -> RunnerStart: ...

    def stop(
        self, engine: "LifeHubEngine", component: ComponentDescriptor, handle: Any
    ) -> None: ...


class RunnerRegistry:
    """Open registry of trusted execution adapters.

    A package names a runner; installing a package never installs or authorizes a
    runner. Runners belong to the host/platform trust boundary.
    """

    def __init__(self) -> None:
        self._runners: dict[str, ComponentRunner] = {}

    def register(self, runner: ComponentRunner) -> None:
        runner_id = runner.id.strip()
        if not runner_id or any(ch.isspace() for ch in runner_id):
            raise ValueError("runner id must be nonempty without whitespace")
        if runner_id in self._runners:
            raise ValueError(f"runner already registered: {runner_id}")
        self._runners[runner_id] = runner

    def resolve(self, runner_id: str) -> ComponentRunner:
        try:
            return self._runners[runner_id]
        except KeyError as exc:
            raise LookupError(f"runner is not installed in this LifeHub engine: {runner_id}") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._runners))


class CoreWasmRunner:
    """Adapter that makes the existing bounded core-Wasm runtime one engine runner."""

    id = "lifehub.wasm"

    def start(self, engine: "LifeHubEngine", component: ComponentDescriptor) -> RunnerStart:
        result = engine.kernel.run_component_wasm(
            plugin_id=component.plugin_id,
            ref=component.ref,
            contract=component.contract,
            config=component.config,
            interface_call=engine._interface_call_for(component),
        )
        return RunnerStart(ExecutionState.COMPLETED, result=result)

    def stop(
        self, engine: "LifeHubEngine", component: ComponentDescriptor, handle: Any
    ) -> None:
        raise ValueError("lifehub.wasm is a one-shot runner and has no running handle")


class LifeHubEngine:
    """Shell-independent execution engine.

    The engine owns platform execution dispatch. Web, desktop, CLI and future
    shells are consumers of this layer, not prerequisites for it.

    Execution state is persisted separately from runner handles. If an engine
    process disappears while a component is running, the next engine instance
    marks that execution interrupted instead of pretending it is still alive.
    """

    def __init__(
        self,
        *,
        db_path: str | Path = "data/lifehub.db",
        plugins_path: str | Path = "lifehub_plugins",
    ) -> None:
        # Acquire before kernel construction or recovery can mutate live history.
        self._lease = EngineLease(db_path)
        try:
            self.kernel = LifeHub(db_path=db_path, plugins_path=plugins_path)
            self.runners = RunnerRegistry()
            self.runners.register(CoreWasmRunner())
            self.runners.register(BackgroundWasmRunner())
            self.routes = InterfaceRouter(self.kernel, self.component)
            self._executions: dict[str, _Execution] = {}
            self._closed = False
            self._init_execution_ledger()
            self._recover_interrupted_executions()
        except BaseException:
            try:
                if hasattr(self, "kernel"):
                    self.kernel.close()
            finally:
                self._lease.close()
            raise

    def close(self) -> None:
        """Release storage only; use shutdown for orderly runner teardown."""
        if not self._closed:
            for execution in self._executions.values():
                execution.ready = False
                if (execution.component.runner_id == "lifehub.wasm-background"
                        and execution.handle is not None):
                    execution.handle.stop()
            try:
                self.kernel.close()
            finally:
                self._lease.close()
                self._closed = True

    def shutdown(self) -> None:
        """Attempt all live runner stops, preserve failures, then release storage.

        Runner stop is cooperative: no forced termination/deadline is implied.
        """
        if self._closed:
            return
        failures = []
        try:
            for execution in tuple(self._executions.values()):
                if execution.state == ExecutionState.RUNNING:
                    try:
                        self.stop(execution.execution_id)
                    except Exception as exc:
                        failures.append(exc)
        finally:
            self.close()
        if failures:
            raise ExceptionGroup("runner failures during Engine shutdown", failures)

    def set_ready(self, execution_id: str, ready: bool) -> ExecutionView:
        """Trusted runner notification; readiness grants no new authority."""
        if self._closed:
            raise RuntimeError("Engine is closed")
        if type(ready) is not bool:
            raise ValueError("ready must be a boolean")
        execution = self._execution(execution_id)
        if execution.state != ExecutionState.RUNNING:
            raise ValueError("only a live running execution can change readiness")
        execution.ready = ready
        execution.updated_at = datetime.now(UTC).isoformat()
        self._persist(execution)
        return self._view(execution)

    def _interface_call_for(self, component: ComponentDescriptor):
        """Trusted runner creates this closure; guests supply only interface and JSON.

        Bind routes to this invocation's exact snapshots, never a guest identity.
        Pure providers use the existing bounded JSON service runtime.
        """
        initial = {
            interface: self.routes.resolve(component.ref, interface)
            for interface in component.requires
        }
        initial_live = {
            route.provider_ref: tuple(item.execution_id for item in self._executions.values()
                                      if item.component.ref == route.provider_ref
                                      and item.state == ExecutionState.RUNNING and item.ready)
            for route in initial.values()
        }

        def call(interface, request):
            self._refresh_background()
            route = self.routes.resolve(component.ref, interface)
            if initial.get(interface) != route:
                raise PermissionError("interface execution snapshot changed")
            provider = self.component(route.provider_ref)
            if provider.runner_id == "lifehub.wasm-background":
                live = [item for item in self._executions.values()
                        if item.component.ref == provider.ref
                        and item.state == ExecutionState.RUNNING and item.ready]
                if (len(live) != 1
                        or initial_live.get(provider.ref) != (live[0].execution_id,)):
                    raise PermissionError("interface needs exactly one ready live provider")
                output = live[0].handle.call(request)
                if self.routes.resolve(component.ref, interface) != route:
                    raise PermissionError("interface snapshots changed during call")
                return output
            if provider.runner_id != "lifehub.wasm" or provider.contract != SERVICE_JSON_CONTRACT:
                raise ValueError("interface provider must use bounded lifehub.service-json@1")
            # This slice supports pure providers only, with no delegated downstream authority.
            if provider.requires:
                raise ValueError("pure interface providers cannot require downstream interfaces")
            bundle = self.kernel.bundle(provider.plugin_id)
            files = self.kernel.packages.approved_files(bundle.root, bundle.manifest)
            module = provider.config.get("module")
            if not isinstance(module, str) or not module.endswith(".wasm") or module not in files:
                raise ValueError("interface provider needs an approved .wasm module")
            output = run_json_service(files[module], request)
            if self.routes.resolve(component.ref, interface) != route:
                raise PermissionError("interface snapshots changed during call")
            return output

        return call

    def register_runner(self, runner: ComponentRunner) -> None:
        self.runners.register(runner)

    def components(self) -> tuple[ComponentDescriptor, ...]:
        items = [self._describe_component(item) for item in self.kernel.registry.components()]
        explicit_refs = {item.ref for item in items}
        for extension in self.kernel.extensions():
            if extension.ref in explicit_refs:
                continue
            runner_id = self._runner_id(extension)
            if runner_id is None:
                continue
            items.append(self._describe_legacy_extension(extension, runner_id))
        return tuple(items)

    def component(self, ref: str) -> ComponentDescriptor:
        try:
            return self._describe_component(self.kernel.registry.component(ref))
        except KeyError:
            pass
        extension = self.kernel.extension(ref)
        runner_id = self._runner_id(extension)
        if runner_id is None:
            raise ValueError(f"extension is not an executable component: {ref}")
        return self._describe_legacy_extension(extension, runner_id)

    def start(self, ref: str) -> ExecutionView:
        if self._closed:
            raise RuntimeError("Engine is closed")
        component = self.component(ref)
        if (component.runner_id == "lifehub.wasm-background"
                and any(item.component.ref == ref and item.state == ExecutionState.RUNNING
                        for item in self._executions.values())):
            self._refresh_background()
            if any(item.component.ref == ref and item.state == ExecutionState.RUNNING
                   for item in self._executions.values()):
                raise ValueError("background component already has a live execution")
        for interface in component.requires:
            self.routes.resolve(component.ref, interface)
        runner = self.runners.resolve(component.runner_id)
        now = datetime.now(UTC).isoformat()
        execution = _Execution(
            execution_id=uuid4().hex,
            component=component,
            state=ExecutionState.RUNNING,
            started_at=now,
            updated_at=now,
        )
        self._executions[execution.execution_id] = execution
        self._persist(execution)
        try:
            started = runner.start(self, component)
            if started.state not in {ExecutionState.RUNNING, ExecutionState.COMPLETED}:
                raise ValueError("runner start must return running or completed state")
            if type(started.ready) is not bool:
                raise ValueError("runner readiness must be a boolean")
            execution.state = started.state
            execution.result = started.result
            execution.handle = started.handle
            execution.ready = started.ready if started.state == ExecutionState.RUNNING else False
            execution.updated_at = datetime.now(UTC).isoformat()
            self._persist(execution)
        except BaseException as exc:
            execution.state = ExecutionState.FAILED
            execution.error = f"{type(exc).__name__}: {exc}"
            execution.updated_at = datetime.now(UTC).isoformat()
            self._persist(execution)
            raise
        return self._view(execution)

    def stop(self, execution_id: str) -> ExecutionView:
        execution = self._execution(execution_id)
        if execution.state != ExecutionState.RUNNING:
            raise ValueError(f"execution is not running: {execution_id}")
        execution.ready = False
        runner = self.runners.resolve(execution.component.runner_id)
        try:
            runner.stop(self, execution.component, execution.handle)
        except BaseException as exc:
            execution.state = ExecutionState.FAILED
            execution.error = f"{type(exc).__name__}: {exc}"
            execution.updated_at = datetime.now(UTC).isoformat()
            self._persist(execution)
            raise
        execution.state = ExecutionState.STOPPED
        execution.updated_at = datetime.now(UTC).isoformat()
        self._persist(execution)
        return self._view(execution)

    def execution(self, execution_id: str) -> ExecutionView:
        self._refresh_background()
        if execution_id in self._executions:
            return self._view(self._executions[execution_id])
        row = self.kernel.store.conn.execute(
            """
            SELECT execution_id, component_ref, runner_id, state, started_at, updated_at, error
            FROM lifehub_engine_executions
            WHERE execution_id=?
            """,
            (execution_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown execution: {execution_id}")
        return ExecutionView(
            execution_id=row["execution_id"],
            component_ref=row["component_ref"],
            runner_id=row["runner_id"],
            state=ExecutionState(row["state"]),
            started_at=row["started_at"],
            updated_at=row["updated_at"],
            error=row["error"],
        )

    def executions(self, *, limit: int = 100) -> tuple[ExecutionView, ...]:
        self._refresh_background()
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("execution limit must be an integer from 1 to 1000")
        rows = self.kernel.store.conn.execute(
            """
            SELECT execution_id, component_ref, runner_id, state, started_at, updated_at, error
            FROM lifehub_engine_executions
            ORDER BY started_at DESC, execution_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(
            ExecutionView(
                execution_id=row["execution_id"],
                component_ref=row["component_ref"],
                runner_id=row["runner_id"],
                state=ExecutionState(row["state"]),
                started_at=row["started_at"],
                updated_at=row["updated_at"],
                error=row["error"],
                ready=(self._executions[row["execution_id"]].ready
                       if row["execution_id"] in self._executions else False),
            )
            for row in rows
        )

    @staticmethod
    def _runner_id(extension: RegisteredExtension) -> str | None:
        contribution = extension.contribution
        if contribution.runner is not None:
            return contribution.runner
        # Compatibility for v0.1 core-Wasm packages. Shell entrypoints such as
        # lifehub.primitive deliberately do not become engine runners.
        if contribution.entrypoint == "lifehub.wasm":
            return "lifehub.wasm"
        return None

    @staticmethod
    def _describe_component(component: RegisteredComponent) -> ComponentDescriptor:
        spec = component.component
        return ComponentDescriptor(
            ref=component.ref,
            plugin_id=component.plugin_id,
            point=None,
            runner_id=spec.runner,
            contract=spec.contract,
            provides=tuple(spec.provides),
            requires=tuple(spec.requires),
            activation=tuple(spec.activation),
            config=deepcopy(spec.config),
        )

    @staticmethod
    def _describe_legacy_extension(
        extension: RegisteredExtension, runner_id: str
    ) -> ComponentDescriptor:
        contribution = extension.contribution
        return ComponentDescriptor(
            ref=extension.ref,
            plugin_id=extension.plugin_id,
            point=contribution.point,
            runner_id=runner_id,
            contract=contribution.contract,
            provides=(),
            requires=(),
            activation=tuple(contribution.activation),
            config=deepcopy(contribution.config),
        )

    def _execution(self, execution_id: str) -> _Execution:
        try:
            return self._executions[execution_id]
        except KeyError as exc:
            raise KeyError(
                f"execution {execution_id} has no live runner handle in this engine process"
            ) from exc

    def _refresh_background(self) -> None:
        for item in self._executions.values():
            if (item.component.runner_id == "lifehub.wasm-background"
                    and item.state == ExecutionState.RUNNING
                    and item.handle is not None and item.handle.process.poll() is not None):
                item.state = ExecutionState.FAILED
                item.ready = False
                item.error = "background guest process exited"
                item.updated_at = datetime.now(UTC).isoformat()
                item.handle.stop()
                self._persist(item)

    def _init_execution_ledger(self) -> None:
        self.kernel.store.conn.executescript(_ENGINE_SCHEMA)
        self.kernel.store.conn.commit()

    def _recover_interrupted_executions(self) -> None:
        now = datetime.now(UTC).isoformat()
        with self.kernel.store.conn:
            self.kernel.store.conn.execute(
                """
                UPDATE lifehub_engine_executions
                SET state=?, updated_at=?,
                    error=COALESCE(error, 'engine process ended before execution completed')
                WHERE state=?
                """,
                (ExecutionState.INTERRUPTED, now, ExecutionState.RUNNING),
            )

    def _persist(self, execution: _Execution) -> None:
        with self.kernel.store.conn:
            self.kernel.store.conn.execute(
                """
                INSERT INTO lifehub_engine_executions(
                    execution_id, component_ref, runner_id, state,
                    started_at, updated_at, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(execution_id) DO UPDATE SET
                    state=excluded.state,
                    updated_at=excluded.updated_at,
                    error=excluded.error
                """,
                (
                    execution.execution_id,
                    execution.component.ref,
                    execution.component.runner_id,
                    execution.state,
                    execution.started_at,
                    execution.updated_at,
                    execution.error,
                ),
            )

    @staticmethod
    def _view(execution: _Execution) -> ExecutionView:
        return ExecutionView(
            execution_id=execution.execution_id,
            component_ref=execution.component.ref,
            runner_id=execution.component.runner_id,
            state=execution.state,
            started_at=execution.started_at,
            updated_at=execution.updated_at,
            result=execution.result,
            error=execution.error,
            ready=execution.ready,
        )
