"""Core Wasm execution with one explicit, read-only host import."""

from __future__ import annotations

import json

from academicos.lifehub.effects import EffectRequest, EffectService
from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.proposals import ProposedChange
from academicos.lifehub.store import ScopedStore

MAX_MODULE_BYTES = 2 * 1024 * 1024
MAX_IO_BYTES = 64 * 1024
MAX_MEMORY_BYTES = 8 * 1024 * 1024
FUEL = 1_000_000
MAX_PROPOSALS = 8
MAX_EFFECT_REQUESTS = 4


class WasmRunner:
    """No WASI, ambient filesystem/network, or other imports are linked."""

    def __init__(
        self,
        scoped: ScopedStore,
        manifest: PluginManifest | None = None,
        effects: EffectService | None = None,
    ) -> None:
        self.scoped = scoped
        self.manifest = manifest
        self.effect_service = effects
        self.proposals: list[ProposedChange] = []
        self.effect_requests: list[EffectRequest] = []

    def run(self, module_bytes: bytes) -> int:
        self.proposals = []
        self.effect_requests = []
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
        read_signature = wasmtime.FuncType([wasmtime.ValType.i32()] * 4, [wasmtime.ValType.i32()])
        propose_signature = wasmtime.FuncType(
            [wasmtime.ValType.i32()] * 6, [wasmtime.ValType.i32()]
        )
        effect_signature = wasmtime.FuncType([wasmtime.ValType.i32()] * 2, [wasmtime.ValType.i32()])
        signatures = {
            "read_json": read_signature,
            "propose_json": propose_signature,
            "request_effect_json": effect_signature,
        }
        for item in module.imports:
            if item.module != "lifehub" or item.name not in signatures:
                raise PermissionError(f"unavailable WebAssembly import: {item.module}.{item.name}")
            signature = signatures[item.name]
            if not isinstance(item.type, wasmtime.FuncType) or (
                [str(value) for value in item.type.params]
                != [str(value) for value in signature.params]
                or [str(value) for value in item.type.results]
                != [str(value) for value in signature.results]
            ):
                raise ValueError(f"unsupported {item.name} import signature")

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

        def propose_json(
            caller,
            name_ptr: int,
            name_len: int,
            key_ptr: int,
            key_len: int,
            payload_ptr: int,
            payload_len: int,
        ) -> int:
            memory = caller.get("memory")
            if not isinstance(memory, wasmtime.Memory):
                raise ValueError("plugin must export linear memory")
            if len(self.proposals) >= MAX_PROPOSALS:
                raise ValueError("too many proposals in one run")
            namespace = _guest_bytes(memory, caller, name_ptr, name_len).decode("utf-8")
            record_key = _guest_bytes(memory, caller, key_ptr, key_len).decode("utf-8")
            raw = _guest_bytes(memory, caller, payload_ptr, payload_len).decode("utf-8")
            if not namespace or not record_key:
                raise ValueError("proposal needs namespace and record key")
            payload = json.loads(raw, parse_constant=lambda value: _invalid_json(value))
            if not isinstance(payload, dict):
                raise ValueError("proposal payload must be a JSON object")
            base = self.scoped.write_base(namespace, record_key)
            self.proposals.append(ProposedChange(namespace, record_key, payload, base))
            return len(self.proposals)

        def request_effect_json(caller, ptr: int, length: int) -> int:
            memory = caller.get("memory")
            if not isinstance(memory, wasmtime.Memory):
                raise ValueError("plugin must export linear memory")
            if len(self.effect_requests) >= MAX_EFFECT_REQUESTS:
                raise ValueError("too many effect requests in one run")
            raw = _guest_bytes(memory, caller, ptr, length).decode("utf-8")
            request = json.loads(raw, parse_constant=lambda value: _invalid_json(value))
            if not isinstance(request, dict) or set(request) != {
                "kind",
                "destination",
                "purpose",
                "payload",
            }:
                raise ValueError("effect request needs kind, destination, purpose and payload")
            kind, destination, purpose, payload = (
                request["kind"],
                request["destination"],
                request["purpose"],
                request["payload"],
            )
            if (
                not isinstance(kind, str)
                or not isinstance(destination, str)
                or not isinstance(purpose, str)
                or not purpose.strip()
                or len(purpose) > 256
                or not isinstance(payload, dict)
            ):
                raise ValueError("invalid effect request fields")
            if self.manifest is None or self.effect_service is None:
                raise PermissionError("effect requests are unavailable")
            self.effect_service.assert_requestable(self.manifest, kind, destination)
            self.effect_requests.append(EffectRequest(kind, destination, purpose, payload))
            return len(self.effect_requests)

        linker.define_func("lifehub", "read_json", read_signature, read_json, access_caller=True)
        linker.define_func(
            "lifehub", "propose_json", propose_signature, propose_json, access_caller=True
        )
        linker.define_func(
            "lifehub",
            "request_effect_json",
            effect_signature,
            request_effect_json,
            access_caller=True,
        )
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


def _invalid_json(value: str) -> None:
    raise ValueError(f"nonfinite JSON number is not supported: {value}")
