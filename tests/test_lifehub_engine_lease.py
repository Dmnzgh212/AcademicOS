import subprocess
import sys

import pytest

from academicos.lifehub.engine import LifeHubEngine, RunnerStart, ExecutionState
from academicos.lifehub.engine_lease import EngineLease


def test_second_manager_cannot_recover_first_managers_live_execution(tmp_path):
    plugins = tmp_path / "plugins"
    package = plugins / "owner.test"
    package.mkdir(parents=True)
    (package / "plugin.toml").write_text('''
manifest_version = 1
api = "lifehub@1"
id = "owner.test"
name = "Owner"
version = "1.0.0"
[[components]]
id = "worker"
runner = "owner.runner"
''')

    class Runner:
        id = "owner.runner"

        def start(self, engine, component):
            return RunnerStart(ExecutionState.RUNNING, ready=True)

        def stop(self, engine, component, handle):
            pass

    db = tmp_path / "engine.db"
    first = LifeHubEngine(db_path=db, plugins_path=plugins)
    first.register_runner(Runner())
    started = first.start("owner.test:worker")
    try:
        with pytest.raises(PermissionError, match="already owned"):
            LifeHubEngine(db_path=db, plugins_path=plugins)
        row = first.kernel.store.conn.execute(
            "SELECT state FROM lifehub_engine_executions WHERE execution_id=?",
            (started.execution_id,),
        ).fetchone()
        assert row["state"] == "running"
        assert first.execution(started.execution_id).ready
    finally:
        first.shutdown()


def test_same_path_alias_is_denied_but_different_database_is_independent(tmp_path):
    first = EngineLease(tmp_path / "engine.db")
    try:
        with pytest.raises(PermissionError):
            EngineLease(tmp_path / "sub" / ".." / "engine.db")
        other = EngineLease(tmp_path / "other.db")
        other.close()
    finally:
        first.close()
    next_owner = EngineLease(tmp_path / "engine.db")
    next_owner.close()


def test_owner_process_death_releases_lease_without_deleting_sidecar(tmp_path):
    db = tmp_path / "engine.db"
    source = '''import sys
from academicos.lifehub.engine_lease import EngineLease
lease = EngineLease(sys.argv[1])
print("owned", flush=True)
sys.stdin.read()
'''
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", source, str(db)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        assert process.stdout.readline().strip() == "owned"
        with pytest.raises(PermissionError):
            EngineLease(db)
    finally:
        process.kill()
        process.communicate(timeout=5)
    recovered = EngineLease(db)
    try:
        assert recovered.path.exists()
    finally:
        recovered.close()


def test_failed_engine_initialization_releases_lease(tmp_path, monkeypatch):
    import academicos.lifehub.engine as module

    actual = module.LifeHub

    def broken(**kwargs):
        raise RuntimeError("initialization failed")

    monkeypatch.setattr(module, "LifeHub", broken)
    with pytest.raises(RuntimeError):
        module.LifeHubEngine(db_path=tmp_path / "engine.db")
    monkeypatch.setattr(module, "LifeHub", actual)
    engine = module.LifeHubEngine(db_path=tmp_path / "engine.db", plugins_path=tmp_path / "plugins")
    engine.shutdown()
