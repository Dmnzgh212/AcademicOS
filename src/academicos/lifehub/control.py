"""Local non-HTTP control plane for the persistent LifeHub Engine."""

from __future__ import annotations

from dataclasses import asdict
from multiprocessing.connection import Client, Listener
from typing import Any

from academicos.lifehub.engine import LifeHubEngine
from academicos.lifehub.messages import MAX_IO_BYTES, decode_message, encode_message

CONTROL_API = "lifehub.engine-control@1"


class EngineController:
    """Versioned local control protocol over a shell-independent engine."""

    def __init__(self, engine: LifeHubEngine) -> None:
        self.engine = engine

    def handle(self, request: Any) -> dict[str, Any]:
        try:
            result = self._dispatch(request)
            return {"api": CONTROL_API, "ok": True, "result": result}
        except (KeyError, LookupError, PermissionError, TypeError, ValueError) as exc:
            return {
                "api": CONTROL_API,
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }

    def _dispatch(self, request: Any) -> Any:
        if not isinstance(request, dict):
            raise TypeError("engine control request must be a JSON object")
        if request.get("api") != CONTROL_API:
            raise ValueError("unsupported engine control API")
        op = request.get("op")
        if not isinstance(op, str):
            raise ValueError("engine control request needs an op")

        if op == "ping":
            _require_keys(request, {"api", "op"})
            return {"status": "ok"}

        if op == "components":
            _require_keys(request, {"api", "op"})
            return [
                {
                    "ref": item.ref,
                    "plugin_id": item.plugin_id,
                    "point": item.point,
                    "runner_id": item.runner_id,
                    "contract": item.contract,
                    "provides": list(item.provides),
                    "requires": list(item.requires),
                    "activation": list(item.activation),
                    "config": item.config,
                }
                for item in self.engine.components()
            ]

        if op == "executions":
            _require_keys(request, {"api", "op", "limit"}, optional={"limit"})
            limit = request.get("limit", 100)
            return [_execution_json(item) for item in self.engine.executions(limit=limit)]

        if op == "start":
            _require_keys(request, {"api", "op", "ref"})
            ref = request["ref"]
            if not isinstance(ref, str) or not ref:
                raise ValueError("start requires a nonempty component ref")
            return _execution_json(self.engine.start(ref))

        if op == "stop":
            _require_keys(request, {"api", "op", "execution_id"})
            execution_id = request["execution_id"]
            if not isinstance(execution_id, str) or not execution_id:
                raise ValueError("stop requires a nonempty execution id")
            return _execution_json(self.engine.stop(execution_id))

        raise ValueError(f"unsupported engine control operation: {op}")


class EngineControlServer:
    """Authenticated local IPC server.

    Transport uses Python's local multiprocessing connection layer (AF_UNIX on
    Unix-like systems or AF_PIPE on Windows when selected by the caller). Payloads
    are bounded JSON bytes; pickle send/recv APIs are deliberately not used.
    """

    def __init__(
        self,
        engine: LifeHubEngine,
        address,
        *,
        authkey: bytes,
        family: str | None = None,
    ) -> None:
        if not authkey:
            raise ValueError("engine control authkey cannot be empty")
        self.controller = EngineController(engine)
        self.listener = Listener(address=address, family=family, authkey=authkey)

    def serve_once(self) -> None:
        connection = self.listener.accept()
        try:
            raw = connection.recv_bytes(MAX_IO_BYTES)
            request = decode_message(raw)
            response = self.controller.handle(request)
            connection.send_bytes(encode_message(response))
        finally:
            connection.close()

    def serve_forever(self) -> None:
        while True:
            self.serve_once()

    def close(self) -> None:
        self.listener.close()


def control_request(
    address,
    request: dict[str, Any],
    *,
    authkey: bytes,
    family: str | None = None,
) -> dict[str, Any]:
    """Send one bounded JSON request to a local engine server."""
    if not authkey:
        raise ValueError("engine control authkey cannot be empty")
    connection = Client(address=address, family=family, authkey=authkey)
    try:
        connection.send_bytes(encode_message(request))
        response = decode_message(connection.recv_bytes(MAX_IO_BYTES))
    finally:
        connection.close()
    if not isinstance(response, dict):
        raise ValueError("engine control response must be a JSON object")
    return response


def _execution_json(view) -> dict[str, Any]:
    data = asdict(view)
    # Runner results are process/runtime-specific and may not be JSON values.
    # The control plane exposes lifecycle state, not arbitrary runner objects.
    data.pop("result", None)
    data["state"] = str(view.state)
    return data


def _require_keys(
    request: dict[str, Any],
    allowed: set[str],
    *,
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    required = allowed - optional
    missing = required - set(request)
    extra = set(request) - allowed
    if missing or extra:
        raise ValueError(
            f"invalid engine control fields; missing={sorted(missing)}, extra={sorted(extra)}"
        )
