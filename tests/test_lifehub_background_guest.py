"""Real subprocess Wasm lifecycle and live-instance authority."""

import importlib.util
from pathlib import Path
import time
import sqlite3
import threading
import zipfile

import pytest

from academicos.lifehub.engine import LifeHubEngine
from academicos.lifehub.background import BackgroundHandle
from academicos.lifehub.control import CONTROL_API, EngineController


def installed(tmp_path, restart=False, backoff=0.1):
    path = Path(__file__).resolve().parents[1] / "examples/lifehub-background-apps/run_demo.py"
    spec = importlib.util.spec_from_file_location("background_proof", path)
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    db, plugins = tmp_path / "state.db", tmp_path / "plugins"
    archives = proof.util.build_packages(tmp_path / "archives")
    if restart:
        for archive in (archives[0], archives[2]):
            with zipfile.ZipFile(archive) as source:
                manifest, module = source.read("plugin.toml"), source.read("worker.wasm")
            manifest += (f'\n[components.config.restart]\nmax_retries=2\nwindow=60\n'
                         f'backoff={backoff}\nmax_backoff={max(0.4, backoff)}\n').encode()
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr("plugin.toml", manifest)
                target.writestr("worker.wasm", module)
    proof.util.install_packages(db, plugins, archives)
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


def test_monitor_records_guest_death_without_engine_query(tmp_path):
    proof, engine = installed(tmp_path)
    try:
        provider = engine.start(proof.PROVIDER)
        handle = engine._execution(provider.execution_id).handle
        handle.process.kill()
        handle.process.wait(timeout=3)
        # Test-only independent ledger observation. No Engine/Shell calls can
        # trigger the old query-time reconciliation during this assertion.
        with sqlite3.connect(tmp_path / "state.db") as observer:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                state = observer.execute(
                    "SELECT state FROM lifehub_engine_executions WHERE execution_id=?",
                    (provider.execution_id,),
                ).fetchone()[0]
                if state == "failed":
                    break
                time.sleep(0.02)
            assert state == "failed"
        assert not engine._executions[provider.execution_id].ready
    finally:
        engine.shutdown()
    assert not engine._monitor.is_alive()


def test_uninstall_stops_guest_without_next_call(tmp_path):
    proof, engine = installed(tmp_path)
    try:
        provider = engine.start(proof.PROVIDER)
        handle = engine._execution(provider.execution_id).handle
        engine.kernel.packages.uninstall("thirdparty.heartbeat")
        # No execution query or guest call is made after uninstall.
        handle.process.wait(timeout=3)
        with sqlite3.connect(tmp_path / "state.db") as observer:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                state, error = observer.execute(
                    "SELECT state,error FROM lifehub_engine_executions WHERE execution_id=?",
                    (provider.execution_id,),
                ).fetchone()
                if state == "failed":
                    break
                time.sleep(0.02)
            assert state == "failed"
            assert error == "background installation identity changed"
        archive = tmp_path / "archives" / "thirdparty.heartbeat.lhpkg"
        review = engine.kernel.packages.review(archive)
        engine.kernel.packages.install(archive, approved_hash=review.content_hash)
        assert handle.process.poll() is not None
        replacement = engine.start(proof.PROVIDER)
        assert replacement.execution_id != provider.execution_id
    finally:
        engine.shutdown()


def test_monitor_busy_ledger_retries_and_stop_is_terminal(tmp_path):
    proof, engine = installed(tmp_path)
    blocker = sqlite3.connect(tmp_path / "state.db")
    try:
        provider = engine.start(proof.PROVIDER)
        blocker.execute("BEGIN EXCLUSIVE")
        handle = engine._execution(provider.execution_id).handle
        handle.process.kill()
        handle.process.wait(timeout=3)
        deadline = time.monotonic() + 3
        while engine._executions[provider.execution_id].ready and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not engine._executions[provider.execution_id].ready
        blocker.rollback()
        deadline = time.monotonic() + 3
        while (engine._executions[provider.execution_id].state != "failed"
               and time.monotonic() < deadline):
            time.sleep(0.02)
        assert engine._executions[provider.execution_id].state == "failed"
        replacement = engine.start(proof.PROVIDER)
        engine.stop(replacement.execution_id)
        time.sleep(0.2)
        assert engine.execution(replacement.execution_id).state == "stopped"
    finally:
        blocker.close()
        engine.shutdown()


def test_cleanup_failure_still_stops_other_guests_and_releases_owner(tmp_path):
    proof, engine = installed(tmp_path)
    first = engine.start(proof.PROVIDER)
    second = engine.start("thirdparty.fault-probe:fail")
    handles = [engine._execution(row.execution_id).handle for row in (first, second)]
    def broken_stop():
        raise RuntimeError("injected worker cleanup failure")
    handles[0].stop = broken_stop
    with pytest.raises(ExceptionGroup):
        engine.shutdown()
    assert all(handle.process.poll() is not None for handle in handles)
    assert engine._closed and not engine._monitor.is_alive()
    # No leaked ownership after an aggregate cleanup error.
    replacement = LifeHubEngine(db_path=tmp_path / "state.db", plugins_path=tmp_path / "plugins")
    replacement.shutdown()


def test_monitor_failure_is_visible_and_denies_new_guests(tmp_path, monkeypatch):
    release = threading.Event()
    def failing_monitor(self):
        release.wait(timeout=5)
        raise RuntimeError("injected monitor failure")
    monkeypatch.setattr(LifeHubEngine, "_monitor_background", failing_monitor)
    proof, engine = installed(tmp_path)
    try:
        started = engine.start(proof.PROVIDER)
        handle = engine._execution(started.execution_id).handle
        release.set()
        handle.process.wait(timeout=3)
        health = EngineController(engine).handle({"api": CONTROL_API, "op": "supervisor-health"})
        assert health["ok"] and health["result"]["status"] == "failed"
        assert "injected monitor failure" in health["result"]["error"]
        assert not engine.execution(started.execution_id).ready
        with pytest.raises(PermissionError, match="supervisor failed"):
            engine.start(proof.PROVIDER)
    finally:
        release.set()
        engine.shutdown()


def test_shutdown_reconciliation_failure_still_cleans_up(tmp_path, monkeypatch):
    proof, engine = installed(tmp_path)
    provider = engine.start(proof.PROVIDER)
    handle = engine._execution(provider.execution_id).handle
    def unavailable_ledger():
        raise sqlite3.OperationalError("injected ledger failure")
    monkeypatch.setattr(engine, "_refresh_background", unavailable_ledger)
    with pytest.raises(ExceptionGroup):
        engine.shutdown()
    assert engine._closed and handle.process.poll() is not None
    replacement = LifeHubEngine(db_path=tmp_path / "state.db", plugins_path=tmp_path / "plugins")
    replacement.shutdown()


def test_automatic_recovery_and_crash_loop_are_bounded(tmp_path):
    proof, engine = installed(tmp_path, restart=True)
    try:
        first = engine.start(proof.PROVIDER)
        old_call = None
        review = engine.routes.review(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER)
        engine.routes.grant(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER,
                            approved_digest=review["approval_digest"])
        old_call = engine._interface_call_for(engine.component(proof.CONSUMER))
        handle = engine._execution(first.execution_id).handle
        handle.process.kill()
        handle.process.wait(timeout=3)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            intent = engine.desired_components()[0]
            if intent["execution_id"] != first.execution_id and engine.execution(intent["execution_id"]).ready:
                break
            time.sleep(0.03)
        assert intent["execution_id"] != first.execution_id
        assert engine.execution(intent["execution_id"]).ready
        with pytest.raises(ValueError, match="not running"):
            engine.stop(first.execution_id)
        assert engine.desired_components()[0]["status"] == "wanted"
        assert engine.execution(intent["execution_id"]).ready
        with pytest.raises(PermissionError):
            old_call(proof.INTERFACE, {})
        assert engine.start(proof.CONSUMER).state == "completed"
        engine.start("thirdparty.fault-probe:fail")
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            rows = engine.desired_components()
            fault = next(row for row in rows if "fault-probe" in row["ref"])
            if fault["status"] == "quarantined":
                break
            time.sleep(0.03)
        assert fault["status"] == "quarantined" and len(fault["failures"]) == 3
        engine.stop_component(proof.PROVIDER)
        time.sleep(0.3)
        assert next(row for row in engine.desired_components() if row["ref"] == proof.PROVIDER)["status"] == "stopped"
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


def test_engine_reopens_and_restores_only_approved_intent(tmp_path):
    proof, engine = installed(tmp_path, restart=True)
    first = engine.start(proof.PROVIDER)
    review = engine.routes.review(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER)
    engine.routes.grant(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER,
                        approved_digest=review['approval_digest'])
    engine.routes.revoke(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER)
    engine.close()
    replacement = LifeHubEngine(db_path=tmp_path / 'state.db', plugins_path=tmp_path / 'plugins')
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            intent = replacement.desired_components()[0]
            if intent['execution_id'] != first.execution_id and replacement.execution(intent['execution_id']).ready:
                break
            time.sleep(0.03)
        assert intent['execution_id'] != first.execution_id
        assert replacement.execution(intent['execution_id']).ready
        assert replacement.execution(first.execution_id).state == 'interrupted'
        with pytest.raises(PermissionError):
            replacement.start(proof.CONSUMER)
        replacement.shutdown()
    finally:
        replacement.close()
    final = LifeHubEngine(db_path=tmp_path / 'state.db', plugins_path=tmp_path / 'plugins')
    try:
        time.sleep(0.3)
        assert final.desired_components()[0]['status'] == 'stopped'
        assert not final._executions
    finally:
        final.shutdown()


@pytest.mark.parametrize('action', ['stop', 'uninstall-reinstall'])
def test_dead_guest_intent_cannot_survive_stop_or_reinstallation(tmp_path, action):
    proof, engine = installed(tmp_path, restart=True)
    try:
        first = engine.start(proof.PROVIDER)
        review = engine.routes.review(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER)
        engine.routes.grant(proof.CONSUMER, proof.INTERFACE, proof.PROVIDER,
                            approved_digest=review['approval_digest'])
        handle = engine._execution(first.execution_id).handle
        # Hold lifecycle coordination only to place the operator action exactly
        # after real guest death and before the unattended monitor can restart.
        with engine._lifecycle_lock:
            handle.process.kill()
            handle.process.wait(timeout=3)
            if action == 'stop':
                engine.stop_component(proof.PROVIDER)
            else:
                engine.kernel.packages.uninstall('thirdparty.heartbeat')
                archive = tmp_path / 'archives' / 'thirdparty.heartbeat.lhpkg'
                proof.util.install_packages(tmp_path / 'state.db', tmp_path / 'plugins', (archive,))
        time.sleep(0.8)
        intent = engine.desired_components()[0]
        assert intent['status'] == 'stopped'
        assert intent['execution_id'] == first.execution_id
        assert engine.execution(first.execution_id).state == 'failed'
        assert not any(row.ready for row in engine.executions())
        if action == 'uninstall-reinstall':
            with pytest.raises(PermissionError):
                engine.start(proof.CONSUMER)
    finally:
        engine.shutdown()


def wait_for_intent(engine, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        intent = engine.desired_components()[0]
        if predicate(intent):
            return intent
        time.sleep(0.02)
    raise AssertionError(f'intent did not reach required state: {intent!r}')


def test_stop_during_declared_backoff_prevents_replacement(tmp_path):
    proof, engine = installed(tmp_path, restart=True, backoff=0.5)
    try:
        first = engine.start(proof.PROVIDER)
        handle = engine._execution(first.execution_id).handle
        handle.process.kill()
        handle.process.wait(timeout=3)
        waiting = wait_for_intent(engine, lambda row: row['status'] == 'recovering')
        assert waiting['execution_id'] == first.execution_id
        assert waiting['next_at'] > time.time()
        engine.stop_component(proof.PROVIDER)
        time.sleep(0.8)  # Past the original retry deadline, without a client call.
        intent = engine.desired_components()[0]
        assert intent['status'] == 'stopped'
        assert intent['execution_id'] == first.execution_id
        assert not any(row.ready for row in engine.executions())
    finally:
        engine.shutdown()


def test_recovery_budget_survives_manager_recreation(tmp_path):
    proof, engine = installed(tmp_path, restart=True)
    try:
        first = engine.start(proof.PROVIDER)
        handle = engine._execution(first.execution_id).handle
        handle.process.kill()
        handle.process.wait(timeout=3)
        recovered = wait_for_intent(engine, lambda row: row['execution_id'] != first.execution_id)
        assert engine.execution(recovered['execution_id']).ready
        assert len(recovered['failures']) == 1
        engine.close()  # Keep approved intent, interrupt its in-memory instance.
        engine = LifeHubEngine(db_path=tmp_path / 'state.db', plugins_path=tmp_path / 'plugins')
        restored = wait_for_intent(engine, lambda row: row['execution_id'] != recovered['execution_id'])
        assert engine.execution(restored['execution_id']).ready
        assert len(restored['failures']) == 2
        engine.close()
        engine = LifeHubEngine(db_path=tmp_path / 'state.db', plugins_path=tmp_path / 'plugins')
        quarantined = wait_for_intent(engine, lambda row: row['status'] == 'quarantined')
        assert len(quarantined['failures']) == 3
        assert quarantined['execution_id'] == restored['execution_id']
        assert not any(row.ready for row in engine.executions())
        engine.close()
        engine = LifeHubEngine(db_path=tmp_path / 'state.db', plugins_path=tmp_path / 'plugins')
        time.sleep(0.3)
        assert engine.desired_components()[0]['status'] == 'quarantined'
        assert not engine._executions
    finally:
        engine.shutdown()
