"""Explicit disclosure requests and a no-automatic-retry effect ledger."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.store import LifeStore


@dataclass(frozen=True)
class EffectRequest:
    kind: str
    destination: str
    purpose: str
    payload: dict[str, Any]


def _allowed(manifest: PluginManifest, kind: str, destination: str) -> bool:
    return any(
        item.kind == kind and item.destination == destination
        for item in manifest.permissions.effect_request
    )


class EffectService:
    def __init__(self, store: LifeStore) -> None:
        self.store = store

    def assert_requestable(self, manifest: PluginManifest, kind: str, destination: str) -> None:
        if not _allowed(manifest, kind, destination):
            raise PermissionError(
                f"effect {kind!r} to {destination!r} was not declared by {manifest.id}"
            )

    def submit(
        self,
        manifest: PluginManifest,
        package_hash: str,
        extension_ref: str,
        requests: list[EffectRequest],
    ) -> list[int]:
        conn = self.store.conn
        own_transaction = not conn.in_transaction
        if own_transaction:
            conn.execute("BEGIN IMMEDIATE")
        ids: list[int] = []
        try:
            approved = conn.execute(
                "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
                (manifest.id,),
            ).fetchone()
            if approved is None or approved["content_hash"] != package_hash:
                raise PermissionError("package approval changed before effect submission")
            for request in requests:
                self.assert_requestable(manifest, request.kind, request.destination)
                payload = json.dumps(
                    request.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                )
                identity = json.dumps(
                    [
                        manifest.id,
                        package_hash,
                        extension_ref,
                        request.kind,
                        request.destination,
                        request.purpose,
                        payload,
                    ],
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO lifehub_effect_requests(
                        request_hash, plugin_id, package_hash, extension_ref, kind,
                        destination, purpose, payload_json, requested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        digest,
                        manifest.id,
                        package_hash,
                        extension_ref,
                        request.kind,
                        request.destination,
                        request.purpose,
                        payload,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                if cursor.rowcount:
                    ids.append(cursor.lastrowid)
                else:
                    ids.append(
                        conn.execute(
                            "SELECT id FROM lifehub_effect_requests WHERE request_hash=?", (digest,)
                        ).fetchone()["id"]
                    )
            if own_transaction:
                conn.commit()
        except BaseException:
            if own_transaction:
                conn.rollback()
            raise
        return ids

    def get(self, request_id: int) -> dict[str, Any]:
        row = self.store.conn.execute(
            "SELECT * FROM lifehub_effect_requests WHERE id=?", (request_id,)
        ).fetchone()
        if row is None:
            raise KeyError(request_id)
        return dict(row) | {"payload": json.loads(row["payload_json"])}

    def list(self, status: str = "pending") -> list[dict[str, Any]]:
        rows = self.store.conn.execute(
            "SELECT id FROM lifehub_effect_requests WHERE status=? ORDER BY id", (status,)
        ).fetchall()
        return [self.get(row["id"]) for row in rows]

    def approve(self, request_id: int, manifest: PluginManifest, package_hash: str) -> None:
        conn = self.store.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM lifehub_effect_requests WHERE id=?", (request_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                raise ValueError("effect request is missing or no longer pending")
            if row["plugin_id"] != manifest.id or row["package_hash"] != package_hash:
                raise PermissionError("effect request package does not match approval")
            self.assert_requestable(manifest, row["kind"], row["destination"])
            approved = conn.execute(
                "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
                (manifest.id,),
            ).fetchone()
            if approved is None or approved["content_hash"] != package_hash:
                raise PermissionError("package approval changed")
            conn.execute(
                "UPDATE lifehub_effect_requests SET status='approved', approved_at=? WHERE id=?",
                (datetime.now(UTC).isoformat(), request_id),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    def reject(self, request_id: int) -> None:
        with self.store.conn:
            changed = self.store.conn.execute(
                """UPDATE lifehub_effect_requests SET status='rejected', resolved_at=?
                WHERE id=? AND status IN ('pending', 'approved')""",
                (datetime.now(UTC).isoformat(), request_id),
            )
            if changed.rowcount != 1:
                raise ValueError("effect request cannot be rejected in its current state")

    def dispatch(
        self,
        request_id: int,
        manifest: PluginManifest,
        package_hash: str,
        executor: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> str:
        request = self.get(request_id)
        if executor is None:
            if request["kind"] != "test.record":
                raise PermissionError("no registered executor for this effect kind")
            executor = self._fake_record
        conn = self.store.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM lifehub_effect_requests WHERE id=?", (request_id,)
            ).fetchone()
            if row is None or row["status"] != "approved":
                raise ValueError("effect request is not approved or was already attempted")
            if row["plugin_id"] != manifest.id or row["package_hash"] != package_hash:
                raise PermissionError("effect request package changed")
            self.assert_requestable(manifest, row["kind"], row["destination"])
            approved = conn.execute(
                "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
                (manifest.id,),
            ).fetchone()
            if approved is None or approved["content_hash"] != package_hash:
                raise PermissionError("package approval changed")
            request = dict(row) | {"payload": json.loads(row["payload_json"])}
            conn.execute(
                "UPDATE lifehub_effect_requests SET status='in_flight', attempted_at=? WHERE id=?",
                (datetime.now(UTC).isoformat(), request_id),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

        try:
            outcome = executor(request)
            result = json.dumps(outcome, sort_keys=True, separators=(",", ":"))
        except Exception:
            self._resolve(request_id, "unknown", None)
            return "unknown"
        self._resolve(request_id, "succeeded", result)
        return "succeeded"

    def mark_unknown(self, request_id: int) -> None:
        """Explicit recovery for an in-flight request after its worker has stopped."""
        self._resolve(request_id, "unknown", None)

    def _resolve(self, request_id: int, status: str, outcome: str | None) -> None:
        with self.store.conn:
            changed = self.store.conn.execute(
                """UPDATE lifehub_effect_requests
                SET status=?, outcome_json=?, resolved_at=?
                WHERE id=? AND status='in_flight'""",
                (status, outcome, datetime.now(UTC).isoformat(), request_id),
            )
            if changed.rowcount != 1:
                raise ValueError("effect request is not in flight")

    def _fake_record(self, request: dict[str, Any]) -> dict[str, Any]:
        with self.store.conn:
            self.store.conn.execute(
                """INSERT INTO lifehub_fake_effect_deliveries(request_id, payload_json, delivered_at)
                VALUES (?, ?, ?)""",
                (request["id"], request["payload_json"], datetime.now(UTC).isoformat()),
            )
        return {"fake_delivery_id": request["id"]}
