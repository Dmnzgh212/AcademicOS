"""Conventional core-Wasm host baseline for the same advisor-email request."""

from __future__ import annotations

import json
import zipfile
from contextlib import closing

import pytest

wasmtime = pytest.importorskip("wasmtime")

from academicos.lifehub.kernel import LifeHub  # noqa: E402
from academicos.lifehub.packages import PackageInstaller  # noqa: E402
from academicos.lifehub.store import LifeStore  # noqa: E402


DESTINATION = "advisor@example.org"
PURPOSE = "Send reviewed academic draft"
PAYLOAD = {"context": {"course": "BIO101"}, "draft": "Please meet"}


def _module(destination=DESTINATION):
    request = json.dumps({
        "kind": "test.record", "destination": destination,
        "purpose": PURPOSE, "payload": PAYLOAD,
    }, separators=(",", ":")).encode()
    encoded = "".join(f"\\{byte:02x}" for byte in request)
    return wasmtime.wat2wasm(
        f'''(module
          (import "lifehub" "request_effect_json"
            (func $request (param i32 i32) (result i32)))
          (memory (export "memory") 1)
          (data (i32.const 0) "{encoded}")
          (func (export "run") (result i32)
            (drop (call $request (i32.const 0) (i32.const {len(request)})))
            i32.const 0))'''
    )


def _install(tmp_path, module):
    root, db = tmp_path / "installed", tmp_path / "hub.db"
    manifest = f'''manifest_version = 1
api = "lifehub@1"
id = "baseline.email"
name = "Email baseline"
version = "1.0.0"
[permissions]
storage_read = []
storage_write = []
network_retrieval = []
localhost_ports = []
[[permissions.effect_request]]
kind = "test.record"
destination = "{DESTINATION}"
[[contributes]]
id = "sender"
point = "task.worker"
entrypoint = "lifehub.wasm"
[contributes.config]
module = "sender.wasm"
'''
    archive = tmp_path / "baseline.zip"
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


def test_wasm_email_uses_manifest_scope_review_and_fake_dispatch(tmp_path):
    root, db = _install(tmp_path, _module())
    with closing(LifeHub(db_path=db, plugins_path=root)) as hub:
        assert hub.run_wasm("baseline.email:sender") == 0
        request = hub.last_effect_ids[0]
        assert hub.effects.get(request)["payload"] == PAYLOAD
        assert hub.effects.get(request)["status"] == "pending"
        hub.approve_effect(request)
        assert hub.dispatch_effect(request) == "succeeded"
        with pytest.raises(ValueError, match="already attempted"):
            hub.dispatch_effect(request)
        hub.run_wasm("baseline.email:sender")
        assert hub.last_effect_ids == [request]


def test_wasm_email_cannot_request_undeclared_recipient(tmp_path):
    root, db = _install(tmp_path, _module("attacker@example.org"))
    with closing(LifeHub(db_path=db, plugins_path=root)) as hub:
        with pytest.raises((PermissionError, wasmtime.Trap)):
            hub.run_wasm("baseline.email:sender")
        assert hub.effects.list() == []
