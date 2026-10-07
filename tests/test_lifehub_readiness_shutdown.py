import pytest

from academicos.lifehub.control import CONTROL_API, EngineController
from academicos.lifehub.daemon import LifeHubEngineDaemon
from academicos.lifehub.engine import ExecutionState, LifeHubEngine, RunnerStart


class Runner:
    id = "test.lifecycle"

    def __init__(self, *, ready=False, fail=False):
        self.ready, self.fail = ready, fail
        self.stops = []

    def start(self, engine, component):
        return RunnerStart(ExecutionState.RUNNING, handle=component.ref, ready=self.ready)

    def stop(self, engine, component, handle):
        self.stops.append(handle)
        if self.fail and component.ref.endswith(":first"):
            raise RuntimeError("stop failed")


def engine_at(tmp_path, runner):
    plugins = tmp_path / "plugins"
    package = plugins / "test.lifecycle"
    package.mkdir(parents=True, exist_ok=True)
    (package / "plugin.toml").write_text('''
manifest_version = 1
api = "lifehub@1"
id = "test.lifecycle"
name = "Lifecycle"
version = "1.0.0"
[[components]]
id = "first"
runner = "test.lifecycle"
[[components]]
id = "second"
runner = "test.lifecycle"
''')
    engine = LifeHubEngine(db_path=tmp_path / "engine.db", plugins_path=plugins)
    engine.register_runner(runner)
    return engine


def test_running_does_not_imply_readiness_and_control_observes_transition(tmp_path):
    engine = engine_at(tmp_path, Runner())
    try:
        started = engine.start("test.lifecycle:first")
        assert started.state == "running" and not started.ready
        ready = engine.set_ready(started.execution_id, True)
        assert ready.ready
        assert engine.execution(started.execution_id).ready
        assert engine.executions()[0].ready
        response = EngineController(engine).handle({"api": CONTROL_API, "op": "executions"})
        assert response["result"][0]["ready"] is True
        assert not engine.set_ready(started.execution_id, False).ready
        with pytest.raises(ValueError):
            engine.set_ready(started.execution_id, "true")
        engine.stop(started.execution_id)
        with pytest.raises(ValueError):
            engine.set_ready(started.execution_id, True)
    finally:
        engine.shutdown()


def test_runner_can_report_immediate_readiness_but_recovery_cannot_restore_it(tmp_path):
    engine = engine_at(tmp_path, Runner(ready=True))
    started = engine.start("test.lifecycle:first")
    assert started.ready
    engine.close()  # storage-only teardown models loss of this manager's handles
    recovered = engine_at(tmp_path, Runner(ready=True))
    try:
        view = recovered.execution(started.execution_id)
        assert view.state == "interrupted" and not view.ready
        with pytest.raises(KeyError):
            recovered.set_ready(started.execution_id, True)
    finally:
        recovered.shutdown()


@pytest.mark.parametrize("fail", [False, True])
def test_shutdown_attempts_all_stops_and_preserves_terminal_history(tmp_path, fail):
    runner = Runner(ready=True, fail=fail)
    engine = engine_at(tmp_path, runner)
    first = engine.start("test.lifecycle:first")
    second = engine.start("test.lifecycle:second")
    if fail:
        with pytest.raises(ExceptionGroup, match="shutdown"):
            engine.shutdown()
    else:
        engine.shutdown()
    assert runner.stops == ["test.lifecycle:first", "test.lifecycle:second"]
    engine.shutdown()
    with pytest.raises(RuntimeError, match="closed"):
        engine.start("test.lifecycle:first")
    recovered = engine_at(tmp_path, Runner())
    try:
        view = recovered.execution(first.execution_id)
        assert view.state == (ExecutionState.FAILED if fail else ExecutionState.STOPPED)
        assert not view.ready
        assert recovered.execution(second.execution_id).state == "stopped"
        assert not recovered.execution(second.execution_id).ready
    finally:
        recovered.shutdown()


def test_completed_runner_cannot_remain_ready(tmp_path):
    class Completed(Runner):
        def start(self, engine, component):
            return RunnerStart(ExecutionState.COMPLETED, ready=True)

    engine = engine_at(tmp_path, Completed())
    try:
        assert not engine.start("test.lifecycle:first").ready
    finally:
        engine.shutdown()


@pytest.mark.parametrize("fail", [False, True])
def test_daemon_close_stops_runner_and_removes_owned_socket_even_on_failure(tmp_path, fail):
    runner = Runner(fail=fail)
    engine = engine_at(tmp_path, runner)
    engine.start("test.lifecycle:first")

    class Listener:
        closed = False

        def close(self):
            self.closed = True

    daemon = object.__new__(LifeHubEngineDaemon)
    daemon.engine, daemon.server = engine, Listener()
    daemon.address = str(tmp_path / "owned.sock")
    daemon._owns_unix_path = True
    (tmp_path / "owned.sock").touch()
    if fail:
        with pytest.raises(ExceptionGroup):
            daemon.close()
    else:
        daemon.close()
    assert daemon.server.closed
    assert runner.stops == ["test.lifecycle:first"]
    assert not (tmp_path / "owned.sock").exists()
