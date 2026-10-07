"""Private host subprocess for bounded persistent core-Wasm; no guest WASI."""

from __future__ import annotations

import base64
import os
import queue
import sys
import threading

from academicos.lifehub.messages import decode_message, encode_message, MAX_IO_BYTES
from academicos.lifehub.wasm import FUEL, MAX_MEMORY_BYTES, MAX_MODULE_BYTES, _guest_bytes


def main():
    import wasmtime

    initial = sys.stdin.buffer.readline(MAX_MODULE_BYTES * 2 + 1024)
    # Only the trusted parent writes this bootstrap frame; it contains no authkey.
    import json
    module_bytes = base64.b64decode(json.loads(initial)["module"], validate=True)
    if len(module_bytes) > MAX_MODULE_BYTES:
        raise ValueError("background module exceeds size limit")
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    module = wasmtime.Module(engine, module_bytes)
    signature = wasmtime.FuncType([wasmtime.ValType.i32()] * 2, [wasmtime.ValType.i32()])
    for item in module.imports:
        if (item.module != "lifehub_service"
                or item.name not in {"read_request", "write_response"}
                or not isinstance(item.type, wasmtime.FuncType)
                or [str(v) for v in item.type.params] != ["i32", "i32"]
                or [str(v) for v in item.type.results] != ["i32"]):
            raise PermissionError("unavailable background import")
    store = wasmtime.Store(engine)
    store.set_limits(memory_size=MAX_MEMORY_BYTES, instances=1, memories=1, tables=0)
    store.set_fuel(FUEL)
    linker = wasmtime.Linker(engine)
    incoming = b"{}"
    responses = []

    def read(caller, ptr, capacity):
        memory = caller.get("memory")
        _guest_bytes(memory, caller, ptr, capacity)
        if len(incoming) > capacity:
            return -len(incoming)
        memory.write(caller, incoming, ptr)
        return len(incoming)

    def write(caller, ptr, length):
        if responses:
            raise ValueError("duplicate response")
        responses.append(decode_message(_guest_bytes(caller.get("memory"), caller, ptr, length)))
        return length

    linker.define_func("lifehub_service", "read_request", signature, read, access_caller=True)
    linker.define_func("lifehub_service", "write_response", signature, write, access_caller=True)
    instance = linker.instantiate(store, module)
    exports = instance.exports(store)
    if not isinstance(exports.get("memory"), wasmtime.Memory):
        raise ValueError("background guest must export memory")
    for name in ("ready", "tick", "run"):
        function = exports.get(name)
        if (not isinstance(function, wasmtime.Func) or function.type(store).params
                or [str(v) for v in function.type(store).results] != ["i32"]):
            raise ValueError(f"background {name} must have signature () -> i32")
    if exports["ready"](store) != 1:
        raise ValueError("guest did not signal ready")

    def emit(value):
        sys.stdout.buffer.write(encode_message(value) + b"\n")
        sys.stdout.buffer.flush()

    commands = queue.Queue(maxsize=1)

    def receive():
        while True:
            raw = sys.stdin.buffer.readline(MAX_IO_BYTES + 2)
            if not raw or len(raw) > MAX_IO_BYTES + 1 or not raw.endswith(b"\n"):
                commands.put(None)
                return
            commands.put(decode_message(raw[:-1]))

    threading.Thread(target=receive, daemon=True).start()
    emit({"ready": True})
    while True:
        try:
            command = commands.get(timeout=0.1)
        except queue.Empty:
            store.set_fuel(FUEL)
            if exports["tick"](store) != 0:
                raise ValueError("background tick failed")
            continue
        if command is None:  # Parent pipe closed: no orphan guest continues working.
            return
        incoming = encode_message(command)
        responses.clear()
        store.set_fuel(FUEL)
        if exports["run"](store) != 0 or len(responses) != 1:
            raise ValueError("background service must return one response")
        emit(responses[0])


if __name__ == "__main__":
    # This dedicated child has no persistent host writes to finalize. Avoid
    # CPython shutdown waiting/aborting on a daemon reader holding stdin's lock.
    # Protocol responses are flushed by emit; EOF/trap both close all OS handles.
    try:
        main()
    except BaseException:
        os._exit(1)
    os._exit(0)
