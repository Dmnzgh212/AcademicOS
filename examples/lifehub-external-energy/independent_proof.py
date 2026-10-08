"""Black-box installed-wheel integration of separately authored energy Wasm apps.

This AI-authored experiment does NOT claim unrelated human developer authorship.
No imports from Engine implementation, packages, kernels or example test utilities.
"""
from __future__ import annotations

import argparse
import ctypes
from contextlib import ExitStack
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from uuid import uuid4
import zipfile

import wasmtime

from academicos.lifehub.control import CONTROL_API, control_request
from academicos.lifehub.daemon import load_authkey


HERE = Path(__file__).resolve().parent
METER = "external.energy-meter:measure"
BUDGET = "external.energy-budget:remaining"
INTERFACE = "lab.energy.spent@1"


def packages(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True)
    result = {}
    for key in ("meter", "budget"):
        archive = directory / f"external.energy-{key}.lhpkg"
        module = wasmtime.wat2wasm((HERE / f"{key}.wat").read_text(encoding="utf-8"))
        manifest = (HERE / key / "plugin.toml").read_bytes()
        with zipfile.ZipFile(archive, "w") as out:
            for name, data in (("plugin.toml", manifest), ("worker.wasm", module)):
                item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                item.compress_type = zipfile.ZIP_STORED
                item.external_attr = 0o644 << 16
                out.writestr(item, data)
        result[key] = archive
    return result


def cli(*args: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-I", "-m", "academicos.lifehub.cli", *map(str, args)],
        check=True, text=True, capture_output=True, timeout=30,
    )
    return completed.stdout


def review_install(archives: dict[str, Path], db: Path, folder: Path):
    inspected = {}
    for key, archive in archives.items():
        output = cli("review-package", str(archive))
        match = re.search(r"sha256-content:\s*([0-9a-f]{64})", output)
        assert match, f"public review command omitted reviewed digest: {output!r}"
        digest = match.group(1)
        cli("install-package", str(archive), "--approve-hash", digest,
            "--db", str(db), "--installed", str(folder))
        inspected[key] = {"zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                          "reviewed_content_sha256": digest}
    return inspected


def endpoint(root: Path):
    if os.name == "nt":
        return rf"\\.\pipe\lifehub-energy-{uuid4().hex}", "AF_PIPE"
    return str(root / "energy.sock"), "AF_UNIX"


def command(address, family, key, operation, **fields):
    return control_request(
        address, {"api": CONTROL_API, "op": operation, **fields},
        authkey=key, family=family,
    )


def accepted(response):
    assert response.get("ok") is True, f"Engine operation unexpectedly rejected: {response!r}"
    return response["result"]


def denied(response):
    assert response.get("ok") is False, f"unauthorized operation accepted: {response!r}"
    assert response.get("error", {}).get("type") in ("PermissionError", "KeyError"), response


def kill_process(pid: int):
    """Trusted test fault injection outside any guest capability."""
    if os.name != "nt":
        import signal
        os.kill(pid, signal.SIGKILL)
        return
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.restype = ctypes.c_void_p
    api.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
    api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    api.TerminateProcess.restype = ctypes.c_int
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = api.OpenProcess(0x0001, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not api.TerminateProcess(handle, 72):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        api.CloseHandle(handle)


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


def wait_until(fetch, condition, seconds=12):
    deadline = time.monotonic() + seconds
    latest = None
    while time.monotonic() < deadline:
        latest = fetch()
        if condition(latest):
            return latest
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for expected state: {latest!r}")


def end_engine(process: subprocess.Popen, address: str, family: str):
    if process.poll() is None:
        process.terminate()  # OS termination, not graceful operator shutdown
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if family == "AF_UNIX":
        Path(address).unlink(missing_ok=True)


def begin_engine(root, db, installed, address, family):
    auth_file = root / "operator.key"
    log_file = root / "engine.log"
    with log_file.open("ab") as log:
        proc = subprocess.Popen(
            [sys.executable, "-I", "-m", "academicos.lifehub.cli", "engine-serve",
             "--db", str(db), "--installed", str(installed),
             "--endpoint", address, "--auth-file", str(auth_file)],
            stdout=log, stderr=subprocess.STDOUT, cwd=root,
        )
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"Engine exited early: {proc.returncode}")
            if auth_file.is_file():
                try:
                    key = load_authkey(auth_file)
                    accepted(command(address, family, key, "ping"))
                    return proc, key
                except (ValueError, OSError, EOFError, ConnectionError):
                    pass  # Auth file may be visible before its 32-byte key is written.
            time.sleep(0.05)
        raise TimeoutError("Engine not ready in 12 s")
    except BaseException:
        end_engine(proc, address, family)
        raise


def prove(root: Path):
    with ExitStack() as observations:
        _prove(root, observations)


def _prove(root: Path, observations):
    start_at = time.monotonic()
    evidence = {"status": "NOT COMPLETED", "author_type": "separate AI integrator",
                "independent_human_authorship": False,
                "git_sha": os.environ.get("GITHUB_SHA"),
                "platform": sys.platform, "python": sys.version,
                "core_files_modified": False, "checks": []}
    root.mkdir(parents=True, exist_ok=False)
    evidence_path = root / "evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    db, installed = root / "engine.db", root / "installed"
    archives = packages(root / "packages")
    evidence["packages"] = review_install(archives, db, installed)
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    address, family = endpoint(root)
    engine, key = begin_engine(root, db, installed, address, family)

    def ask(op, **fields):
        return command(address, family, key, op, **fields)

    def ok(op, **fields):
        return accepted(ask(op, **fields))

    binding = {"consumer": BUDGET, "interface": INTERFACE, "provider": METER}
    ids = {}
    try:
        discovered = {item["ref"] for item in ok("components")}
        assert discovered == {METER, BUDGET}, discovered
        first = ok("start", ref=METER)
        ids["initial"] = first["execution_id"]
        assert first["ready"] and first["state"] == "running"
        denied(ask("start", ref=BUDGET))
        review = ok("route-review", **binding)
        ok("route-grant", **binding, approval_digest=review["approval_digest"])
        first_budget = ok("start", ref=BUDGET)
        assert first_budget["state"] == "completed"
        before = first_budget["result"]
        assert 0 < before <= 200, before
        time.sleep(0.85)  # Every operator request closed its IPC connection.
        after = ok("start", ref=BUDGET)["result"]
        assert 0 <= after < before and (before - after) >= 14, (before, after)
        evidence["checks"].append({"name": "shell-free guest-owned energy work",
                                   "remaining_before": before, "remaining_after": after,
                                   "observed_units_delta": before - after,
                                   "clients_connected_during_sleep": 0})
        print(f"PASS independent Wasm budget calculation while Shell absent: {before} -> {after}")

        ok("route-revoke", **binding)
        denied(ask("start", ref=BUDGET))
        evidence["checks"].append({"name": "revoke denies subsequent consumer", "pass": True})
        ok("route-grant", **binding, approval_digest=ok("route-review", **binding)["approval_digest"])

        workers = ok("supervisor-health")["workers"]
        victim = next(item["pid"] for item in workers if item["execution_id"] == ids["initial"])
        killed_worker = ProcessObservation(victim)
        observations.callback(killed_worker.close)
        kill_process(victim)
        newer = wait_until(lambda: ok("desired-components"),
                           lambda items: any(x["ref"] == METER and
                                             x["execution_id"] != ids["initial"] and
                                             x["status"] == "wanted" for x in items))
        ids["guest_recovery"] = next(x["execution_id"] for x in newer if x["ref"] == METER)
        wait_until(lambda: ok("executions"),
                   lambda items: any(x["execution_id"] == ids["guest_recovery"] and x["ready"]
                                     for x in items))
        assert killed_worker.exited(), "killed worker remains live after recovery readiness"
        assert 0 < ok("start", ref=BUDGET)["result"] <= 200
        evidence["checks"].append({"name": "guest death automatically recovered", "pass": True})
        print(f"PASS guest OS crash recovered: {ids['initial']} -> {ids['guest_recovery']}")

        ok("route-revoke", **binding)
        old_pid = next(x["pid"] for x in ok("supervisor-health")["workers"]
                       if x["execution_id"] == ids["guest_recovery"])
        old_worker = ProcessObservation(old_pid)
        observations.callback(old_worker.close)
        assert not old_worker.exited()
    finally:
        end_engine(engine, address, family)

    engine, key = begin_engine(root, db, installed, address, family)
    try:
        resumed = wait_until(lambda: ok("desired-components"),
                             lambda items: any(x["ref"] == METER and
                                               x["execution_id"] != ids["guest_recovery"] and
                                               x["status"] == "wanted" for x in items))
        ids["engine_recovery"] = next(x["execution_id"] for x in resumed if x["ref"] == METER)
        wait_until(lambda: ok("executions"),
                   lambda items: any(x["execution_id"] == ids["engine_recovery"] and x["ready"]
                                     for x in items))
        assert old_worker.exited(), "old worker remains live after Engine recovery readiness"
        evidence["old_guest_exited_by_replacement_ready"] = True
        denied(ask("start", ref=BUDGET))
        ok("stop-component", ref=METER)
        time.sleep(0.75)
        intent = next(x for x in ok("desired-components") if x["ref"] == METER)
        assert intent["status"] == "stopped"
        assert not any(x["ready"] for x in ok("executions") if x["component_ref"] == METER)
        evidence["checks"].append({"name": "Engine OS restart restores only desired guest; "
                                            "revocation and stop persist", "pass": True})
        print("PASS Engine OS restart restored authorized intent, not revoked route")

        fresh = ok("start", ref=METER)
        ids["before_uninstall"] = fresh["execution_id"]
        uninstall_pid = next(x["pid"] for x in ok("supervisor-health")["workers"]
                             if x["execution_id"] == ids["before_uninstall"])
        uninstalled_worker = ProcessObservation(uninstall_pid)
        observations.callback(uninstalled_worker.close)
        cli("uninstall-package", "external.energy-meter", "--db", str(db),
            "--installed", str(installed))
        # OS-only observation: no Engine request can trigger cleanup here.
        wait_until(uninstalled_worker.exited, bool)
        evidence["uninstalled_guest_exited_before_next_request"] = True
        terminated = next(x for x in ok("executions")
                          if x["execution_id"] == ids["before_uninstall"])
        assert terminated["state"] == "failed" and not terminated["ready"], terminated
        review_install({"meter": archives["meter"]}, db, installed)
        replacement = ok("start", ref=METER)
        ids["reinstalled"] = replacement["execution_id"]
        assert ids["reinstalled"] != ids["before_uninstall"]
        denied(ask("start", ref=BUDGET))
        ok("stop-component", ref=METER)
        evidence["checks"].append({"name": "uninstall stops live guest; reinstall never "
                                            "revives revoked route", "pass": True})
        print("PASS uninstall and same-bytes reinstall cannot resurrect authority")
    finally:
        end_engine(engine, address, family)

    evidence.update(status="PASS", execution_ids=ids,
                    elapsed_seconds=round(time.monotonic() - start_at, 3),
                    completed_at=datetime.now(UTC).isoformat())
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": "PASS", "platform": sys.platform,
                      "external_ai_authorship": True,
                      "human_independence_verified": False,
                      "execution_ids": ids,
                      "checks": len(evidence["checks"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        with TemporaryDirectory(prefix="lifehub-energy-integrator-") as temp:
            prove(Path(temp) / "test")
    else:
        prove(args.output)
