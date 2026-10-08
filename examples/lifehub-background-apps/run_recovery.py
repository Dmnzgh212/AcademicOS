"""Installed-wheel real-process recovery proof, using two independent guest apps."""

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import sys
from tempfile import TemporaryDirectory
import time
import zipfile

spec = importlib.util.spec_from_file_location("background_proof", Path(__file__).with_name("run_demo.py"))
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)


def kill_guest(pid):
    # Trusted operator fault injection, never an operation available to guests.
    if os.name == "nt":
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.restype = ctypes.c_void_p
        api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = api.OpenProcess(1, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not api.TerminateProcess(handle, 91):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            api.CloseHandle(handle)
    else:
        os.kill(pid, signal.SIGKILL)


class ProcessObservation:
    """Operator-only observation, pinned against PID reuse; not a guest API."""

    def __init__(self, pid):
        self.pid = pid
        self.handle = None
        self.pidfd = None
        if os.name == "nt":
            self.api = ctypes.WinDLL("kernel32", use_last_error=True)
            self.api.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
            self.api.OpenProcess.restype = ctypes.c_void_p
            self.api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            self.api.WaitForSingleObject.restype = ctypes.c_uint
            self.api.CloseHandle.argtypes = [ctypes.c_void_p]
            self.handle = self.api.OpenProcess(0x100000, False, pid)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
        elif sys.platform == "linux":
            self.pidfd = os.pidfd_open(pid)
            self.poller = select.poll()
            self.poller.register(self.pidfd, select.POLLIN)
        else:
            raise RuntimeError("process observation supports Linux and Windows only")

    def exited(self):
        if self.handle is not None:
            result = self.api.WaitForSingleObject(self.handle, 0)
            if result not in (0, 258):
                raise ctypes.WinError(ctypes.get_last_error())
            return result == 0
        return bool(self.poller.poll(0))

    def close(self):
        if self.pidfd is not None:
            os.close(self.pidfd)
            self.pidfd = None
        if self.handle is not None:
            self.api.CloseHandle(self.handle)
            self.handle = None


def wait_for(function, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = function()
        if predicate(value):
            return value
        time.sleep(0.05)
    raise AssertionError(f"recovery deadline exceeded: {value!r}")


def run(root):
    began = time.monotonic()
    db, installed = root / "engine.db", root / "installed"
    archives = proof.util.build_packages(root / "packages")
    for archive in (archives[0], archives[2]):
        with zipfile.ZipFile(archive) as source:
            manifest, module = source.read("plugin.toml"), source.read("worker.wasm")
        manifest += b'\n[components.config.restart]\nmax_retries=2\nwindow=60\nbackoff=0.2\nmax_backoff=0.8\n'
        with zipfile.ZipFile(archive, "w") as target:
            for name, contents in (("plugin.toml", manifest), ("worker.wasm", module)):
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.external_attr = 0o644 << 16
                target.writestr(entry, contents)
    proof.util.install_packages(db, installed, archives)
    evidence = {"status": "NOT COMPLETED", "git_sha": os.environ.get("GITHUB_SHA"),
                "platform": sys.platform, "python": sys.version,
                "packages": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in archives}}
    (root / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    address, family = proof.util.endpoint_for(root)
    process, key = proof.util.start_daemon(root, db, installed, address, family)

    def ok(op, **fields):
        return proof.util.require_ok(proof.util.request(address, family, key, op, **fields))

    def intents():
        return {item["ref"]: item for item in ok("desired-components")}

    binding = dict(consumer=proof.CONSUMER, interface=proof.INTERFACE, provider=proof.PROVIDER)
    old_worker = None
    try:
        first = ok("start", ref=proof.PROVIDER)
        review = ok("route-review", **binding)
        ok("route-grant", **binding, approval_digest=review["approval_digest"])
        before = ok("start", ref=proof.CONSUMER)["result"]
        time.sleep(0.6)
        assert ok("start", ref=proof.CONSUMER)["result"] - before >= 2
        pid = next(worker["pid"] for worker in ok("supervisor-health")["workers"]
                   if worker["execution_id"] == first["execution_id"])
        kill_guest(pid)
        time.sleep(1)  # All clients disconnected during recovery.
        recovered = wait_for(intents, lambda rows: rows[proof.PROVIDER]["execution_id"] != first["execution_id"])[proof.PROVIDER]
        wait_for(lambda: ok("executions"), lambda rows: any(
            row["execution_id"] == recovered["execution_id"] and row["ready"] for row in rows))
        assert ok("start", ref=proof.CONSUMER)["state"] == "completed"
        print(f"PASS actual guest death -> automatic new execution {first['execution_id']} -> {recovered['execution_id']}")
        ok("start", ref="thirdparty.fault-probe:fail")
        wait_for(intents, lambda rows: rows["thirdparty.fault-probe:fail"]["status"] == "quarantined")
        assert len(intents()["thirdparty.fault-probe:fail"]["failures"]) == 3
        assert ok("start", ref=proof.CONSUMER)["state"] == "completed"
        print("PASS crash loop quarantined after two retries; independent provider still serves")
        ok("route-revoke", **binding)
        old_pid = next(worker["pid"] for worker in ok("supervisor-health")["workers"]
                       if worker["execution_id"] == recovered["execution_id"])
        old_worker = ProcessObservation(old_pid)
        assert not old_worker.exited()
    finally:
        proof.util.stop_daemon(process, address, family)
    process, key = proof.util.start_daemon(root, db, installed, address, family)
    try:
        restored = wait_for(intents, lambda rows: rows[proof.PROVIDER]["execution_id"] != recovered["execution_id"])[proof.PROVIDER]
        wait_for(lambda: ok("executions"), lambda rows: any(row["execution_id"] == restored["execution_id"] and row["ready"] for row in rows))
        assert old_worker.exited(), "old guest remains live after replacement is ready"
        print(f"PASS old guest pid={old_pid} exited by replacement readiness; PID-reuse-safe observation")
        assert any(row["execution_id"] == recovered["execution_id"] and row["state"] == "interrupted" for row in ok("executions"))
        denied = proof.util.request(address, family, key, "start", ref=proof.CONSUMER)
        proof.util.require_denied(denied)
        assert intents()["thirdparty.fault-probe:fail"]["status"] == "quarantined"
        ok("stop-component", ref=proof.PROVIDER)
        time.sleep(0.6)
        assert intents()[proof.PROVIDER]["status"] == "stopped"
        print(f"PASS killed Engine -> automatic desired-state restoration {restored['execution_id']}; revoke retained; stop suppresses restart")
    finally:
        proof.util.stop_daemon(process, address, family)
        if old_worker is not None:
            old_worker.close()
    print(json.dumps({"status": "PASS", "platform": sys.platform,
                      "automatic_guest_recovery": True, "automatic_engine_restoration": True,
                      "max_retries": 2, "window": 60, "backoff": [0.2, 0.4, 0.8]}))
    evidence.update(status="PASS", elapsed_seconds=time.monotonic() - began,
                    execution_ids=[first["execution_id"], recovered["execution_id"], restored["execution_id"]],
                    old_guest_pid=old_pid, old_guest_exited_by_replacement_ready=True,
                    policy={"max_retries": 2, "window": 60, "backoff": 0.2, "max_backoff": 0.8})
    (root / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Preserve exact packages and run evidence in a fresh directory")
    arguments = parser.parse_args()
    if arguments.output is None:
        with TemporaryDirectory(prefix="lifehub-recovery-proof-") as directory:
            run(Path(directory))
    else:
        arguments.output.mkdir(parents=True, exist_ok=False)
        run(arguments.output)
