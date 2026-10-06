from __future__ import annotations

import os
from pathlib import Path
from threading import Thread

import pytest

from academicos.lifehub.control import CONTROL_API, control_request
from academicos.lifehub.daemon import (
    LifeHubEngineDaemon,
    default_control_endpoint,
    load_authkey,
    load_or_create_authkey,
)
from academicos.lifehub.engine import ExecutionState, RunnerStart


def _write_package(root: Path) -> None:
    package = root / "demo.daemon"
    package.mkdir(parents=True)
    (package / "plugin.toml").write_text(
        """
manifest_version = 1
api = "lifehub@1"
id = "demo.daemon"
name = "Daemon demo"
version = "1.0.0"

[[contributes]]
id = "worker"
point = "example.component"
runner = "test.daemon"
""".strip(),
        encoding="utf-8",
    )


class _Runner:
    id = "test.daemon"

    def start(self, engine, component):
        return RunnerStart(ExecutionState.RUNNING, handle=component.ref)

    def stop(self, engine, component, handle):
        assert handle == component.ref


def test_engine_authkey_is_created_once_and_reused(tmp_path: Path) -> None:
    path = tmp_path / "engine.key"
    first = load_or_create_authkey(path)
    second = load_or_create_authkey(path)
    assert first == second
    assert len(first) == 32
    assert load_authkey(path) == first


def test_default_endpoint_is_local_platform_transport(tmp_path: Path) -> None:
    address, family = default_control_endpoint(tmp_path)
    if os.name == "nt":
        assert family == "AF_PIPE"
        assert address.startswith(r"\\.\pipe\")
    else:
        assert family == "AF_UNIX"
        assert address == str(tmp_path / "lifehub-engine.sock")


@pytest.mark.skipif(os.name == "nt", reason="CI validates AF_UNIX; Windows daemon uses AF_PIPE")
def test_daemon_keeps_runner_handle_across_separate_control_clients(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_package(plugins)
    socket_path = str(tmp_path / "engine.sock")
    authkey = b"daemon-test-key-that-is-at-least-32-bytes"
    daemon = LifeHubEngineDaemon(
        db_path=tmp_path / "lifehub.db",
        plugins_path=plugins,
        address=socket_path,
        family="AF_UNIX",
        authkey=authkey,
    )
    daemon.engine.register_runner(_Runner())

    def request(op: str, **extra):
        thread = Thread(target=daemon.serve_once, daemon=True)
        thread.start()
        response = control_request(
            socket_path,
            {"api": CONTROL_API, "op": op, **extra},
            authkey=authkey,
            family="AF_UNIX",
        )
        thread.join(timeout=5)
        assert not thread.is_alive()
        return response

    try:
        components = request("components")
        assert components["result"][0]["ref"] == "demo.daemon:worker"

        started = request("start", ref="demo.daemon:worker")
        assert started["result"]["state"] == "running"

        stopped = request("stop", execution_id=started["result"]["execution_id"])
        assert stopped["result"]["state"] == "stopped"
    finally:
        daemon.close()

    assert not Path(socket_path).exists()
