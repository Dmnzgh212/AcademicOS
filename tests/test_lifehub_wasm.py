from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime")

from academicos.lifehub.kernel import LifeHub  # noqa: E402
from academicos.lifehub.packages import PackageInstaller  # noqa: E402
from academicos.lifehub.store import LifeStore  # noqa: E402


def _module(namespace: str = "public.today") -> bytes:
    return wasmtime.wat2wasm(
        f'''(module
          (import "lifehub" "read_json" (func $read (param i32 i32 i32 i32) (result i32)))
          (memory (export "memory") 1)
          (data (i32.const 0) "{namespace}")
          (func (export "run") (result i32)
            (call $read (i32.const 0) (i32.const {len(namespace)})
                        (i32.const 128) (i32.const 4096)))
        )'''
    )


def _install(tmp_path: Path, module: bytes) -> tuple[Path, Path]:
    root = tmp_path / "installed"
    db = tmp_path / "lifehub.db"
    manifest = b"""manifest_version = 1
api = "lifehub@1"
id = "demo.isolated"
name = "Isolated"
version = "1.0.0"
[permissions]
storage_read = ["public"]
storage_write = []
network_retrieval = []
localhost_ports = []
[[contributes]]
id = "worker"
point = "task.worker"
entrypoint = "lifehub.wasm"
[contributes.config]
module = "worker.wasm"
"""
    archive = tmp_path / "plugin.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("plugin.toml", manifest)
        output.writestr("worker.wasm", module)
    store = LifeStore(db)
    try:
        installer = PackageInstaller(root, store)
        installer.install(archive, approved_hash=installer.review(archive).content_hash)
    finally:
        store.close()
    return root, db


def test_approved_wasm_reads_only_after_grant(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _module())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.store.append_record(
            plugin_id="producer", namespace="public.today", record_key="one", payload={"x": 1}
        )
        with pytest.raises(PermissionError, match="cannot read"):
            hub.run_wasm("demo.isolated:worker")
        hub.grant_read("demo.isolated", "public")
        assert hub.run_wasm("demo.isolated:worker") > 0
        hub.revoke_read("demo.isolated", "public")
        with pytest.raises(PermissionError, match="cannot read"):
            hub.run_wasm("demo.isolated:worker")
        (root / "demo.isolated" / "worker.wasm").write_bytes(_module("private.today"))
        with pytest.raises(PermissionError, match="changed after approval"):
            hub.run_wasm("demo.isolated:worker")
    finally:
        hub.close()


def test_wasm_cannot_read_undeclared_namespace(tmp_path: Path) -> None:
    root, db = _install(tmp_path, _module("private.today"))
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.grant_read("demo.isolated", "public")
        with pytest.raises(PermissionError, match="cannot read"):
            hub.run_wasm("demo.isolated:worker")
    finally:
        hub.close()


@pytest.mark.parametrize("module_name", ["wasi_snapshot_preview1", "network", "filesystem"])
def test_wasm_ambient_imports_rejected(tmp_path: Path, module_name: str) -> None:
    module = wasmtime.wat2wasm(
        f'''(module (import "{module_name}" "open" (func))
            (memory (export "memory") 1)
            (func (export "run") (result i32) (i32.const 0)))'''
    )
    root, db = _install(tmp_path, module)
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        with pytest.raises(PermissionError, match="unavailable WebAssembly import"):
            hub.run_wasm("demo.isolated:worker")
    finally:
        hub.close()


def test_wasm_infinite_loop_exhausts_fuel(tmp_path: Path) -> None:
    module = wasmtime.wat2wasm(
        """(module (memory (export "memory") 1)
          (func (export "run") (result i32)
            (loop $again (br $again)) (i32.const 0)))"""
    )
    root, db = _install(tmp_path, module)
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        with pytest.raises(wasmtime.Trap, match="fuel"):
            hub.run_wasm("demo.isolated:worker")
    finally:
        hub.close()


def test_wasm_memory_growth_is_limited(tmp_path: Path) -> None:
    module = wasmtime.wat2wasm(
        """(module (memory (export "memory") 1)
          (func (export "run") (result i32)
            (memory.grow (i32.const 1000))))"""
    )
    root, db = _install(tmp_path, module)
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        assert hub.run_wasm("demo.isolated:worker") == -1
    finally:
        hub.close()


def test_wasm_record_response_rejects_nonfinite_stored_payload(tmp_path):
    root, db = _install(tmp_path, _module())
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.store.append_record(plugin_id="producer", namespace="public.today",
                                record_key="legacy", payload={"x": float("inf")})
        hub.grant_read("demo.isolated", "public")
        with pytest.raises(ValueError, match="JSON"):
            hub.run_wasm("demo.isolated:worker")
        assert hub.last_proposal_ids == []
        assert hub.last_effect_ids == []
    finally:
        hub.close()
