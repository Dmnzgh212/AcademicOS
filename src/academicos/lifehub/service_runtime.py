"""Bounded JSON computation service with no storage, effect, or ambient imports."""

from __future__ import annotations

import json
from typing import Any

from academicos.lifehub.wasm import FUEL, MAX_IO_BYTES, MAX_MEMORY_BYTES, MAX_MODULE_BYTES
from academicos.lifehub.wasm import _guest_bytes, _invalid_json

SERVICE_JSON_CONTRACT = "lifehub.service-json@1"


def encode_message(value: Any) -> bytes:
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    if len(raw) > MAX_IO_BYTES:
        raise ValueError("service message exceeds IO limit")
    return raw


def run_json_service(module_bytes: bytes, request: Any) -> Any:
    """Exactly one complete JSON response, released only after successful return."""
    import wasmtime

    incoming = encode_message(request)
    if len(module_bytes) > MAX_MODULE_BYTES:
        raise ValueError("WebAssembly module exceeds size limit")
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    module = wasmtime.Module(engine, module_bytes)
    signature = wasmtime.FuncType([wasmtime.ValType.i32()] * 2, [wasmtime.ValType.i32()])
    for item in module.imports:
        if item.module != "lifehub_service" or item.name not in {"read_request", "write_response"}:
            raise PermissionError(f"unavailable service import: {item.module}.{item.name}")
        if not isinstance(item.type, wasmtime.FuncType) or (
            [str(v) for v in item.type.params] != ["i32", "i32"]
            or [str(v) for v in item.type.results] != ["i32"]
        ):
            raise ValueError("unsupported service import signature")
    store = wasmtime.Store(engine)
    store.set_limits(memory_size=MAX_MEMORY_BYTES, instances=1, memories=1, tables=0)
    store.set_fuel(FUEL)
    linker = wasmtime.Linker(engine)
    responses = []

    def memory_of(caller):
        memory = caller.get("memory")
        if not isinstance(memory, wasmtime.Memory):
            raise ValueError("service must export memory")
        return memory

    def read_request(caller, ptr, capacity):
        memory = memory_of(caller)
        _guest_bytes(memory, caller, ptr, capacity)
        if len(incoming) > capacity:
            return -len(incoming)
        memory.write(caller, incoming, ptr)
        return len(incoming)

    def write_response(caller, ptr, length):
        if responses:
            raise ValueError("service may return only one response")
        raw = _guest_bytes(memory_of(caller), caller, ptr, length)
        output = json.loads(raw.decode("utf-8"), parse_constant=_invalid_json)
        # Reject oversized canonical output as well as oversized guest bytes.
        encode_message(output)
        responses.append(output)
        return length

    linker.define_func(
        "lifehub_service", "read_request", signature, read_request, access_caller=True
    )
    linker.define_func(
        "lifehub_service", "write_response", signature, write_response, access_caller=True
    )
    instance = linker.instantiate(store, module)
    exports = instance.exports(store)
    if not isinstance(exports.get("memory"), wasmtime.Memory):
        raise ValueError("service must export memory")
    run = exports.get("run")
    if not isinstance(run, wasmtime.Func):
        raise ValueError("service must export run")
    if run.type(store).params or [str(v) for v in run.type(store).results] != ["i32"]:
        raise ValueError("service run must have type () -> i32")
    if run(store) != 0:
        raise ValueError("service returned nonzero status")
    if len(responses) != 1:
        raise ValueError("service must return one response")
    return responses[0]
