"""Separate-daemon proof of actual guest work while no Shell is connected."""

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

HERE = Path(__file__).resolve().parent
# Reuse public demonstration packaging/daemon utilities, never a guest Python runner.
spec = importlib.util.spec_from_file_location(
    "proof_util", HERE.parent / "lifehub-third-party-apps" / "run_demo.py"
)
util = importlib.util.module_from_spec(spec)
spec.loader.exec_module(util)
util.HERE = HERE
util.APPS = (("thirdparty.heartbeat", "heartbeat"), ("thirdparty.observer", "observer"),
             ("thirdparty.fault-probe", "fault"))
CONSUMER = "thirdparty.observer:observe"
PROVIDER = "thirdparty.heartbeat:counter"
INTERFACE = "example.heartbeat@1"


def prove(root):
    db, installed = root / "engine.db", root / "installed"
    util.install_packages(db, installed, util.build_packages(root / "packages"))
    address, family = util.endpoint_for(root)
    process, key = util.start_daemon(root, db, installed, address, family)

    def request(op, **fields):
        return util.request(address, family, key, op, **fields)

    def ok(op, **fields):
        return util.require_ok(request(op, **fields))

    try:
        provider = ok("start", ref=PROVIDER)
        assert provider["state"] == "running" and provider["ready"]
        util.require_denied(request("start", ref=CONSUMER))
        binding = dict(consumer=CONSUMER, interface=INTERFACE, provider=PROVIDER)
        review = ok("route-review", **binding)
        ok("route-grant", **binding, approval_digest=review["approval_digest"])
        fault = ok("start", ref="thirdparty.fault-probe:fail")
        before = ok("start", ref=CONSUMER)["result"]
        # Every request closes its connection. No client remains connected here.
        time.sleep(0.8)
        query_at = datetime.now(UTC)
        rows = ok("executions")
        failed = next(row for row in rows if row["execution_id"] == fault["execution_id"])
        assert failed["state"] == "failed" and not failed["ready"]
        assert (query_at - datetime.fromisoformat(failed["updated_at"])).total_seconds() > 0.05
        print("PASS guest failure persisted before any client reconnected")
        after = ok("start", ref=CONSUMER)["result"]
        assert after - before >= 2, (before, after)
        print(f"PASS shell-free guest work: counter {before} -> {after}")
        ok("route-revoke", **binding)
        util.require_denied(request("start", ref=CONSUMER))
    finally:
        # Actual Engine process termination, not orderly Engine.shutdown().
        util.stop_daemon(process, address, family)
    process, key = util.start_daemon(root, db, installed, address, family)
    try:
        rows = ok("executions")
        assert any(row["execution_id"] == provider["execution_id"]
                   and row["state"] == "interrupted" for row in rows)
        util.require_denied(request("start", ref=CONSUMER))
        recovered = ok("start", ref=PROVIDER)
        assert recovered["execution_id"] != provider["execution_id"]
        assert recovered["ready"]
        stopped = ok("stop", execution_id=recovered["execution_id"])
        assert stopped["state"] == "stopped" and not stopped["ready"]
        print("PASS crash history, explicit new execution, retained revocation, graceful guest stop")
    finally:
        util.stop_daemon(process, address, family)
    assert "http.server" not in sys.modules
    print(json.dumps({"status": "PASS", "platform": sys.platform,
                      "persistent_guest": True, "shell_free_work_delta": after - before,
                      "shell_free_failure_monitor": True,
                      "automatic_restart": False}))


if __name__ == "__main__":
    with TemporaryDirectory(prefix="lifehub-background-proof-") as directory:
        prove(Path(directory))
