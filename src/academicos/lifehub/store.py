from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.registry import PluginRegistry


def namespace_allowed(namespace: str, patterns: Iterable[str]) -> bool:
    return any(namespace == prefix or namespace.startswith(prefix + ".") for prefix in patterns)


SCHEMA = """
CREATE TABLE IF NOT EXISTS lifehub_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    record_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    source TEXT,
    content_hash TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    UNIQUE(plugin_id, namespace, record_key, content_hash)
);
CREATE INDEX IF NOT EXISTS idx_lifehub_records_namespace
    ON lifehub_records(namespace, observed_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS lifehub_permission_grants (
    plugin_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    resource TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    PRIMARY KEY(plugin_id, capability, resource)
);

CREATE TABLE IF NOT EXISTS lifehub_installed_packages (
    plugin_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    approved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lifehub_managed_roots (
    path TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS lifehub_change_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_id TEXT NOT NULL,
    package_hash TEXT NOT NULL,
    extension_ref TEXT NOT NULL,
    namespace TEXT NOT NULL,
    record_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    base_record_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    decided_at TEXT,
    committed_record_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_lifehub_proposals_status
    ON lifehub_change_proposals(status, id);

CREATE TABLE IF NOT EXISTS lifehub_workspace_items (
    workspace_id TEXT NOT NULL,
    extension_ref TEXT NOT NULL,
    breakpoint TEXT NOT NULL DEFAULT 'lg',
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    visible INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(workspace_id, extension_ref, breakpoint)
);

CREATE TABLE IF NOT EXISTS lifehub_network_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_id TEXT NOT NULL,
    method TEXT NOT NULL,
    host TEXT NOT NULL,
    path TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    checked_at TEXT NOT NULL
);
"""


class LifeStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path) if str(path) != ":memory:" else Path(":memory:")
        if str(self.path) == ":memory:":
            self.conn = sqlite3.connect(":memory:")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def scoped(
        self, manifest: PluginManifest, *, verify: Callable[[], None] | None = None
    ) -> ScopedStore:
        return ScopedStore(self, manifest, verify=verify)

    def append_record(
        self,
        *,
        plugin_id: str,
        namespace: str,
        record_key: str,
        payload: dict[str, Any],
        observed_at: str | None = None,
        source: str | None = None,
    ) -> bool:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        now = datetime.now(UTC).isoformat()
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT OR IGNORE INTO lifehub_records(
                    plugin_id, namespace, record_key, payload_json,
                    observed_at, source, content_hash, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plugin_id,
                    namespace,
                    record_key,
                    canonical,
                    observed_at or now,
                    source,
                    digest,
                    now,
                ),
            )
        return cursor.rowcount > 0

    def latest_records(self, namespace: str, *, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT plugin_id, namespace, record_key, payload_json, observed_at, source, ingested_at
            FROM lifehub_records
            WHERE namespace = ?
            ORDER BY observed_at DESC, id DESC
            LIMIT ?
            """,
            (namespace, limit),
        ).fetchall()
        return [
            {
                "plugin_id": row["plugin_id"],
                "namespace": row["namespace"],
                "record_key": row["record_key"],
                "payload": json.loads(row["payload_json"]),
                "observed_at": row["observed_at"],
                "source": row["source"],
                "ingested_at": row["ingested_at"],
            }
            for row in rows
        ]

    def latest_record_id(self, namespace: str, record_key: str) -> int | None:
        row = self.conn.execute(
            "SELECT MAX(id) AS id FROM lifehub_records WHERE namespace=? AND record_key=?",
            (namespace, record_key),
        ).fetchone()
        return row["id"]

    def grant(self, plugin_id: str, capability: str, resource: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO lifehub_permission_grants(
                    plugin_id, capability, resource, granted_at
                ) VALUES (?, ?, ?, ?)
                """,
                (plugin_id, capability, resource, datetime.now(UTC).isoformat()),
            )

    def revoke(self, plugin_id: str, capability: str, resource: str) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM lifehub_permission_grants WHERE plugin_id=? AND capability=? AND resource=?",
                (plugin_id, capability, resource),
            )

    def is_granted(self, plugin_id: str, capability: str, namespace: str) -> bool:
        rows = self.conn.execute(
            "SELECT resource FROM lifehub_permission_grants WHERE plugin_id=? AND capability=?",
            (plugin_id, capability),
        ).fetchall()
        return namespace_allowed(namespace, (row["resource"] for row in rows))

    def grants(self, plugin_id: str | None = None) -> list[dict[str, str]]:
        if plugin_id is None:
            rows = self.conn.execute(
                "SELECT plugin_id, capability, resource, granted_at FROM lifehub_permission_grants "
                "ORDER BY plugin_id, capability, resource"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT plugin_id, capability, resource, granted_at FROM lifehub_permission_grants "
                "WHERE plugin_id=? ORDER BY capability, resource",
                (plugin_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def sync_workspace_extensions(
        self,
        registry: PluginRegistry,
        workspace_id: str = "home",
        breakpoint: str = "lg",
    ) -> None:
        existing = {
            row["extension_ref"]
            for row in self.conn.execute(
                "SELECT extension_ref FROM lifehub_workspace_items WHERE workspace_id=? AND breakpoint=?",
                (workspace_id, breakpoint),
            ).fetchall()
        }
        index = len(existing)
        with self.conn:
            for extension in registry.extensions("workspace.widget"):
                if extension.ref in existing:
                    continue
                config = extension.contribution.config
                if config.get("default_workspace", True) is False:
                    continue
                width = max(1, min(12, int(config.get("width", 4))))
                height = max(1, min(100, int(config.get("height", 3))))
                x = (index * 4) % 12
                y = (index * 4) // 12 * 3
                if x + width > 12:
                    x = 0
                    y += 3
                self.conn.execute(
                    """
                    INSERT INTO lifehub_workspace_items(
                        workspace_id, extension_ref, breakpoint, x, y, width, height, visible
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (workspace_id, extension.ref, breakpoint, x, y, width, height),
                )
                index += 1

    def workspace_layout(
        self, workspace_id: str = "home", breakpoint: str = "lg"
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT extension_ref, x, y, width, height, visible, config_json
            FROM lifehub_workspace_items
            WHERE workspace_id=? AND breakpoint=?
            ORDER BY y, x, extension_ref
            """,
            (workspace_id, breakpoint),
        ).fetchall()
        return [dict(row) | {"config": json.loads(row["config_json"])} for row in rows]

    def save_workspace_layout(
        self,
        items: list[dict[str, Any]],
        workspace_id: str = "home",
        breakpoint: str = "lg",
    ) -> None:
        with self.conn:
            for item in items:
                width = max(1, min(12, int(item.get("width", 4))))
                x = max(0, min(12 - width, int(item.get("x", 0))))
                self.conn.execute(
                    """
                    UPDATE lifehub_workspace_items
                    SET x=?, y=?, width=?, height=?, visible=?, config_json=?
                    WHERE workspace_id=? AND extension_ref=? AND breakpoint=?
                    """,
                    (
                        x,
                        max(0, int(item.get("y", 0))),
                        width,
                        max(1, min(100, int(item.get("height", 3)))),
                        1 if item.get("visible", True) else 0,
                        json.dumps(item.get("config", {}), separators=(",", ":")),
                        workspace_id,
                        str(item["extension_ref"]),
                        breakpoint,
                    ),
                )

    def network_audit(
        self, *, plugin_id: str, method: str, host: str, path: str, allowed: bool
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO lifehub_network_audit(plugin_id, method, host, path, allowed, checked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (plugin_id, method, host, path, 1 if allowed else 0, datetime.now(UTC).isoformat()),
            )


class ScopedStore:
    def __init__(
        self,
        store: LifeStore,
        manifest: PluginManifest,
        *,
        verify: Callable[[], None] | None = None,
    ) -> None:
        self._store = store
        self._manifest = manifest
        self._verify = verify

    def append(
        self,
        namespace: str,
        record_key: str,
        payload: dict[str, Any],
        *,
        observed_at: str | None = None,
        source: str | None = None,
    ) -> bool:
        self.assert_writable(namespace)
        return self._store.append_record(
            plugin_id=self._manifest.id,
            namespace=namespace,
            record_key=record_key,
            payload=payload,
            observed_at=observed_at,
            source=source,
        )

    def assert_writable(self, namespace: str) -> None:
        if self._verify is not None:
            self._verify()
        if not namespace_allowed(namespace, self._manifest.permissions.storage_write):
            raise PermissionError(
                f"plugin {self._manifest.id} cannot write namespace {namespace!r}"
            )

    def write_base(self, namespace: str, record_key: str) -> int | None:
        self.assert_writable(namespace)
        return self._store.latest_record_id(namespace, record_key)

    def read(self, namespace: str, *, limit: int = 8) -> list[dict[str, Any]]:
        if self._verify is not None:
            self._verify()
        if namespace_allowed(namespace, self._manifest.permissions.storage_write):
            return self._store.latest_records(namespace, limit=limit)
        requested = namespace_allowed(namespace, self._manifest.permissions.storage_read)
        granted = self._store.is_granted(self._manifest.id, "storage.read", namespace)
        if not (requested and granted):
            raise PermissionError(f"plugin {self._manifest.id} cannot read namespace {namespace!r}")
        return self._store.latest_records(namespace, limit=limit)
