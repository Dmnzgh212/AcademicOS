from __future__ import annotations

from pathlib import Path

from academicos.lifehub.engine import ExecutionState, LifeHubEngine, RunnerStart


def _write_package(root: Path) -> None:
    package = root / "demo.supervisor"
    package.mkdir(parents=True)
    (package / "plugin.toml").write_text(
        """
manifest_version = 1
api = "lifehub@1"
id = "demo.supervisor"
name = "Supervisor demo"
version = "1.0.0"

[[contributes]]
id = "worker"
point = "example.component"
runner = "test.persistent"
""".strip(),
        encoding="utf-8",
    )


class _PersistentRunner:
    id = "test.persistent"

    def start(self, engine, component):
        return RunnerStart(ExecutionState.RUNNING, handle={"ref": component.ref})

    def stop(self, engine, component, handle):
        return None


class _FailingRunner:
    id = "test.persistent"

    def start(self, engine, component):
        raise RuntimeError("synthetic failure")

    def stop(self, engine, component, handle):
        return None


def test_running_execution_is_recovered_as_interrupted_after_engine_restart(
    tmp_path: Path,
) -> None:
    plugins = tmp_path / "plugins"
    db = tmp_path / "lifehub.db"
    _write_package(plugins)

    first = LifeHubEngine(db_path=db, plugins_path=plugins)
    first.register_runner(_PersistentRunner())
    started = first.start("demo.supervisor:worker")
    assert started.state == ExecutionState.RUNNING
    first.close()

    second = LifeHubEngine(db_path=db, plugins_path=plugins)
    try:
        recovered = second.execution(started.execution_id)
        assert recovered.state == ExecutionState.INTERRUPTED
        assert "engine process ended" in (recovered.error or "")
    finally:
        second.close()


def test_stopped_execution_remains_terminal_across_restart(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    db = tmp_path / "lifehub.db"
    _write_package(plugins)

    first = LifeHubEngine(db_path=db, plugins_path=plugins)
    first.register_runner(_PersistentRunner())
    started = first.start("demo.supervisor:worker")
    stopped = first.stop(started.execution_id)
    assert stopped.state == ExecutionState.STOPPED
    first.close()

    second = LifeHubEngine(db_path=db, plugins_path=plugins)
    try:
        recovered = second.execution(started.execution_id)
        assert recovered.state == ExecutionState.STOPPED
    finally:
        second.close()


def test_failed_start_is_persisted_for_diagnostics(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    db = tmp_path / "lifehub.db"
    _write_package(plugins)

    engine = LifeHubEngine(db_path=db, plugins_path=plugins)
    engine.register_runner(_FailingRunner())
    try:
        try:
            engine.start("demo.supervisor:worker")
        except RuntimeError:
            pass
        rows = engine.executions()
        assert len(rows) == 1
        assert rows[0].state == ExecutionState.FAILED
        assert rows[0].error == "RuntimeError: synthetic failure"
    finally:
        engine.close()


def test_execution_listing_is_bounded(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    db = tmp_path / "lifehub.db"
    _write_package(plugins)

    engine = LifeHubEngine(db_path=db, plugins_path=plugins)
    engine.register_runner(_PersistentRunner())
    try:
        first = engine.start("demo.supervisor:worker")
        second = engine.start("demo.supervisor:worker")
        rows = engine.executions(limit=1)
        assert len(rows) == 1
        assert rows[0].execution_id in {first.execution_id, second.execution_id}
    finally:
        engine.close()
