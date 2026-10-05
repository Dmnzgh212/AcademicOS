import pytest

wasmtime = pytest.importorskip("wasmtime")
from academicos.lifehub.service_runtime import run_json_service  # noqa: E402


def module(body):
    return wasmtime.wat2wasm(
        """(module
      (import "lifehub_service" "read_request" (func $read (param i32 i32) (result i32)))
      (import "lifehub_service" "write_response" (func $write (param i32 i32) (result i32)))
      (memory (export "memory") 1)
      (func (export "run") (result i32) (local $n i32)
      """
        + body
        + "))"
    )


def test_json_roundtrip_is_detached():
    echo = module("""(local.set $n (call $read (i32.const 0) (i32.const 4096)))
      (drop (call $write (i32.const 0) (local.get $n))) (i32.const 0)""")
    request = {"text": "中文", "items": [1, True, None]}
    output = run_json_service(echo, request)
    assert output == request
    output["items"].append(2)
    assert len(request["items"]) == 3
    with pytest.raises(ValueError, match="IO limit"):
        run_json_service(echo, {"x": "x" * 65536})
    with pytest.raises(ValueError):
        run_json_service(echo, float("nan"))


@pytest.mark.parametrize(
    "body, error",
    [
        ("(drop (call $read (i32.const 65530) (i32.const 20))) (i32.const 0)", "out of bounds"),
        ("(i32.const 0)", "one response"),
        ("(drop (call $write (i32.const 0) (i32.const 1))) (i32.const 0)", None),
        (
            """(local.set $n (call $read (i32.const 0) (i32.const 4096)))
      (drop (call $write (i32.const 0) (local.get $n)))
      (drop (call $write (i32.const 0) (local.get $n))) (i32.const 0)""",
            "only one",
        ),
        (
            """(local.set $n (call $read (i32.const 0) (i32.const 4096)))
      (drop (call $write (i32.const 0) (local.get $n))) (i32.const 1)""",
            "nonzero",
        ),
    ],
)
def test_invalid_response_is_not_released(body, error):
    with pytest.raises(ValueError, match=error):
        run_json_service(module(body), {})


def test_response_before_trap_is_discarded():
    with pytest.raises(wasmtime.Trap):
        run_json_service(
            module("""(local.set $n (call $read (i32.const 0) (i32.const 4096)))
          (drop (call $write (i32.const 0) (local.get $n))) unreachable"""),
            {},
        )


def test_storage_import_is_unavailable():
    wasm = wasmtime.wat2wasm("""(module
      (import "lifehub" "read_json" (func (param i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (func (export "run") (result i32) (i32.const 0)))""")
    with pytest.raises(PermissionError, match="unavailable service import"):
        run_json_service(wasm, {})


def test_installed_json_service_requires_exact_grant(tmp_path):
    import zipfile
    from academicos.lifehub.kernel import LifeHub
    from academicos.lifehub.packages import PackageInstaller
    from academicos.lifehub.store import LifeStore

    db, root = tmp_path / "hub.db", tmp_path / "installed"
    store = LifeStore(db)
    try:
        installer = PackageInstaller(root, store)
        for name in ("caller", "echo"):
            archive = tmp_path / f"{name}.zip"
            manifest = f'''manifest_version = 1
api = "lifehub@1"
id = "sample.{name}"
name = "{name}"
version = "1.0.0"
[permissions]
'''
            if name == "caller":
                manifest += 'service_call = ["sample.echo:echo"]\n'
            else:
                manifest += """[[contributes]]
id = "echo"
point = "lifehub.service"
entrypoint = "lifehub.wasm"
contract = "lifehub.service-json@1"
[contributes.config]
module = "echo.wasm"
"""
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("plugin.toml", manifest)
                output.writestr(
                    "echo.wasm",
                    module("""
                  (local.set $n (call $read (i32.const 0) (i32.const 4096)))
                  (drop (call $write (i32.const 0) (local.get $n))) (i32.const 0)"""),
                )
            installer.install(archive, approved_hash=installer.review(archive).content_hash)
    finally:
        store.close()
    hub = LifeHub(db_path=db, plugins_path=root)
    args = ("sample.caller", "sample.echo:echo", "lifehub.service-json@1")
    try:
        with pytest.raises(PermissionError, match="not granted"):
            hub.call_service(args[0], args[1], {"message": "hello"})
        review = hub.review_service(*args)
        hub.grant_service(*args, approved_digest=review["approval_digest"])
        assert hub.call_service(args[0], args[1], {"message": "hello"}) == {"message": "hello"}
        with pytest.raises(ValueError, match="activation requires"):
            hub.activate_service(*args)
        hub.revoke_service(*args)
        with pytest.raises(PermissionError, match="not granted"):
            hub.call_service(args[0], args[1], {})
    finally:
        hub.close()


def test_service_requires_exported_memory_even_without_host_imports():
    wasm = wasmtime.wat2wasm('(module (func (export "run") (result i32) (i32.const 0)))')
    with pytest.raises(ValueError, match="must export memory"):
        run_json_service(wasm, {})


def test_service_fuel_exhaustion_terminates_guest():
    wasm = wasmtime.wat2wasm("""(module (memory (export "memory") 1)
      (func (export "run") (result i32) (loop $spin (br $spin)) (i32.const 0)))""")
    with pytest.raises(wasmtime.Trap, match="fuel"):
        run_json_service(wasm, {})
