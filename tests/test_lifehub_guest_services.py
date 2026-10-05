import pytest

wasmtime = pytest.importorskip("wasmtime")
from academicos.lifehub.wasm import WasmRunner  # noqa: E402


def guest(body):
    return wasmtime.wat2wasm(
        """(module
      (import "lifehub" "call_service_json" (func $call
        (param i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "p:echo") (data (i32.const 64) "{}")
      (func (export "run") (result i32) """
        + body
        + "))"
    )


CALL = "(call $call (i32.const 0) (i32.const 6) (i32.const 64) (i32.const 2) (i32.const 128) (i32.const 4096))"


def test_guest_service_count_is_bounded_and_reset():
    calls = []
    runner = WasmRunner(None, service_call=lambda ref, req: calls.append((ref, req)) or req)
    assert runner.run(guest(CALL)) == 2
    assert calls == [("p:echo", {})]
    with pytest.raises(ValueError, match="too many service calls"):
        runner.run(guest("".join(f"(drop {CALL})" for _ in range(5)) + "(i32.const 0)"))
    assert len(calls) == 5
    assert runner.run(guest(CALL)) == 2


def test_guest_invalid_output_buffer_does_not_invoke_provider():
    calls = []
    runner = WasmRunner(None, service_call=lambda ref, req: calls.append(ref) or req)
    with pytest.raises(ValueError, match="out of bounds"):
        runner.run(guest(CALL.replace("(i32.const 128)", "(i32.const 65535)")))
    assert calls == []


def test_guest_service_bridge_is_unavailable_without_bound_host():
    with pytest.raises(PermissionError, match="unavailable"):
        WasmRunner(None).run(guest(CALL))
