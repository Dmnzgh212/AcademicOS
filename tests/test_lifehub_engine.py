from __future__ import annotations

from pathlib import Path

import pytest

from academicos.lifehub.engine import (
    ExecutionState,
    LifeHubEngine,
    RunnerStart,
)
from academicos.lifehub.manifest import PluginManifest


def _write_package(root: Path, *, runner: str = "test.runner") -> None:
    package = root / "demo.engine"
    package.mkdir(parents=True)
    (package / "plugin.toml").write_text(
        f"""
manifest_version = 1
api = "lifehub@1"
id = "demo.engine"
name = "Engine demo"
version = "1.0.0"

[[contributes]]
id = "card"
point = "workspace.widget"
entrypoint = "lifehub.primitive"

[[contributes]]
id = "worker"
point = "example.component"
runner = "{runner}"
contract = "example.worker@1"
""".strip(),
        encoding="utf-8",
    )


class _PersistentRunner:
    id = "test.runner"

    def __init__(self) -> None:
        self.stopped = []

    def start(self, engine, component):
        return RunnerStart(ExecutionState.RUNNING, handle={"ref": component.ref})

    def stop(self, engine, component, handle):
        self.stopped.append((component.ref, handle))


def test_engine_discovers_executable_components_without_treating_shell_widgets_as_runtime(
    tmp_path: Path,
) -> None:
    plugins = tmp_path / "plugins"
    _write_package(plugins)
    engine = LifeHubEngine(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    try:
        components = engine.components()
        assert [item.ref for item in components] == ["demo.engine:worker"]
        assert components[0].point == "example.component"
        assert components[0].runner_id == "test.runner"
    finally:
        engine.close()


def test_runner_registry_supports_non_web_long_lived_component_lifecycle(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_package(plugins)
    engine = LifeHubEngine(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    runner = _PersistentRunner()
    try:
        engine.register_runner(runner)
        started = engine.start("demo.engine:worker")
        assert started.state == ExecutionState.RUNNING
        assert started.runner_id == "test.runner"

        stopped = engine.stop(started.execution_id)
        assert stopped.state == ExecutionState.STOPPED
        assert runner.stopped == [
            ("demo.engine:worker", {"ref": "demo.engine:worker"})
        ]
    finally:
        engine.close()


def test_unknown_runner_fails_at_execution_boundary_not_discovery(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_package(plugins, runner="vendor.future")
    engine = LifeHubEngine(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    try:
        assert engine.component("demo.engine:worker").runner_id == "vendor.future"
        with pytest.raises(LookupError, match="runner is not installed"):
            engine.start("demo.engine:worker")
    finally:
        engine.close()


def test_legacy_core_wasm_entrypoint_maps_to_builtin_runner(tmp_path: Path) -> None:
    package = tmp_path / "plugins" / "demo.wasm"
    package.mkdir(parents=True)
    (package / "plugin.toml").write_text(
        """
manifest_version = 1
api = "lifehub@1"
id = "demo.wasm"
name = "Wasm demo"
version = "1.0.0"

[[contributes]]
id = "worker"
point = "example.component"
entrypoint = "lifehub.wasm"
contract = "lifehub.core-wasm@1"
""".strip(),
        encoding="utf-8",
    )
    engine = LifeHubEngine(db_path=tmp_path / "lifehub.db", plugins_path=tmp_path / "plugins")
    try:
        component = engine.component("demo.wasm:worker")
        assert component.runner_id == "lifehub.wasm"
        assert "lifehub.wasm" in engine.runners.ids()
    finally:
        engine.close()


def test_manifest_runner_is_a_host_execution_identifier() -> None:
    payload = {
        "id": "demo.runner",
        "name": "Runner",
        "version": "1.0.0",
        "contributes": [{"id": "x", "point": "x", "runner": "bad runner"}],
    }
    with pytest.raises(ValueError, match="runner"):
        PluginManifest.model_validate(payload)
