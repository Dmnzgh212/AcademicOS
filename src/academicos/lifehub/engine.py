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
from academicos.lifehub.registry import RegisteredComponent, RegisteredExtension


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
        self.kernel = LifeHub(db_path=db_path, plugins_path=plugins_path)
        self.runners = RunnerRegistry()
        self.runners.register(CoreWasmRunner())
        self._executions: dict[str, _Execution] = {}
        self._init_execution_ledger()
        self._recover_interrupted_executions()

    def close(self) -> None:
        self.kernel.close()

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
        component = self.component(ref)
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
            execution.state = started.state
            execution.result = started.result
            execution.handle = started.handle
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
        )
