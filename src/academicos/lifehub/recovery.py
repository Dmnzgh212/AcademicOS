"""Bounded, installation-bound background intent; no grants are synthesized."""

from dataclasses import asdict
from datetime import UTC, datetime
import json
import time
from types import SimpleNamespace
from uuid import uuid4

from academicos.lifehub.background import BackgroundWasmRunner
from academicos.lifehub.kernel import LifeHub

SCHEMA = """
CREATE TABLE IF NOT EXISTS lifehub_engine_desired (
 component_ref TEXT PRIMARY KEY, installation TEXT NOT NULL, component TEXT NOT NULL,
 policy TEXT NOT NULL, status TEXT NOT NULL, failures TEXT NOT NULL,
 execution_id TEXT NOT NULL, next_at REAL NOT NULL
);
"""


def policy_for(component):
    policy = component.config.get("restart")
    if policy is None:
        return None
    if not isinstance(policy, dict) or set(policy) != {"max_retries", "window", "backoff", "max_backoff"}:
        raise ValueError("restart policy requires max_retries, window, backoff, max_backoff")
    bounds = {"max_retries": (1, 5), "window": (5, 3600),
              "backoff": (0.1, 30), "max_backoff": (0.1, 60)}
    for field, (lower, upper) in bounds.items():
        value = policy[field]
        if type(value) not in (int, float) or not lower <= value <= upper:
            raise ValueError(f"invalid bounded restart {field}")
    if type(policy["max_retries"]) is not int or policy["max_backoff"] < policy["backoff"]:
        raise ValueError("invalid restart retry count/backoff")
    return policy


def remember(engine, component, execution_id, policy):
    if policy is None:
        return
    row = engine.kernel.store.conn.execute(
        "SELECT * FROM lifehub_installed_packages WHERE plugin_id=?", (component.plugin_id,)
    ).fetchone()
    if row is None:
        raise PermissionError("recovery requires approved installed package")
    with engine.kernel.store.conn:
        engine.kernel.store.conn.execute(
            "INSERT OR REPLACE INTO lifehub_engine_desired VALUES (?,?,?,?,?,?,?,?)",
            (component.ref, json.dumps(tuple(row)), json.dumps(asdict(component)),
             json.dumps(policy), "wanted", "[]", execution_id, 0),
        )


def suppress(engine, ref):
    with engine.kernel.store.conn:
        engine.kernel.store.conn.execute(
            "UPDATE lifehub_engine_desired SET status='stopped' WHERE component_ref=?", (ref,)
        )


def reconcile(engine, conn):
    # Connection and temporary kernel below are owned by the supervisor thread.
    # The operator's kernel connection never crosses threads.
    from academicos.lifehub.engine import ComponentDescriptor, ExecutionState, _Execution

    rows = conn.execute("SELECT * FROM lifehub_engine_desired WHERE status IN ('wanted','recovering')").fetchall()
    for ref, installation, encoded_component, encoded_policy, status, history, last_id, next_at in rows:
        component = ComponentDescriptor(**json.loads(encoded_component))
        identity = tuple(json.loads(installation))
        current = conn.execute("SELECT * FROM lifehub_installed_packages WHERE plugin_id=?",
                               (component.plugin_id,)).fetchone()
        if current != identity:
            with conn:
                conn.execute("UPDATE lifehub_engine_desired SET status='stopped' WHERE component_ref=?", (ref,))
            continue
        state = conn.execute("SELECT state FROM lifehub_engine_executions WHERE execution_id=?", (last_id,)).fetchone()
        if state is not None and state[0] == "running":
            continue
        now = time.time()
        policy = json.loads(encoded_policy)
        if status == "wanted":
            failures = [stamp for stamp in json.loads(history) if now - stamp <= policy["window"]]
            failures.append(now)
            status = "quarantined" if len(failures) > policy["max_retries"] else "recovering"
            delay = min(policy["max_backoff"], policy["backoff"] * 2 ** (len(failures) - 1))
            with conn:
                conn.execute("UPDATE lifehub_engine_desired SET status=?,failures=?,next_at=? WHERE component_ref=?",
                             (status, json.dumps(failures), now + delay, ref))
            continue
        if now < next_at:
            continue
        stamp = datetime.now(UTC).isoformat()
        item = _Execution(uuid4().hex, component, ExecutionState.RUNNING, stamp, stamp)
        engine._executions[item.execution_id] = item
        kernel = None
        handle = None
        try:
            # Ledger failure is a failed attempt, never a live handleless execution.
            engine._persist(item, connection=conn)
            with conn:
                conn.execute("UPDATE lifehub_engine_desired SET execution_id=?,status='wanted' WHERE component_ref=?",
                             (item.execution_id, ref))
            kernel = LifeHub(db_path=engine._ledger_path, plugins_path=engine._plugins_path)
            bundle = kernel.bundle(component.plugin_id)
            manifest = bundle.manifest.model_copy(deep=True)
            started = BackgroundWasmRunner().start(SimpleNamespace(kernel=kernel), component)
            handle = started.handle
            if conn.execute("SELECT * FROM lifehub_installed_packages WHERE plugin_id=?",
                            (component.plugin_id,)).fetchone() != identity:
                raise PermissionError("installation changed during recovery")
            # Invocation-time verification runs on the operator thread, using its
            # own kernel. No closure may retain the temporary thread-owned store.
            def verify(plugin_id=component.plugin_id, expected=identity, expected_manifest=manifest):
                current_bundle = engine.kernel.bundle(plugin_id)
                row = engine.kernel.store.conn.execute(
                    "SELECT * FROM lifehub_installed_packages WHERE plugin_id=?", (plugin_id,)
                ).fetchone()
                if (row is None or tuple(row) != expected
                        or current_bundle.manifest != expected_manifest):
                    raise PermissionError("recovered installation snapshot changed")
            handle.verify = verify
            item.handle, item.ready = handle, started.ready
        except Exception as exc:
            if handle is not None:
                handle.stop()
            item.state, item.error = ExecutionState.FAILED, f"{type(exc).__name__}: {exc}"
        finally:
            if kernel is not None:
                kernel.close()
            item.updated_at = datetime.now(UTC).isoformat()
            engine._persist(item, connection=conn)
