from __future__ import annotations

import zipfile

import pytest
import wasmtime

import academicos.lifehub.engine as engine_module
from academicos.lifehub.engine import ExecutionState, LifeHubEngine
from academicos.lifehub.messages import MAX_IO_BYTES
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.store import LifeStore

ECHO = '''(module
 (import "lifehub_service" "read_request" (func $r (param i32 i32) (result i32)))
 (import "lifehub_service" "write_response" (func $w (param i32 i32) (result i32)))
 (memory (export "memory") 1)
 (func (export "run") (result i32) (local $n i32)
  (local.set $n (call $r (i32.const 0) (i32.const 65536)))
  (drop (call $w (i32.const 0) (local.get $n))) (i32.const 0)))'''
CONSUMER = r'''(module
 (import "lifehub" "call_interface_json"
  (func $call (param i32 i32 i32 i32 i32 i32) (result i32)))
 (memory (export "memory") 1)
 (data (i32.const 0) "example.echo@1")
 (data (i32.const 64) "{\22caller\22:\22forged\22}")
 (func (export "run") (result i32)
  (call $call (i32.const 0) (i32.const 14)
   (i32.const 64) (i32.const 19) (i32.const 128) (i32.const 4096))))'''


def _archive(tmp_path, name, declarations, wat):
    archive = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("plugin.toml", f'''
manifest_version = 1
api = "lifehub@1"
id = "{name}"
name = "{name}"
version = "1.0.0"
[[components]]
id = "worker"
runner = "lifehub.wasm"
{declarations}
[components.config]
module = "worker.wasm"
''')
        output.writestr("worker.wasm", wasmtime.wat2wasm(wat))
    return archive


@pytest.fixture
def pair(tmp_path):
    store = LifeStore(tmp_path / "engine.db")
    installed = tmp_path / "installed"
    installer = PackageInstaller(installed, store)
    for name, declaration, wat in (
        ("ipc.consumer", 'requires = ["example.echo@1"]', CONSUMER),
        ("ipc.provider", 'provides = ["example.echo@1"]\ncontract = "lifehub.service-json@1"', ECHO),
    ):
        archive = _archive(tmp_path, name, declaration, wat)
        review = installer.review(archive)
        installer.install(archive, approved_hash=review.content_hash)
    store.close()
    engine = LifeHubEngine(db_path=tmp_path / "engine.db", plugins_path=installed)
    yield engine
    engine.close()


def _grant(engine):
    review = engine.routes.review("ipc.consumer:worker", "example.echo@1", "ipc.provider:worker")
    engine.routes.grant(
        "ipc.consumer:worker", "example.echo@1", "ipc.provider:worker",
        approved_digest=review["approval_digest"],
    )


def test_two_first_class_wasm_components_call_without_shell_or_service_grant(pair):
    with pytest.raises(PermissionError):
        pair.start("ipc.consumer:worker")
    _grant(pair)
    execution = pair.start("ipc.consumer:worker")
    assert execution.state == ExecutionState.COMPLETED
    assert execution.result == 19
    assert all(item["capability"] != "service.activate" for item in pair.kernel.store.grants())
    pair.routes.revoke("ipc.consumer:worker", "example.echo@1")
    with pytest.raises(PermissionError):
        pair.start("ipc.consumer:worker")


def test_payload_cannot_claim_identity_or_select_provider(pair):
    _grant(pair)
    call = pair._interface_call_for(pair.component("ipc.consumer:worker"))
    assert call("example.echo@1", {"caller": "forged", "provider": "other"}) == {
        "caller": "forged", "provider": "other"
    }
    with pytest.raises(PermissionError, match="did not declare"):
        call("ipc.provider:worker", {})
    pair.routes.revoke("ipc.consumer:worker", "example.echo@1")
    with pytest.raises(PermissionError):
        call("example.echo@1", {"capability": "granted"})


@pytest.mark.parametrize("endpoint", ["ipc.consumer", "ipc.provider"])
def test_existing_execution_callback_rejects_uninstall(pair, endpoint):
    _grant(pair)
    call = pair._interface_call_for(pair.component("ipc.consumer:worker"))
    assert call("example.echo@1", {}) == {}
    pair.kernel.packages.uninstall(endpoint)
    with pytest.raises((PermissionError, KeyError)):
        call("example.echo@1", {})


@pytest.mark.parametrize("endpoint", ["ipc.consumer", "ipc.provider"])
def test_existing_execution_callback_rejects_tampering(pair, endpoint):
    _grant(pair)
    call = pair._interface_call_for(pair.component("ipc.consumer:worker"))
    (pair.kernel.packages.root / endpoint / "unexpected.txt").write_text("tampered")
    with pytest.raises((PermissionError, KeyError)):
        call("example.echo@1", {})


@pytest.mark.parametrize("endpoint", ["ipc.consumer", "ipc.provider"])
def test_new_approved_route_cannot_refresh_old_execution_snapshot(pair, endpoint, tmp_path):
    _grant(pair)
    call = pair._interface_call_for(pair.component("ipc.consumer:worker"))
    root = pair.kernel.packages.root / endpoint
    archive = tmp_path / "replacement.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for file in root.iterdir():
            output.writestr(file.name, file.read_bytes())
        output.writestr("new-resource.txt", "new approved snapshot")
    installer = pair.kernel.packages
    installer.uninstall(endpoint)
    review = installer.review(archive)
    installer.install(archive, approved_hash=review.content_hash)
    _grant(pair)
    with pytest.raises(PermissionError, match="execution snapshot changed"):
        call("example.echo@1", {})
    assert pair.start("ipc.consumer:worker").result == 19


def test_revocation_during_provider_execution_discards_response(pair, monkeypatch):
    _grant(pair)
    call = pair._interface_call_for(pair.component("ipc.consumer:worker"))
    actual = engine_module.run_json_service

    def revoke(module, request):
        output = actual(module, request)
        pair.routes.revoke("ipc.consumer:worker", "example.echo@1")
        return output

    monkeypatch.setattr(engine_module, "run_json_service", revoke)
    with pytest.raises(PermissionError):
        call("example.echo@1", {})


@pytest.mark.parametrize("payload", [{"x": float("nan")}, {"x": "a" * MAX_IO_BYTES}])
def test_interface_messages_keep_existing_json_bounds(pair, payload):
    _grant(pair)
    call = pair._interface_call_for(pair.component("ipc.consumer:worker"))
    with pytest.raises(ValueError):
        call("example.echo@1", payload)
