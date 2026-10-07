from __future__ import annotations

import os
from multiprocessing import AuthenticationError
from multiprocessing.connection import Client
from threading import Thread

import pytest

from academicos.lifehub.control import CONTROL_API, EngineControlServer, control_request
from academicos.lifehub.engine import LifeHubEngine
from academicos.lifehub.messages import MAX_IO_BYTES, decode_message, encode_message


class _Connection:
    def __init__(self, incoming, *, send_error=None):
        self.incoming = incoming
        self.send_error = send_error
        self.sent = []
        self.closed = False

    def recv_bytes(self, limit):
        assert limit == MAX_IO_BYTES
        if isinstance(self.incoming, Exception):
            raise self.incoming
        return self.incoming

    def send_bytes(self, value):
        if self.send_error:
            raise self.send_error
        assert len(value) <= MAX_IO_BYTES
        self.sent.append(decode_message(value))

    def close(self):
        self.closed = True


class _Listener:
    def __init__(self, items):
        self.items = iter(items)

    def accept(self):
        item = next(self.items)
        if isinstance(item, Exception):
            raise item
        return item


def _server(listener, controller):
    server = object.__new__(EngineControlServer)
    server.listener = listener
    server.controller = controller
    return server


class _Controller:
    def handle(self, request):
        assert request == {"api": CONTROL_API, "op": "ping"}
        return {"api": CONTROL_API, "ok": True, "result": {"status": "ok"}}


@pytest.mark.parametrize("bad", [
    b"{", b"\xff", EOFError(), OSError("bad message length"),
    AuthenticationError("wrong key"), ConnectionResetError(),
])
def test_bad_client_does_not_prevent_next_request(bad):
    first = bad if isinstance(bad, (AuthenticationError, ConnectionResetError)) else _Connection(bad)
    good = _Connection(encode_message({"api": CONTROL_API, "op": "ping"}))
    server = _server(_Listener([first, good]), _Controller())
    server.serve_once()
    server.serve_once()
    assert good.sent[0]["ok"] is True
    assert good.closed
    if isinstance(first, _Connection):
        assert first.closed and not first.sent


def test_disconnected_response_client_is_closed():
    connection = _Connection(
        encode_message({"api": CONTROL_API, "op": "ping"}),
        send_error=BrokenPipeError(),
    )
    _server(_Listener([connection]), _Controller()).serve_once()
    assert connection.closed


def test_listener_failure_propagates_instead_of_spinning():
    server = _server(_Listener([OSError("listener closed")]), _Controller())
    with pytest.raises(OSError, match="listener closed"):
        server.serve_once()


def test_oversized_response_returns_bounded_error():
    class HugeController:
        def handle(self, request):
            return {"result": "x" * MAX_IO_BYTES}

    connection = _Connection(encode_message({"api": CONTROL_API, "op": "ping"}))
    _server(_Listener([connection]), HugeController()).serve_once()
    assert connection.closed
    assert connection.sent[0]["ok"] is False
    assert "bounds" in connection.sent[0]["error"]["message"]


@pytest.mark.skipif(os.name == "nt", reason="AF_PIPE needs separate Windows validation")
def test_real_transport_survives_bad_auth_json_oversize_and_disconnect(tmp_path):
    engine = LifeHubEngine(db_path=tmp_path / "engine.db", plugins_path=tmp_path / "plugins")
    address, key = str(tmp_path / "control.sock"), b"control-resilience-test-key"
    server = EngineControlServer(engine, address, authkey=key, family="AF_UNIX")
    errors = []

    def serve():
        try:
            for _ in range(5):
                server.serve_once()
        except BaseException as exc:
            errors.append(exc)

    thread = Thread(target=serve, daemon=True)
    thread.start()
    try:
        with pytest.raises(AuthenticationError):
            Client(address, authkey=b"wrong-key", family="AF_UNIX")
        for payload in (b"{", b"x" * (MAX_IO_BYTES + 1), None):
            connection = Client(address, authkey=key, family="AF_UNIX")
            try:
                if payload is not None:
                    connection.send_bytes(payload)
            finally:
                connection.close()
        response = control_request(
            address, {"api": CONTROL_API, "op": "ping"}, authkey=key, family="AF_UNIX"
        )
        assert response["ok"] is True
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert not errors
    finally:
        server.close()
        engine.close()
