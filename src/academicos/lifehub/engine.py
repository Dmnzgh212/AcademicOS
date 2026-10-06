"""Shell-independent LifeHub platform engine and component runner abstraction."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.registry import RegisteredExtension


class ExecutionState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class ComponentDescriptor:
    """An executable component discovered from an otherwise open extension graph."""

    ref: str
    plugin_id: str
    point: str
    runner_id: str
    contract: str | None
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
    result: Any = None
    error: str | None = None


@dataclass
class _Execution:
    execution_id: str
    component: ComponentDescriptor
    state: ExecutionState
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
        result = engine.kernel.run_wasm(component.ref)
        return RunnerStart(ExecutionState.COMPLETED, result=result)

    def stop(
        self, engine: "LifeHubEngine", component: ComponentDescriptor, handle: Any
    ) -> None:
        raise ValueError("lifehub.wasm is a one-shot runner and has no running handle")


class LifeHubEngine:
    """Shell-independent execution engine.

    The engine owns platform execution dispatch. Web, desktop, CLI and future
    shells are consumers of this layer, not prerequisites for it.
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

    def close(self) -> None:
        self.kernel.close()

    def register_runner(self, runner: ComponentRunner) -> None:
        self.runners.register(runner)

    def components(self) -> tuple[ComponentDescriptor, ...]:
        items = []
        for extension in self.kernel.extensions():
            runner_id = self._runner_id(extension)
            if runner_id is None:
                continue
            items.append(self._describe(extension, runner_id))
        return tuple(items)

    def component(self, ref: str) -> ComponentDescriptor:
        extension = self.kernel.extension(ref)
        runner_id = self._runner_id(extension)
        if runner_id is None:
            raise ValueError(f"extension is not an executable component: {ref}")
        return self._describe(extension, runner_id)

    def start(self, ref: str) -> ExecutionView:
        component = self.component(ref)
        runner = self.runners.resolve(component.runner_id)
        execution = _Execution(
            execution_id=uuid4().hex,
            component=component,
            state=ExecutionState.RUNNING,
        )
        self._executions[execution.execution_id] = execution
        try:
            started = runner.start(self, component)
            if started.state not in {ExecutionState.RUNNING, ExecutionState.COMPLETED}:
                raise ValueError("runner start must return running or completed state")
            execution.state = started.state
            execution.result = started.result
            execution.handle = started.handle
        except BaseException as exc:
            execution.state = ExecutionState.FAILED
            execution.error = f"{type(exc).__name__}: {exc}"
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
            raise
        execution.state = ExecutionState.STOPPED
        return self._view(execution)

    def execution(self, execution_id: str) -> ExecutionView:
        return self._view(self._execution(execution_id))

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
    def _describe(extension: RegisteredExtension, runner_id: str) -> ComponentDescriptor:
        contribution = extension.contribution
        return ComponentDescriptor(
            ref=extension.ref,
            plugin_id=extension.plugin_id,
            point=contribution.point,
            runner_id=runner_id,
            contract=contribution.contract,
            activation=tuple(contribution.activation),
            config=deepcopy(contribution.config),
        )

    def _execution(self, execution_id: str) -> _Execution:
        try:
            return self._executions[execution_id]
        except KeyError as exc:
            raise KeyError(f"unknown execution: {execution_id}") from exc

    @staticmethod
    def _view(execution: _Execution) -> ExecutionView:
        return ExecutionView(
            execution_id=execution.execution_id,
            component_ref=execution.component.ref,
            runner_id=execution.component.runner_id,
            state=execution.state,
            result=execution.result,
            error=execution.error,
        )
