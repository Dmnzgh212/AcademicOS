"""Durable proposals and explicit host commit decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.store import LifeStore, namespace_allowed


@dataclass(frozen=True)
class ProposedChange:
    namespace: str
    record_key: str
    payload: dict[str, Any]
    base_record_id: int | None


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ProposalService:
    def __init__(self, store: LifeStore) -> None:
        self.store = store

    def submit(
        self,
        plugin_id: str,
        package_hash: str,
        extension_ref: str,
        changes: list[ProposedChange],
    ) -> list[int]:
        ids: list[int] = []
        now = datetime.now(UTC).isoformat()
        conn = self.store.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            approved = conn.execute(
                "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
                (plugin_id,),
            ).fetchone()
            if approved is None or approved["content_hash"] != package_hash:
                raise PermissionError("package approval changed before proposal submission")
            for change in changes:
                payload = _canonical(change.payload)
                existing = conn.execute(
                    """SELECT id FROM lifehub_change_proposals
                    WHERE plugin_id=? AND package_hash=? AND extension_ref=? AND namespace=?
                      AND record_key=? AND payload_json=? AND base_record_id IS ?
                      AND status='pending' LIMIT 1""",
                    (
                        plugin_id,
                        package_hash,
                        extension_ref,
                        change.namespace,
                        change.record_key,
                        payload,
                        change.base_record_id,
                    ),
                ).fetchone()
                if existing:
                    ids.append(existing["id"])
                    continue
                cursor = conn.execute(
                    """INSERT INTO lifehub_change_proposals(
                        plugin_id, package_hash, extension_ref, namespace, record_key,
                        payload_json, base_record_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        plugin_id,
                        package_hash,
                        extension_ref,
                        change.namespace,
                        change.record_key,
                        payload,
                        change.base_record_id,
                        now,
                    ),
                )
                ids.append(cursor.lastrowid)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return ids

    def list(self, status: str = "pending") -> list[dict[str, Any]]:
        rows = self.store.conn.execute(
            "SELECT * FROM lifehub_change_proposals WHERE status=? ORDER BY id", (status,)
        ).fetchall()
        return [dict(row) | {"payload": json.loads(row["payload_json"])} for row in rows]

    def get(self, proposal_id: int) -> dict[str, Any]:
        row = self.store.conn.execute(
            "SELECT * FROM lifehub_change_proposals WHERE id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return dict(row) | {"payload": json.loads(row["payload_json"])}

    def reject(self, proposal_id: int) -> None:
        with self.store.conn:
            cursor = self.store.conn.execute(
                """UPDATE lifehub_change_proposals SET status='rejected', decided_at=?
                WHERE id=? AND status='pending'""",
                (datetime.now(UTC).isoformat(), proposal_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("proposal is missing or no longer pending")

    def approve(self, proposal_id: int, manifest: PluginManifest, package_hash: str) -> str:
        conn = self.store.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM lifehub_change_proposals WHERE id=?", (proposal_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                raise ValueError("proposal is missing or no longer pending")
            if row["plugin_id"] != manifest.id or row["package_hash"] != package_hash:
                raise PermissionError("proposal package does not match current approval")
            if not namespace_allowed(row["namespace"], manifest.permissions.storage_write):
                raise PermissionError("proposal namespace is no longer permitted")
            approved = conn.execute(
                "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
                (manifest.id,),
            ).fetchone()
            if approved is None or approved["content_hash"] != package_hash:
                raise PermissionError("package approval has changed")
            now = datetime.now(UTC).isoformat()
            latest = self.store.latest_record_id(row["namespace"], row["record_key"])
            if latest != row["base_record_id"]:
                conn.execute(
                    """UPDATE lifehub_change_proposals SET status='stale', decided_at=?
                    WHERE id=?""",
                    (now, proposal_id),
                )
                conn.commit()
                return "stale"
            payload = row["payload_json"]
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            cursor = conn.execute(
                """INSERT OR IGNORE INTO lifehub_records(
                    plugin_id, namespace, record_key, payload_json, observed_at,
                    source, content_hash, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    manifest.id,
                    row["namespace"],
                    row["record_key"],
                    payload,
                    now,
                    f"lifehub.proposal:{proposal_id}",
                    digest,
                    now,
                ),
            )
            if cursor.rowcount == 0:
                conn.execute(
                    """UPDATE lifehub_change_proposals
                    SET status='already_recorded', decided_at=? WHERE id=?""",
                    (now, proposal_id),
                )
                conn.commit()
                return "already_recorded"
            conn.execute(
                """UPDATE lifehub_change_proposals
                SET status='committed', decided_at=?, committed_record_id=? WHERE id=?""",
                (now, cursor.lastrowid, proposal_id),
            )
            conn.commit()
            return "committed"
        except BaseException:
            conn.rollback()
            raise
