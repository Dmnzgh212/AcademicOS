"""Real subprocess Wasm lifecycle and live-instance authority."""

import importlib.util
from pathlib import Path
import time

import pytest

from academicos.lifehub.engine import LifeHubEngine
from academicos.lifehub.background import BackgroundHandle


def installed(tmp_path):
    path = Path(__file__).resolve().parents[1] / "examples/lifehub-background-apps/run_demo.py"
    spec = importlib.util.spec_from_file_location("background_proof", path)
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    db, plugins = tmp_path / "state.db", tmp_path / "plugins"
    proof.util.install_packages(db, plugins, proof.util.build_packages(tmp_path / "archives"))
    return proof, LifeHubEngine(db_path=db, plugins_path=plugins)


def test_background_rejects_ambient_imports_and_fuel_traps():
    import wasmtime
    with pytest.raises(ValueError):
        BackgroundHandle(wasmtime.wat2wasm('''(module
          (import "wasi_snapshot_preview1" "fd_write" (func))
          (memory (export "memory") 1))'''), lambda: None)
    handle = BackgroundHandle(wasmtime.wat2wasm('''(module
      (memory (export "memory") 1)
      (func (export "ready") (result i32) i32.const 1)
      (func (export "tick") (result i32) (loop $spin br $spin) i32.const 0)
      (func (export "run") (result i32) i32.const 0))'''), lambda: None)
    try:
        handle.process.wait(timeout=3)
        assert handle.process.returncode != 0
    finally:
        handle.stop()


def test_guest_works_without_clients_and_live_route_revoke(tmp_path):
    proof, engine = installed(tmp_path)
    try:
        provider = engine.start(proof.PROVIDER)
        assert provider.ready
        with pytest.raises(PermissionError):
            engine.start(proof.CONSUMER)
        review = engine.routes.review(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER)
        engine.routes.grant(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER,
                            approved_digest=review["approval_digest"])
        first = engine.start(proof.CONSUMER).result
        time.sleep(0.5)
        second = engine.start(proof.CONSUMER).result
        assert second - first >= 2
        old_call = engine._interface_call_for(engine.component(proof.CONSUMER))
        engine.stop(provider.execution_id)
        provider = engine.start(proof.PROVIDER)
        with pytest.raises(PermissionError):
            old_call(proof.INTERFACE, {})
        engine.routes.revoke(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER)
        with pytest.raises(PermissionError):
            engine.start(proof.CONSUMER)
        handle = engine._execution(provider.execution_id).handle
        handle.process.kill()
        handle.process.wait(timeout=3)
        assert engine.execution(provider.execution_id).state == "failed"
        assert not engine.execution(provider.execution_id).ready
        new = engine.start(proof.PROVIDER)
        assert new.execution_id != provider.execution_id
        engine.stop(new.execution_id)
    finally:
        engine.shutdown()


def test_identical_reinstall_cannot_reuse_background_handle(tmp_path):
    proof, engine = installed(tmp_path)
    try:
        provider = engine.start(proof.PROVIDER)
        handle = engine._execution(provider.execution_id).handle
        engine.kernel.packages.uninstall("thirdparty.heartbeat")
        archive = tmp_path / "archives" / "thirdparty.heartbeat.lhpkg"
        review = engine.kernel.packages.review(archive)
        engine.kernel.packages.install(archive, approved_hash=review.content_hash)
        with pytest.raises(PermissionError):
            handle.call({})
    finally:
        engine.shutdown()


def test_background_tamper_and_inflight_revocation_fail_closed(tmp_path):
    proof, engine = installed(tmp_path)
    try:
        provider = engine.start(proof.PROVIDER)
        review = engine.routes.review(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER)
        engine.routes.grant(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER,
                            approved_digest=review["approval_digest"])
        callback = engine._interface_call_for(engine.component(proof.CONSUMER))
        handle = engine._execution(provider.execution_id).handle
        original = handle.call
        def revoked(request):
            output = original(request)
            engine.routes.revoke(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER)
            return output
        handle.call = revoked
        with pytest.raises(PermissionError):
            callback(proof.INTERFACE, {})
        (engine.kernel.bundle("thirdparty.heartbeat").root / "worker.wasm").write_bytes(b"tamper")
        with pytest.raises(PermissionError):
            original({})
    finally:
        engine.shutdown()
