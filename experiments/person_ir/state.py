"""Host-side durable proposals with an ordinary SQLite compare-and-swap commit."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .authority import AuthorityRegistry, Capability
from .runtime import Intent


def _json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StateSnapshot:
    namespace: str
    key: str
    version: int
    content_hash: str | None
    value: Any


class VersionedState:
    """The trusted host owns this connection; IR code receives only JSON snapshots."""

    def __init__(self, path: str | Path) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._snapshots: dict[int, StateSnapshot] = {}
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS person_ir_state (
                namespace TEXT NOT NULL, record_key TEXT NOT NULL, version INTEGER NOT NULL,
                content_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
                PRIMARY KEY (namespace, record_key)
            );
            CREATE TABLE IF NOT EXISTS person_ir_proposals (
                id INTEGER PRIMARY KEY, identity_hash TEXT NOT NULL UNIQUE,
                principal TEXT NOT NULL, domain TEXT NOT NULL,
                namespace TEXT NOT NULL, record_key TEXT NOT NULL,
                base_version INTEGER NOT NULL, base_hash TEXT,
                payload_json TEXT NOT NULL, sources_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', committed_version INTEGER,
                trace_json TEXT, authority_id TEXT
            );
        """)
        columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(person_ir_proposals)")
        }
        for name in ("trace_json", "authority_id"):
            if name not in columns:
                self.conn.execute(f"ALTER TABLE person_ir_proposals ADD COLUMN {name} TEXT")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> VersionedState:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def read(self, namespace: str, key: str) -> StateSnapshot:
        row = self.conn.execute(
            "SELECT version, content_hash, payload_json FROM person_ir_state WHERE namespace=? AND record_key=?",
            (namespace, key),
        ).fetchone()
        snapshot = StateSnapshot(
            namespace,
            key,
            row["version"] if row else 0,
            row["content_hash"] if row else None,
            json.loads(row["payload_json"]) if row else None,
        )
        self._snapshots[id(snapshot)] = snapshot
        return snapshot

    def prepare(
        self, intent: Intent, snapshot: StateSnapshot, *, principal: str, domain: str
    ) -> int:
        if intent.kind != "commit_request":
            raise ValueError("only a commit request can create a proposal")
        namespace, key = intent.parameters["namespace"], intent.parameters["key"]
        if not all(type(part) is str and part for part in (namespace, key, principal, domain)):
            raise ValueError("invalid proposal target or principal")
        if self._snapshots.get(id(snapshot)) is not snapshot or (
            snapshot.namespace,
            snapshot.key,
        ) != (namespace, key):
            raise PermissionError("proposal requires a host-issued snapshot for its target")
        if snapshot.version and _hash(_json(snapshot.value)) != snapshot.content_hash:
            raise PermissionError("snapshot was modified after reading")
        payload = _json(intent.data)
        sources = _json(sorted(intent.sources))
        trace = _json(asdict(intent.trace)) if intent.trace else None
        identity = _hash(
            _json(
                [
                    principal,
                    domain,
                    namespace,
                    key,
                    snapshot.version,
                    snapshot.content_hash,
                    payload,
                    sources,
                    trace,
                ]
            )
        )
        with self.conn:
            self.conn.execute(
                """INSERT OR IGNORE INTO person_ir_proposals (
                    identity_hash, principal, domain, namespace, record_key, base_version,
                    base_hash, payload_json, sources_json, trace_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    identity,
                    principal,
                    domain,
                    namespace,
                    key,
                    snapshot.version,
                    snapshot.content_hash,
                    payload,
                    sources,
                    trace,
                ),
            )
            row = self.conn.execute(
                "SELECT id FROM person_ir_proposals WHERE identity_hash=?", (identity,)
            ).fetchone()
        return row["id"]

    def proposal(self, proposal_id: int) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM person_ir_proposals WHERE id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return dict(row) | {
            "payload": json.loads(row["payload_json"]),
            "sources": json.loads(row["sources_json"]),
            "trace": json.loads(row["trace_json"]) if row["trace_json"] else None,
        }

    def reject(self, proposal_id: int) -> None:
        with self.conn:
            changed = self.conn.execute(
                "UPDATE person_ir_proposals SET status='rejected' WHERE id=? AND status='pending'",
                (proposal_id,),
            )
            if changed.rowcount != 1:
                raise ValueError("proposal is no longer pending")

    def commit(
        self,
        proposal_id: int,
        authority: AuthorityRegistry,
        handle: Capability,
        *,
        principal: str,
        domain: str,
        context: str | None = None,
    ) -> str:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            proposal = self.proposal(proposal_id)
            if proposal["principal"] != principal or proposal["domain"] != domain:
                raise PermissionError("proposal principal or domain mismatch")
            resource = _json([proposal["namespace"], proposal["record_key"]])
            grant = authority.require(
                handle,
                principal=principal,
                domain=domain,
                operation="state.commit",
                resource=resource,
                context=context,
            )
            if proposal["status"] == "committed":
                self.conn.commit()
                return "already_committed"
            if proposal["status"] != "pending":
                raise ValueError("proposal is no longer pending")
            current = self.conn.execute(
                "SELECT version, content_hash FROM person_ir_state WHERE namespace=? AND record_key=?",
                (proposal["namespace"], proposal["record_key"]),
            ).fetchone()
            version = current["version"] if current else 0
            content_hash = current["content_hash"] if current else None
            if (version, content_hash) != (proposal["base_version"], proposal["base_hash"]):
                self.conn.execute(
                    "UPDATE person_ir_proposals SET status='stale' WHERE id=?", (proposal_id,)
                )
                self.conn.commit()
                return "stale"
            next_version = version + 1
            payload = proposal["payload_json"]
            self.conn.execute(
                """INSERT INTO person_ir_state(namespace, record_key, version, content_hash, payload_json)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(namespace, record_key) DO UPDATE SET
                     version=excluded.version, content_hash=excluded.content_hash,
                     payload_json=excluded.payload_json""",
                (
                    proposal["namespace"],
                    proposal["record_key"],
                    next_version,
                    _hash(payload),
                    payload,
                ),
            )
            self.conn.execute(
                "UPDATE person_ir_proposals SET status='committed', committed_version=?, authority_id=? WHERE id=?",
                (next_version, grant.capability_id, proposal_id),
            )
            self.conn.commit()
            return "committed"
        except BaseException:
            self.conn.rollback()
            raise
