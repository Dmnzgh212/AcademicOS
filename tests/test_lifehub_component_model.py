from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from academicos.lifehub.engine import ExecutionState, LifeHubEngine, RunnerStart
from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.store import LifeStore


class _Runner:
    id = "test.component"

    def __init__(self) -> None:
        self.stopped = []

    def start(self, engine, component):
        assert component.provides == ("example.output@1",)
        assert component.requires == ()
        return RunnerStart(ExecutionState.RUNNING, handle=component.ref)

    def stop(self, engine, component, handle):
        self.stopped.append((component.ref, handle))


def _write_component_package(root: Path) -> None:
    package = root / "demo.component"
    package.mkdir(parents=True)
    (package / "plugin.toml").write_text(
        """
manifest_version = 1
api = "lifehub@1"
id = "demo.component"
name = "Component only"
version = "1.0.0"

[[components]]
id = "worker"
runner = "test.component"
contract = "example.worker@1"
provides = ["example.output@1"]
requires = []
activation = ["manual"]

[components.config]
mode = "synthetic"
""".strip(),
        encoding="utf-8",
    )


def test_package_can_be_executable_without_any_extension_or_ui(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_component_package(plugins)
    engine = LifeHubEngine(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    runner = _Runner()
    try:
        assert engine.kernel.extensions() == ()
        assert engine.kernel.registry.points() == ()

        components = engine.components()
        assert len(components) == 1
        component = components[0]
        assert component.ref == "demo.component:worker"
        assert component.point is None
        assert component.runner_id == "test.component"
        assert component.provides == ("example.output@1",)
        assert component.requires == ()

        engine.register_runner(runner)
        started = engine.start(component.ref)
        assert started.state == ExecutionState.RUNNING
        stopped = engine.stop(started.execution_id)
        assert stopped.state == ExecutionState.STOPPED
        assert runner.stopped == [(component.ref, component.ref)]
    finally:
        engine.close()


def test_component_and_extension_ids_share_one_package_identity_namespace() -> None:
    payload = {
        "id": "demo.collision",
        "name": "Collision",
        "version": "1.0.0",
        "components": [{"id": "same", "runner": "test.component"}],
        "contributes": [{"id": "same", "point": "shell.surface"}],
    }
    with pytest.raises(ValueError, match="duplicate package entry id"):
        PluginManifest.model_validate(payload)


def test_component_interface_ids_are_explicit_and_unique() -> None:
    payload = {
        "id": "demo.interfaces",
        "name": "Interfaces",
        "version": "1.0.0",
        "components": [
            {
                "id": "worker",
                "runner": "test.component",
                "provides": ["example.echo@1", "example.echo@1"],
            }
        ],
    }
    with pytest.raises(ValueError, match="duplicate component interface"):
        PluginManifest.model_validate(payload)


def test_first_class_core_wasm_component_runs_without_extension_surface(tmp_path: Path) -> None:
    wasmtime = pytest.importorskip("wasmtime")
    module = wasmtime.wat2wasm(
        """(module
          (memory (export "memory") 1)
          (func (export "run") (result i32) (i32.const 7)))"""
    )
    archive = tmp_path / "component.zip"
    manifest = b"""manifest_version = 1
api = "lifehub@1"
id = "demo.component-wasm"
name = "Component Wasm"
version = "1.0.0"
[permissions]
storage_read = []
storage_write = []
network_retrieval = []
localhost_ports = []

[[components]]
id = "worker"
runner = "lifehub.wasm"
contract = "lifehub.core-wasm@1"

[components.config]
module = "worker.wasm"
"""
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("plugin.toml", manifest)
        output.writestr("worker.wasm", module)

    installed = tmp_path / "installed"
    db = tmp_path / "lifehub.db"
    store = LifeStore(db)
    try:
        installer = PackageInstaller(installed, store)
        review = installer.review(archive)
        installer.install(archive, approved_hash=review.content_hash)
    finally:
        store.close()

    engine = LifeHubEngine(db_path=db, plugins_path=installed)
    try:
        assert engine.kernel.extensions() == ()
        component = engine.component("demo.component-wasm:worker")
        assert component.runner_id == "lifehub.wasm"
        result = engine.start(component.ref)
        assert result.state == ExecutionState.COMPLETED
        assert result.result == 7
    finally:
        engine.close()
