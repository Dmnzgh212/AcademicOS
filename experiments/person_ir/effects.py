"""Host-owned fake effect ledger; explicit approval, one attempt, no automatic retry."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .authority import AuthorityRegistry, Capability
from .runtime import Intent


def _json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


@dataclass(frozen=True)
class Outcome:
    ok: bool
    detail: str


class EffectLedger:
    """Only trusted host code can register an executor; graphs return requests as data."""

    def __init__(
        self,
        path: str | Path,
        executor: Callable[[dict[str, Any]], Outcome] | None = None,
    ) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._executor = executor or self._fake_record
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS person_ir_effects (
                id INTEGER PRIMARY KEY, identity_hash TEXT NOT NULL UNIQUE,
                principal TEXT NOT NULL, domain TEXT NOT NULL,
                kind TEXT NOT NULL, destination TEXT NOT NULL, purpose TEXT NOT NULL,
                payload_json TEXT NOT NULL, sources_json TEXT NOT NULL,
                disclosures_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                outcome_json TEXT, trace_json TEXT,
                approved_capability_id TEXT, dispatch_capability_id TEXT
            );
            CREATE TABLE IF NOT EXISTS person_ir_fake_deliveries (
                request_id INTEGER PRIMARY KEY, payload_json TEXT NOT NULL
            );
        """)
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(person_ir_effects)")}
        for name in ("trace_json", "approved_capability_id", "dispatch_capability_id"):
            if name not in columns:
                self.conn.execute(f"ALTER TABLE person_ir_effects ADD COLUMN {name} TEXT")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> EffectLedger:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def request(self, intent: Intent, *, principal: str, domain: str) -> int:
        if intent.kind != "effect_request" or set(intent.parameters) != {
            "kind",
            "destination",
            "purpose",
        }:
            raise ValueError("only a complete effect request can be enqueued")
        kind, destination, purpose = (
            intent.parameters[name] for name in ("kind", "destination", "purpose")
        )
        if not all(
            type(item) is str and item for item in (principal, domain, kind, destination, purpose)
        ):
            raise ValueError("effect metadata must be nonempty strings")
        if (
            intent.label not in {"public", "protected"}
            or intent.label == "protected"
            or any(
                (target, reason) != (destination, purpose) for target, reason in intent.disclosures
            )
        ):
            raise PermissionError("protected payload requires a matching disclosure path")
        if intent.trace is None or any(
            origin.producer == "unverified-host" or origin.security_label is None
            for origin in intent.trace.evidence
        ):
            raise PermissionError("external effect requires host-labeled evidence")
        if any(
            origin.security_label == "protected" for origin in intent.trace.evidence
        ) and not any(
            release == (destination, "whole_value", purpose) for release in intent.trace.disclosures
        ):
            raise PermissionError("protected evidence requires explicit disclosure")
        payload = _json(intent.data)
        sources = _json(sorted(intent.sources))
        disclosures = _json(intent.disclosures)
        trace = _json(asdict(intent.trace)) if intent.trace else None
        identity = hashlib.sha256(
            _json(
                [
                    principal,
                    domain,
                    kind,
                    destination,
                    purpose,
                    payload,
                    sources,
                    disclosures,
                    trace,
                ]
            ).encode()
        ).hexdigest()
        with self.conn:
            self.conn.execute(
                """INSERT OR IGNORE INTO person_ir_effects(
                    identity_hash, principal, domain, kind, destination, purpose,
                    payload_json, sources_json, disclosures_json, trace_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    identity,
                    principal,
                    domain,
                    kind,
                    destination,
                    purpose,
                    payload,
                    sources,
                    disclosures,
                    trace,
                ),
            )
            row = self.conn.execute(
                "SELECT id FROM person_ir_effects WHERE identity_hash=?", (identity,)
            ).fetchone()
        return row["id"]

    def get(self, request_id: int) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM person_ir_effects WHERE id=?", (request_id,)
        ).fetchone()
        if row is None:
            raise KeyError(request_id)
        return dict(row) | {
            "payload": json.loads(row["payload_json"]),
            "sources": json.loads(row["sources_json"]),
            "disclosures": json.loads(row["disclosures_json"]),
            "trace": json.loads(row["trace_json"]) if row["trace_json"] else None,
            "outcome": json.loads(row["outcome_json"]) if row["outcome_json"] else None,
        }

    @staticmethod
    def _require(
        row: dict[str, Any],
        authority: AuthorityRegistry,
        handle: Capability,
        *,
        principal: str,
        domain: str,
        context: str | None,
    ) -> str:
        if row["principal"] != principal or row["domain"] != domain:
            raise PermissionError("request principal or domain mismatch")
        grant = authority.require(
            handle,
            principal=principal,
            domain=domain,
            operation="effect.dispatch",
            resource=_json([row["kind"], row["destination"]]),
            context=context,
        )
        return grant.capability_id

    def approve(
        self,
        request_id: int,
        authority: AuthorityRegistry,
        handle: Capability,
        *,
        principal: str,
        domain: str,
        context: str | None = None,
    ) -> None:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.get(request_id)
            grant_id = self._require(
                row, authority, handle, principal=principal, domain=domain, context=context
            )
            if row["status"] != "pending":
                raise ValueError("request is not pending")
            self.conn.execute(
                "UPDATE person_ir_effects SET status='approved', approved_capability_id=? WHERE id=?",
                (grant_id, request_id),
            )
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def reject(self, request_id: int) -> None:
        with self.conn:
            changed = self.conn.execute(
                "UPDATE person_ir_effects SET status='rejected' WHERE id=? AND status IN ('pending', 'approved')",
                (request_id,),
            )
            if changed.rowcount != 1:
                raise ValueError("request is no longer rejectable")

    def dispatch(
        self,
        request_id: int,
        authority: AuthorityRegistry,
        handle: Capability,
        *,
        principal: str,
        domain: str,
        context: str | None = None,
    ) -> str:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.get(request_id)
            grant_id = self._require(
                row, authority, handle, principal=principal, domain=domain, context=context
            )
            if row["status"] != "approved":
                raise ValueError("request is not approved or was already attempted")
            self.conn.execute(
                "UPDATE person_ir_effects SET status='in_flight', dispatch_capability_id=? WHERE id=?",
                (grant_id, request_id),
            )
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

        try:
            outcome = self._executor(row)
            if not isinstance(outcome, Outcome):
                raise TypeError("executor must return an Outcome")
        except Exception:
            self._resolve(request_id, "unknown", None)
            return "unknown"
        status = "succeeded" if outcome.ok else "failed"
        self._resolve(request_id, status, _json({"detail": outcome.detail}))
        return status

    def mark_unknown(self, request_id: int) -> None:
        """Operator action after confirming an interrupted executor is stopped."""
        self._resolve(request_id, "unknown", None)

    def _resolve(self, request_id: int, status: str, outcome_json: str | None) -> None:
        with self.conn:
            changed = self.conn.execute(
                "UPDATE person_ir_effects SET status=?, outcome_json=? WHERE id=? AND status='in_flight'",
                (status, outcome_json, request_id),
            )
            if changed.rowcount != 1:
                raise ValueError("request is not in flight")

    def _fake_record(self, row: dict[str, Any]) -> Outcome:
        with self.conn:
            self.conn.execute(
                "INSERT INTO person_ir_fake_deliveries(request_id, payload_json) VALUES (?, ?)",
                (row["id"], row["payload_json"]),
            )
        return Outcome(True, "local fake delivery")
