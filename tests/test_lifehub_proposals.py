from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

wasmtime = pytest.importorskip("wasmtime")

from academicos.lifehub.kernel import LifeHub  # noqa: E402
from academicos.lifehub.cli import app  # noqa: E402
from academicos.lifehub.packages import PackageInstaller  # noqa: E402
from academicos.lifehub.proposals import ProposalService  # noqa: E402
from academicos.lifehub.store import LifeStore  # noqa: E402


def _wasm(namespace: str = "tasks.today", *, trap: bool = False) -> bytes:
    payload = b'{"title":"Study"}'
    encoded = "".join(f"\\{byte:02x}" for byte in payload)
    tail = "unreachable" if trap else "i32.const 0"
    return wasmtime.wat2wasm(
        f'''(module
          (import "lifehub" "propose_json"
            (func $propose (param i32 i32 i32 i32 i32 i32) (result i32)))
          (memory (export "memory") 1)
          (data (i32.const 0) "{namespace}")
          (data (i32.const 64) "plan")
          (data (i32.const 128) "{encoded}")
          (func (export "run") (result i32)
            (drop (call $propose
              (i32.const 0) (i32.const {len(namespace)})
              (i32.const 64) (i32.const 4)
              (i32.const 128) (i32.const {len(payload)})))
            {tail}))'''
    )


def _install(tmp_path: Path, module: bytes) -> tuple[Path, Path]:
    root = tmp_path / "installed"
    db = tmp_path / "hub.db"
    manifest = b"""manifest_version = 1
api = "lifehub@1"
id = "demo.planner"
name = "Planner"
version = "1.0.0"
[permissions]
storage_read = []
storage_write = ["tasks"]
network_retrieval = []
localhost_ports = []
[[contributes]]
id = "plan"
point = "task.worker"
entrypoint = "lifehub.wasm"
[contributes.config]
module = "plan.wasm"
"""
    archive = tmp_path / "plugin.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("plugin.toml", manifest)
        output.writestr("plan.wasm", module)
    store = LifeStore(db)
    try:
        installer = PackageInstaller(root, store)
        installer.install(archive, approved_hash=installer.review(archive).content_hash)
    finally:
        store.close()
    return root, db


def test_proposal_requires_separate_person_commit_and_survives_restart(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _wasm())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        assert hub.run_wasm("demo.planner:plan") == 0
        proposal_id = hub.last_proposal_ids[0]
        assert hub.store.latest_records("tasks.today") == []
        pending = hub.proposals.get(proposal_id)
        assert pending["payload"] == {"title": "Study"}
        assert pending["base_record_id"] is None
        assert hub.run_wasm("demo.planner:plan") == 0
        assert hub.last_proposal_ids == [proposal_id]
    finally:
        hub.close()
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        assert hub.approve_proposal(proposal_id) == "committed"
        assert hub.store.latest_records("tasks.today")[0]["payload"] == {"title": "Study"}
        assert hub.proposals.get(proposal_id)["committed_record_id"] is not None
        with pytest.raises(ValueError, match="no longer pending"):
            hub.approve_proposal(proposal_id)
        assert len(hub.store.latest_records("tasks.today")) == 1
    finally:
        hub.close()


def test_trap_discards_staged_proposal(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _wasm(trap=True))
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        with pytest.raises(wasmtime.Trap):
            hub.run_wasm("demo.planner:plan")
        assert hub.proposals.list() == []
        assert hub.store.latest_records("tasks.today") == []
    finally:
        hub.close()


def test_undeclared_write_is_denied_before_proposal(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _wasm("private.today"))
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        with pytest.raises(PermissionError, match="cannot write"):
            hub.run_wasm("demo.planner:plan")
        assert hub.proposals.list() == []
    finally:
        hub.close()


def test_stale_target_cannot_commit(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _wasm())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.run_wasm("demo.planner:plan")
        proposal_id = hub.last_proposal_ids[0]
        hub.store.append_record(
            plugin_id="external",
            namespace="tasks.today",
            record_key="plan",
            payload={"title": "Changed"},
        )
        assert hub.approve_proposal(proposal_id) == "stale"
        assert hub.proposals.get(proposal_id)["status"] == "stale"
        assert hub.store.latest_records("tasks.today")[0]["payload"] == {"title": "Changed"}
    finally:
        hub.close()


def test_reject_and_uninstall_invalidate_without_mutating_records(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _wasm())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.run_wasm("demo.planner:plan")
        first = hub.last_proposal_ids[0]
        hub.proposals.reject(first)
        hub.run_wasm("demo.planner:plan")
        second = hub.last_proposal_ids[0]
        assert second != first
        assert hub.proposals.get(first)["status"] == "rejected"
        assert hub.store.latest_records("tasks.today") == []
    finally:
        hub.close()
    store = LifeStore(db)
    try:
        PackageInstaller(root, store).uninstall("demo.planner")
        assert ProposalService(store).get(second)["status"] == "invalidated"
    finally:
        store.close()


def test_changed_package_cannot_approve_pending_proposal(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _wasm())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.run_wasm("demo.planner:plan")
        proposal_id = hub.last_proposal_ids[0]
        (root / "demo.planner" / "extra.txt").write_text("changed")
        with pytest.raises(PermissionError, match="changed after approval"):
            hub.approve_proposal(proposal_id)
        assert hub.store.latest_records("tasks.today") == []
    finally:
        hub.close()


def test_identical_existing_record_is_reviewed_noop(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _wasm())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.store.append_record(
            plugin_id="demo.planner",
            namespace="tasks.today",
            record_key="plan",
            payload={"title": "Study"},
        )
        hub.run_wasm("demo.planner:plan")
        proposal_id = hub.last_proposal_ids[0]
        assert hub.approve_proposal(proposal_id) == "already_recorded"
        assert len(hub.store.latest_records("tasks.today")) == 1
    finally:
        hub.close()


def test_cli_review_and_approve_round_trip(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _wasm())
    cli = CliRunner()
    run = cli.invoke(
        app, ["run-wasm", "demo.planner:plan", "--db", str(db), "--installed", str(root)]
    )
    assert run.exit_code == 0, run.output
    assert "Pending proposals: 1" in run.output
    review = cli.invoke(app, ["proposals", "--db", str(db)])
    assert review.exit_code == 0, review.output
    assert '"title": "Study"' in review.output
    assert "tasks.today/plan" in review.output
    approval = cli.invoke(app, ["approve-proposal", "1", "--db", str(db), "--installed", str(root)])
    assert approval.exit_code == 0, approval.output
    assert "committed" in approval.output
    store = LifeStore(db)
    try:
        assert store.latest_records("tasks.today")[0]["payload"] == {"title": "Study"}
    finally:
        store.close()


@pytest.mark.parametrize("change", ["replacement", "tamper", "uninstall"])
def test_execution_discards_staged_work_when_package_changes(tmp_path, monkeypatch, change):
    from academicos.lifehub.wasm import WasmRunner

    root, db = _install(tmp_path, _wasm())
    hub = LifeHub(db_path=db, plugins_path=root)
    original_run = WasmRunner.run

    def intervening_run(runner, wasm):
        result = original_run(runner, wasm)
        if change == "tamper":
            (root / "demo.planner" / "unexpected.txt").write_text("changed")
        else:
            files = {p.name: p.read_bytes() for p in (root / "demo.planner").iterdir()}
            hub.packages.uninstall("demo.planner")
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
            hub.run_wasm("demo.planner:plan")
        assert hub.proposals.list() == []
        assert hub.effects.list() == []
        assert hub.last_proposal_ids == []
        assert hub.last_effect_ids == []
        assert hub.store.latest_records("tasks.today") == []
        assert not hub.store.conn.in_transaction
    finally:
        hub.close()
