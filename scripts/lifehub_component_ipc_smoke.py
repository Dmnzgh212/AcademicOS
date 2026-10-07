"""Validate component IPC using an installed wheel outside the source checkout."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import zipfile

import academicos
import wasmtime

from academicos.lifehub.engine import LifeHubEngine
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.store import LifeStore


def denied(operation):
    try:
        operation()
    except (PermissionError, KeyError):
        return
    raise AssertionError("operation unexpectedly retained authority")


def main():
    repo = Path(sys.argv[1]).resolve()
    assert not Path(academicos.__file__).resolve().is_relative_to(repo)
    provider = '''(module
      (import "lifehub_service" "read_request" (func $r (param i32 i32) (result i32)))
      (import "lifehub_service" "write_response" (func $w (param i32 i32) (result i32)))
      (memory (export "memory") 1)
      (func (export "run") (result i32) (local $n i32)
        (local.set $n (call $r (i32.const 0) (i32.const 65536)))
        (drop (call $w (i32.const 0) (local.get $n))) (i32.const 0)))'''
    consumer = '''(module
      (import "lifehub" "call_interface_json"
        (func $c (param i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "example.echo@1")
      (data (i32.const 64) "{}")
      (func (export "run") (result i32)
        (call $c (i32.const 0) (i32.const 14) (i32.const 64) (i32.const 2)
                 (i32.const 128) (i32.const 4096))))'''
    with TemporaryDirectory(prefix="lifehub-component-ipc-") as work:
        root = Path(work)
        db, installed = root / "engine.db", root / "installed"
        archives = {}
        store = LifeStore(db)
        try:
            installer = PackageInstaller(installed, store)
            for name, declarations, wat in (
                ("smoke.consumer", 'requires = ["example.echo@1"]', consumer),
                ("smoke.provider", 'provides = ["example.echo@1"]\n'
                 'contract = "lifehub.service-json@1"', provider),
            ):
                archive = root / f"{name}.lhpkg"
                archives[name] = archive
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
                review = installer.review(archive)
                installer.install(archive, approved_hash=review.content_hash)
        finally:
            store.close()

        def grant(engine):
            review = engine.routes.review(
                "smoke.consumer:worker", "example.echo@1", "smoke.provider:worker"
            )
            engine.routes.grant(
                "smoke.consumer:worker", "example.echo@1", "smoke.provider:worker",
                approved_digest=review["approval_digest"],
            )

        engine = LifeHubEngine(db_path=db, plugins_path=installed)
        try:
            assert len(engine.components()) == 2
            assert all(item.point is None for item in engine.components())
            denied(lambda: engine.start("smoke.consumer:worker"))
            grant(engine)
            completed = engine.start("smoke.consumer:worker")
            assert completed.result == 2 and completed.state == "completed"
            engine.routes.revoke("smoke.consumer:worker", "example.echo@1")
            denied(lambda: engine.start("smoke.consumer:worker"))
        finally:
            engine.close()

        engine = LifeHubEngine(db_path=db, plugins_path=installed)
        try:
            assert engine.execution(completed.execution_id).state == "completed"
            denied(lambda: engine.start("smoke.consumer:worker"))
            grant(engine)
            assert engine.start("smoke.consumer:worker").result == 2
            engine.kernel.packages.uninstall("smoke.provider")
            denied(lambda: engine.start("smoke.consumer:worker"))
            archive = archives["smoke.provider"]
            review = engine.kernel.packages.review(archive)
            engine.kernel.packages.install(archive, approved_hash=review.content_hash)
            denied(lambda: engine.start("smoke.consumer:worker"))
        finally:
            engine.close()
    assert "http.server" not in sys.modules
    assert "academicos.lifehub.web" not in sys.modules
    print(json.dumps({"status": "PASS", "scope": "installed-wheel component IPC/revoke/restart/uninstall",
                      "host_platform": sys.platform, "windows_certified": False}))


if __name__ == "__main__":
    main()
