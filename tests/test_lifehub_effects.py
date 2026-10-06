from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

wasmtime = pytest.importorskip("wasmtime")

from academicos.lifehub.cli import app  # noqa: E402
from academicos.lifehub.kernel import LifeHub  # noqa: E402
from academicos.lifehub.packages import PackageInstaller  # noqa: E402
from academicos.lifehub.store import LifeStore  # noqa: E402


def _module(*, destination: str = "demo.outbox", trap: bool = False, request_bytes: bytes | None = None) -> bytes:
    request = json.dumps(
        {
            "kind": "test.record",
            "destination": destination,
            "purpose": "Share a chosen summary",
            "payload": {"private": "example"},
        },
        separators=(",", ":"),
    ).encode()
    if request_bytes is not None:
        request = request_bytes
    encoded = "".join(f"\\{byte:02x}" for byte in request)
    tail = "unreachable" if trap else "i32.const 0"
    return wasmtime.wat2wasm(
        f'''(module
          (import "lifehub" "request_effect_json"
            (func $request (param i32 i32) (result i32)))
          (memory (export "memory") 1)
          (data (i32.const 0) "{encoded}")
          (func (export "run") (result i32)
            (drop (call $request (i32.const 0) (i32.const {len(request)})))
            {tail}))'''
    )


def _install(tmp_path: Path, module: bytes) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "installed"
    db = tmp_path / "hub.db"
    manifest = b"""manifest_version = 1
api = "lifehub@1"
id = "demo.effect"
name = "Effect"
version = "1.0.0"
[permissions]
storage_read = []
storage_write = ["tasks"]
network_retrieval = []
localhost_ports = []
[[permissions.effect_request]]
kind = "test.record"
destination = "demo.outbox"
[[contributes]]
id = "sender"
point = "task.worker"
entrypoint = "lifehub.wasm"
[contributes.config]
module = "sender.wasm"
"""
    archive = tmp_path / "effect.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("plugin.toml", manifest)
        output.writestr("sender.wasm", module)
    store = LifeStore(db)
    try:
        installer = PackageInstaller(root, store)
        installer.install(archive, approved_hash=installer.review(archive).content_hash)
    finally:
        store.close()
    return root, db


def test_effect_requires_review_approval_and_separate_dispatch(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _module())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        assert hub.run_wasm("demo.effect:sender") == 0
        request_id = hub.last_effect_ids[0]
        assert hub.effects.get(request_id)["status"] == "pending"
        assert hub.effects.get(request_id)["purpose"] == "Share a chosen summary"
        assert hub.effects.get(request_id)["payload"] == {"private": "example"}
        assert (
            hub.store.conn.execute(
                "SELECT count(*) FROM lifehub_fake_effect_deliveries"
            ).fetchone()[0]
            == 0
        )
        with pytest.raises(ValueError, match="not approved"):
            hub.dispatch_effect(request_id)
        hub.approve_effect(request_id)
        assert hub.effects.get(request_id)["status"] == "approved"
        assert hub.dispatch_effect(request_id) == "succeeded"
        assert (
            hub.store.conn.execute(
                "SELECT count(*) FROM lifehub_fake_effect_deliveries"
            ).fetchone()[0]
            == 1
        )
        with pytest.raises(ValueError, match="already attempted"):
            hub.dispatch_effect(request_id)
        hub.run_wasm("demo.effect:sender")
        assert hub.last_effect_ids == [request_id]
        assert len(hub.effects.list("succeeded")) == 1
    finally:
        hub.close()


def test_unlisted_destination_and_trap_never_enqueue(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _module(destination="secret.attacker"))
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        with pytest.raises(PermissionError, match="was not declared"):
            hub.run_wasm("demo.effect:sender")
        assert hub.effects.list() == []
    finally:
        hub.close()

    root2, db2 = _install(tmp_path / "second", _module(trap=True))
    hub = LifeHub(db_path=db2, plugins_path=root2)
    try:
        with pytest.raises(wasmtime.Trap):
            hub.run_wasm("demo.effect:sender")
        assert hub.effects.list() == []
    finally:
        hub.close()


def test_uncertain_executor_outcome_is_not_retried(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _module())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.run_wasm("demo.effect:sender")
        request_id = hub.last_effect_ids[0]
        hub.approve_effect(request_id)
        calls = []

        def uncertain(request):
            calls.append(request["id"])
            raise RuntimeError("response lost after possible delivery")

        manifest = hub.manifest("demo.effect")
        digest = hub.effects.get(request_id)["package_hash"]
        assert hub.effects.dispatch(request_id, manifest, digest, uncertain) == "unknown"
        assert calls == [request_id]
        with pytest.raises(ValueError, match="already attempted"):
            hub.effects.dispatch(request_id, manifest, digest, uncertain)
        assert calls == [request_id]
        hub.run_wasm("demo.effect:sender")
        assert hub.last_effect_ids == [request_id]
        assert hub.effects.get(request_id)["status"] == "unknown"
    finally:
        hub.close()


def test_interrupted_dispatch_stays_inflight_until_explicit_recovery(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _module())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.run_wasm("demo.effect:sender")
        request_id = hub.last_effect_ids[0]
        hub.approve_effect(request_id)

        def interrupted(_request):
            raise SystemExit("simulated process exit")

        with pytest.raises(SystemExit):
            hub.effects.dispatch(
                request_id,
                hub.manifest("demo.effect"),
                hub.effects.get(request_id)["package_hash"],
                interrupted,
            )
    finally:
        hub.close()
    store = LifeStore(db)
    try:
        from academicos.lifehub.effects import EffectService

        service = EffectService(store)
        assert service.get(request_id)["status"] == "in_flight"
        service.mark_unknown(request_id)
        assert service.get(request_id)["status"] == "unknown"
    finally:
        store.close()


def test_uninstall_invalidates_unattempted_effects(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _module())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.run_wasm("demo.effect:sender")
        request_id = hub.last_effect_ids[0]
        hub.approve_effect(request_id)
    finally:
        hub.close()
    store = LifeStore(db)
    try:
        PackageInstaller(root, store).uninstall("demo.effect")
        from academicos.lifehub.effects import EffectService

        assert EffectService(store).get(request_id)["status"] == "invalidated"
    finally:
        store.close()


def test_cli_effect_review_and_fake_dispatch(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _module())
    cli = CliRunner()
    run = cli.invoke(
        app, ["run-wasm", "demo.effect:sender", "--db", str(db), "--installed", str(root)]
    )
    assert run.exit_code == 0, run.output
    assert "Pending effects: 1" in run.output
    review = cli.invoke(app, ["effects", "--db", str(db)])
    assert review.exit_code == 0, review.output
    assert "demo.outbox" in review.output and '"private": "example"' in review.output
    approve = cli.invoke(app, ["approve-effect", "1", "--db", str(db), "--installed", str(root)])
    assert approve.exit_code == 0, approve.output
    dispatch = cli.invoke(
        app, ["dispatch-fake-effect", "1", "--db", str(db), "--installed", str(root)]
    )
    assert dispatch.exit_code == 0, dispatch.output
    assert "succeeded" in dispatch.output


def test_changed_package_cannot_approve_disclosure(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _module())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.run_wasm("demo.effect:sender")
        request_id = hub.last_effect_ids[0]
        (root / "demo.effect" / "extra.txt").write_text("changed")
        with pytest.raises(PermissionError, match="changed after approval"):
            hub.approve_effect(request_id)
        assert hub.effects.get(request_id)["status"] == "pending"
    finally:
        hub.close()


def test_local_and_effect_requests_persist_atomically(tmp_path: Path, monkeypatch) -> None:
    request = json.dumps(
        {
            "kind": "test.record",
            "destination": "demo.outbox",
            "purpose": "Share a chosen summary",
            "payload": {"private": "example"},
        },
        separators=(",", ":"),
    ).encode()
    encoded = "".join(f"\\{byte:02x}" for byte in request)
    module = wasmtime.wat2wasm(
        f'''(module
          (import "lifehub" "propose_json"
            (func $propose (param i32 i32 i32 i32 i32 i32) (result i32)))
          (import "lifehub" "request_effect_json"
            (func $request (param i32 i32) (result i32)))
          (memory (export "memory") 1)
          (data (i32.const 0) "tasks.today")
          (data (i32.const 32) "plan")
          (data (i32.const 64) "{{}}")
          (data (i32.const 128) "{encoded}")
          (func (export "run") (result i32)
            (drop (call $propose (i32.const 0) (i32.const 11)
              (i32.const 32) (i32.const 4) (i32.const 64) (i32.const 2)))
            (drop (call $request (i32.const 128) (i32.const {len(request)})))
            (i32.const 0)))'''
    )
    root, db = _install(tmp_path, module)
    hub = LifeHub(db_path=db, plugins_path=root)
    try:

        def fail_after_proposal(*_args):
            raise RuntimeError("effect ledger unavailable")

        monkeypatch.setattr(hub.effects, "submit", fail_after_proposal)
        with pytest.raises(RuntimeError, match="ledger unavailable"):
            hub.run_wasm("demo.effect:sender")
        assert hub.proposals.list() == []
        assert hub.effects.list() == []
    finally:
        hub.close()


@pytest.mark.parametrize("change", ["replacement", "tamper", "uninstall"])
def test_execution_discards_staged_work_when_package_changes(tmp_path, monkeypatch, change):
    from academicos.lifehub.wasm import WasmRunner

    root, db = _install(tmp_path, _module())
    hub = LifeHub(db_path=db, plugins_path=root)
    original_run = WasmRunner.run

    def intervening_run(runner, wasm):
        result = original_run(runner, wasm)
        if change == "tamper":
            (root / "demo.effect" / "unexpected.txt").write_text("changed")
        else:
            files = {p.name: p.read_bytes() for p in (root / "demo.effect").iterdir()}
            hub.packages.uninstall("demo.effect")
            if change == "replacement":
                archive = tmp_path / "replacement.zip"
                with zipfile.ZipFile(archive, "w") as output:
                    for name, content in files.items():
                        output.writestr(name, content)
                    output.writestr("new-asset.txt", "approved replacement")
                review = hub.packages.review(archive)
                hub.packages.install(archive, approved_hash=review.content_hash)
        return result

    monkeypatch.setattr(WasmRunner, "run", intervening_run)
    try:
        with pytest.raises(PermissionError, match="changed|revoked"):
            hub.run_wasm("demo.effect:sender")
        assert hub.proposals.list() == []
        assert hub.effects.list() == []
        assert hub.last_proposal_ids == []
        assert hub.last_effect_ids == []
        assert hub.store.latest_records("tasks.today") == []
        assert not hub.store.conn.in_transaction
    finally:
        hub.close()


def test_tampering_after_approval_prevents_effect_dispatch(tmp_path):
    root, db = _install(tmp_path, _module())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.run_wasm("demo.effect:sender")
        request_id = hub.last_effect_ids[0]
        hub.approve_effect(request_id)
        (root / "demo.effect" / "changed.txt").write_text("tampered after approval")
        with pytest.raises(PermissionError, match="changed after approval"):
            hub.dispatch_effect(request_id)
        assert hub.effects.get(request_id)["status"] == "approved"
        assert hub.store.conn.execute(
            "SELECT count(*) FROM lifehub_fake_effect_deliveries"
        ).fetchone()[0] == 0
    finally:
        hub.close()


@pytest.mark.parametrize("payload", [
    b'{"x":1e400}',
    b'{"x":' + b'[' * 65 + b'0' + b']' * 65 + b'}',
    b'{"x":[' + b','.join([b'1e100'] * 10000) + b']}',
], ids=["exponent-overflow", "depth-limit", "canonical-size"])
def test_effect_guest_rejects_invalid_bounded_json(tmp_path, payload):
    request = (b'{"kind":"test.record","destination":"demo.outbox",'
               b'"purpose":"Synthetic check","payload":' + payload + b'}')
    root, db = _install(tmp_path, _module(request_bytes=request))
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        with pytest.raises(ValueError, match="JSON|nesting|IO limit"):
            hub.run_wasm("demo.effect:sender")
        assert hub.effects.list() == []
        assert hub.proposals.list() == []
    finally:
        hub.close()
