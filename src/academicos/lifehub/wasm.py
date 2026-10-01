"""Core Wasm execution with one explicit, read-only host import."""

from __future__ import annotations

import json

from academicos.lifehub.store import ScopedStore

MAX_MODULE_BYTES = 2 * 1024 * 1024
MAX_IO_BYTES = 64 * 1024
MAX_MEMORY_BYTES = 8 * 1024 * 1024
FUEL = 1_000_000


class WasmRunner:
    """No WASI, ambient filesystem/network, or other imports are linked."""

    def __init__(self, scoped: ScopedStore) -> None:
        self.scoped = scoped

    def run(self, module_bytes: bytes) -> int:
        try:
            import wasmtime
        except ImportError as exc:
            raise RuntimeError("install academicos[wasm] to run WebAssembly plugins") from exc

        if len(module_bytes) > MAX_MODULE_BYTES:
            raise ValueError("WebAssembly module exceeds size limit")
        config = wasmtime.Config()
        config.consume_fuel = True
        engine = wasmtime.Engine(config)
        module = wasmtime.Module(engine, module_bytes)
        signature = wasmtime.FuncType([wasmtime.ValType.i32()] * 4, [wasmtime.ValType.i32()])
        for item in module.imports:
            if item.module != "lifehub" or item.name != "read_json":
                raise PermissionError(f"unavailable WebAssembly import: {item.module}.{item.name}")
            if not isinstance(item.type, wasmtime.FuncType) or (
                [str(value) for value in item.type.params]
                != [str(value) for value in signature.params]
                or [str(value) for value in item.type.results]
                != [str(value) for value in signature.results]
            ):
                raise ValueError("unsupported read_json import signature")

        store = wasmtime.Store(engine)
        store.set_limits(memory_size=MAX_MEMORY_BYTES, instances=1, memories=1, tables=0)
        store.set_fuel(FUEL)
        linker = wasmtime.Linker(engine)

        def read_json(caller, name_ptr: int, name_len: int, out_ptr: int, out_cap: int) -> int:
            memory = caller.get("memory")
            if not isinstance(memory, wasmtime.Memory):
                raise ValueError("plugin must export linear memory")
            name = _guest_bytes(memory, caller, name_ptr, name_len).decode("utf-8")
            if out_cap < 0 or out_cap > MAX_IO_BYTES:
                raise ValueError("invalid WebAssembly output capacity")
            rows = self.scoped.read(name)
            output = json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if len(output) > MAX_IO_BYTES:
                raise ValueError("host response exceeds WebAssembly IO limit")
            _guest_bytes(memory, caller, out_ptr, out_cap)
            if len(output) > out_cap:
                return -len(output)
            memory.write(caller, output, out_ptr)
            return len(output)

        linker.define_func("lifehub", "read_json", signature, read_json, access_caller=True)
        instance = linker.instantiate(store, module)
        exports = instance.exports(store)
        memory = exports.get("memory")
        run = exports.get("run")
        if not isinstance(memory, wasmtime.Memory) or not isinstance(run, wasmtime.Func):
            raise ValueError("plugin must export memory and run")
        run_type = run.type(store)
        if run_type.params or [str(value) for value in run_type.results] != ["i32"]:
            raise ValueError("plugin run must have type () -> i32")
        return run(store)


def _guest_bytes(memory, caller, ptr: int, length: int) -> bytes:
    if ptr < 0 or length < 0 or length > MAX_IO_BYTES or ptr > memory.data_len(caller) - length:
        raise ValueError("WebAssembly memory access out of bounds")
    return bytes(memory.read(caller, ptr, ptr + length))
