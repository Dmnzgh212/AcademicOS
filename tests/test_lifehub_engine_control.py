from __future__ import annotations

import os
from pathlib import Path
from threading import Thread

import pytest

from academicos.lifehub.control import (
    CONTROL_API,
    EngineControlServer,
    EngineController,
    control_request,
)
from academicos.lifehub.engine import ExecutionState, LifeHubEngine, RunnerStart


def _write_package(root: Path) -> None:
    package = root / "demo.control"
    package.mkdir(parents=True)
    (package / "plugin.toml").write_text(
        """
manifest_version = 1
api = "lifehub@1"
id = "demo.control"
name = "Control demo"
version = "1.0.0"

[[contributes]]
id = "worker"
point = "example.component"
runner = "test.control"
""".strip(),
        encoding="utf-8",
    )


class _Runner:
    id = "test.control"

    def start(self, engine, component):
        return RunnerStart(ExecutionState.RUNNING, handle=component.ref)

    def stop(self, engine, component, handle):
        assert handle == component.ref


def _request(op: str, **extra):
    return {"api": CONTROL_API, "op": op, **extra}


def test_controller_exposes_engine_not_shell_state(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_package(plugins)
    engine = LifeHubEngine(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    engine.register_runner(_Runner())
    controller = EngineController(engine)
    try:
        ping = controller.handle(_request("ping"))
        assert ping == {"api": CONTROL_API, "ok": True, "result": {"status": "ok"}}

        components = controller.handle(_request("components"))
        assert components["ok"] is True
        assert components["result"][0]["ref"] == "demo.control:worker"
        assert "workspace" not in components["result"][0]

        started = controller.handle(_request("start", ref="demo.control:worker"))
        assert started["ok"] is True
        assert started["result"]["state"] == "running"
        execution_id = started["result"]["execution_id"]

        stopped = controller.handle(_request("stop", execution_id=execution_id))
        assert stopped["ok"] is True
        assert stopped["result"]["state"] == "stopped"
    finally:
        engine.close()


def test_control_protocol_rejects_unknown_fields_and_unknown_ops(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_package(plugins)
    engine = LifeHubEngine(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    controller = EngineController(engine)
    try:
        bad = controller.handle({"api": CONTROL_API, "op": "ping", "surprise": True})
        assert bad["ok"] is False
        assert bad["error"]["type"] == "ValueError"

        unknown = controller.handle(_request("launch-browser"))
        assert unknown["ok"] is False
        assert "unsupported engine control operation" in unknown["error"]["message"]

        wrong_api = controller.handle({"api": "other@1", "op": "ping"})
        assert wrong_api["ok"] is False
        assert "unsupported engine control API" in wrong_api["error"]["message"]
    finally:
        engine.close()


@pytest.mark.skipif(os.name == "nt", reason="CI validates AF_UNIX; Windows uses AF_PIPE")
def test_authenticated_local_transport_uses_bounded_json_not_web(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_package(plugins)
    engine = LifeHubEngine(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    socket_path = str(tmp_path / "engine.sock")
    authkey = b"synthetic-engine-control-key"
    server = EngineControlServer(engine, socket_path, authkey=authkey, family="AF_UNIX")
    thread = Thread(target=server.serve_once, daemon=True)
    thread.start()
    try:
        response = control_request(
            socket_path,
            _request("components"),
            authkey=authkey,
            family="AF_UNIX",
        )
        assert response["ok"] is True
        assert response["result"][0]["runner_id"] == "test.control"
        thread.join(timeout=5)
        assert not thread.is_alive()
    finally:
        server.close()
        engine.close()
