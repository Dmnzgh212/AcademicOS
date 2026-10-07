"""Real Windows named-pipe boundaries, independently of Unix transport tests."""
import os
from multiprocessing import AuthenticationError
from multiprocessing.connection import Client
from threading import Thread
from uuid import uuid4

import pytest

from academicos.lifehub.control import CONTROL_API, control_request
from academicos.lifehub.daemon import LifeHubEngineDaemon
from academicos.lifehub.engine import LifeHubEngine, ExecutionState, RunnerStart
from academicos.lifehub.messages import MAX_IO_BYTES

pytestmark = pytest.mark.skipif(os.name != "nt", reason="real Windows AF_PIPE validation")


def daemon_at(tmp_path):
    return LifeHubEngineDaemon(
        db_path=tmp_path / "engine.db", plugins_path=tmp_path / "plugins",
        address=rf"\\.\pipe\lifehub-test-{uuid4().hex}", family="AF_PIPE",
        authkey=b"windows-engine-control-test-key",
    )


def test_windows_named_pipe_rejects_bad_clients_and_accepts_next_ping(tmp_path):
    daemon = daemon_at(tmp_path)
    key, address = b"windows-engine-control-test-key", daemon.address
    errors = []

    def serve():
        try:
            for _ in range(5):
                daemon.serve_once()
        except BaseException as exc:
            errors.append(exc)

    thread = Thread(target=serve, daemon=True)
    thread.start()
    try:
        with pytest.raises(AuthenticationError):
            Client(address, authkey=b"wrong", family="AF_PIPE")
        for payload in (b"{", b"x" * (MAX_IO_BYTES + 1), None):
            connection = Client(address, authkey=key, family="AF_PIPE")
            try:
                if payload is not None:
                    try:
                        connection.send_bytes(payload)
                    except BrokenPipeError:
                        assert len(payload) > MAX_IO_BYTES
            finally:
                connection.close()
        response = control_request(
            address, {"api": CONTROL_API, "op": "ping"}, authkey=key, family="AF_PIPE"
        )
        assert response["ok"] is True
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert not errors
    finally:
        daemon.close()


def test_windows_daemon_retains_handles_across_clients_and_shuts_down(tmp_path):
    package = tmp_path / "plugins" / "windows.test"
    package.mkdir(parents=True)
    (package / "plugin.toml").write_text('''
manifest_version = 1
api = "lifehub@1"
id = "windows.test"
name = "Windows test"
version = "1.0.0"
[[components]]
id = "worker"
runner = "windows.test"
''')

    class Runner:
        id = "windows.test"
        stops = []

        def start(self, engine, component):
            return RunnerStart(ExecutionState.RUNNING, handle=component.ref, ready=True)

        def stop(self, engine, component, handle):
            self.stops.append(handle)

    runner = Runner()
    daemon = daemon_at(tmp_path)
    daemon.engine.register_runner(runner)

    def request(op, **fields):
        result, errors = {}, []

        def client():
            try:
                result["value"] = control_request(
                    daemon.address, {"api": CONTROL_API, "op": op, **fields},
                    authkey=b"windows-engine-control-test-key", family="AF_PIPE",
                )
            except BaseException as exc:
                errors.append(exc)

        thread = Thread(target=client, daemon=True)
        thread.start()
        daemon.serve_once()
        thread.join(timeout=5)
        assert not thread.is_alive() and not errors
        assert result["value"]["ok"] is True
        return result["value"]["result"]

    try:
        started = request("start", ref="windows.test:worker")
        assert started["state"] == "running" and started["ready"]
        assert request("executions")[0]["execution_id"] == started["execution_id"]
        assert not runner.stops
    finally:
        daemon.close()
    assert runner.stops == ["windows.test:worker"]
    recovered = LifeHubEngine(db_path=tmp_path / "engine.db", plugins_path=tmp_path / "plugins")
    try:
        assert recovered.execution(started["execution_id"]).state == "stopped"
    finally:
        recovered.shutdown()
