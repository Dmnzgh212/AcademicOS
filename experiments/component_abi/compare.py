"""Isolated ABI probe; not a LifeHub runner or authorization implementation."""

import json
from importlib.metadata import version
from pathlib import Path

import wasmtime
from wasmtime.component import Component, Linker

from academicos.lifehub.service_runtime import run_json_service


def typed_instance(text, fuel=100_000):
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    component = Component(engine, text)
    store = wasmtime.Store(engine)
    store.set_limits(memory_size=65_536, instances=2, memories=1, tables=0)
    store.set_fuel(fuel)
    instance = Linker(engine).instantiate(store, component)
    return store, instance.get_func(store, "echo")


def main():
    text = Path(__file__).with_name("echo.wat").read_text()
    store, echo = typed_instance(text)
    for value in (0, 7, 2**32 - 1):
        assert echo(store, value) == value
        echo.post_return(store)
    errors = {}
    for value in (-1, 2**32, "7", None):
        try:
            result = echo(store, value)
        except (TypeError, ValueError, OverflowError) as error:
            errors[repr(value)] = type(error).__name__
        else:
            errors[repr(value)] = {"accepted_result": result}
            echo.post_return(store)
    assert errors == {"-1": {"accepted_result": 2**32 - 1},
                      "4294967296": {"accepted_result": 0},
                      "'7'": "TypeError", "None": "TypeError"}
    # Deliberately observe Python bool handling instead of assuming strict u32.
    bool_result = echo(store, True)
    echo.post_return(store)
    assert bool_result == 1
    looping = text.replace("local.get 0", "(loop $spin (br $spin)) local.get 0")
    limited_store, limited_echo = typed_instance(looping, fuel=100)
    try:
        limited_echo(limited_store, 7)
    except wasmtime.WasmtimeError as error:
        assert "fuel" in str(error)
    else:
        raise AssertionError("infinite loop escaped fuel limit")
    # Existing bounded JSON service ABI, unchanged; schema checking is explicit.
    module = wasmtime.wat2wasm('''(module
      (import "lifehub_service" "read_request" (func $read (param i32 i32) (result i32)))
      (import "lifehub_service" "write_response" (func $write (param i32 i32) (result i32)))
      (memory (export "memory") 1)
      (func (export "run") (result i32)
        i32.const 0 i32.const 0 i32.const 65536 call $read call $write drop i32.const 0))''')
    for value in (0, 7, 2**32 - 1):
        assert run_json_service(module, {"value": value}) == {"value": value}
    # JSON framing does not itself define domain types, unlike a component signature.
    assert run_json_service(module, {"value": "7"}) == {"value": "7"}
    print(json.dumps({"status": "PASS", "wasmtime": version("wasmtime"),
                      "invalid_inputs": errors, "python_bool_result": bool_result,
                      "fuel_trap": True, "json_service_echo": True,
                      "generated_bindings": False, "engine_integration": False}))


if __name__ == "__main__":
    main()
