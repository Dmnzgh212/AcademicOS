from __future__ import annotations

import fnmatch
import hashlib
import json
import sqlite3
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PermissionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_write: list[str] = Field(default_factory=list)
    network_hosts: list[str] = Field(default_factory=list)
    localhost_ports: list[int] = Field(default_factory=list)

    @field_validator("localhost_ports")
    @classmethod
    def validate_ports(cls, value: list[int]) -> list[int]:
        for port in value:
            if not 1 <= port <= 65535:
                raise ValueError(f"invalid localhost port: {port}")
        return value


class WidgetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    namespace: str
    renderer: str = "list"
    width: int = Field(default=1, ge=1, le=3)
    height: int = Field(default=1, ge=1, le=3)
    limit: int = Field(default=8, ge=1, le=50)
    description: str | None = None

    @field_validator("renderer")
    @classmethod
    def validate_renderer(cls, value: str) -> str:
        allowed = {"list", "metric", "text", "table"}
        if value not in allowed:
            raise ValueError(f"unsupported renderer: {value}")
        return value


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    version: str
    description: str | None = None
    kind: list[str] = Field(default_factory=list)
    permissions: PermissionSpec = Field(default_factory=PermissionSpec)
    widgets: list[WidgetSpec] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for ch in cleaned):
            raise ValueError("plugin id must use lowercase letters, digits, '.', '_' or '-'")
        return cleaned

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: list[str]) -> list[str]:
        allowed = {"connector", "service", "widget", "analyzer"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unsupported plugin kind(s): {sorted(unknown)}")
        return value


@dataclass(frozen=True)
class PluginBundle:
    root: Path
    manifest: PluginManifest

    @property
    def seed_file(self) -> Path:
        return self.root / "seed.json"


class PluginRegistry:
    def __init__(self, root: str | Path = "lifehub_plugins") -> None:
        self.root = Path(root)

    def discover(self) -> tuple[PluginBundle, ...]:
        if not self.root.exists():
            return ()
        found: dict[str, PluginBundle] = {}
        for manifest_path in sorted(self.root.glob("*/plugin.toml")):
            payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = PluginManifest.model_validate(payload)
            if manifest.id in found:
                raise ValueError(f"duplicate plugin id: {manifest.id}")
            for widget in manifest.widgets:
                if not _namespace_allowed(widget.namespace, manifest.permissions.storage_write):
                    raise ValueError(
                        f"plugin {manifest.id} widget {widget.id} reads namespace "
                        f"{widget.namespace!r} that the plugin does not own"
                    )
            found[manifest.id] = PluginBundle(manifest_path.parent, manifest)
        return tuple(found.values())


def _namespace_allowed(namespace: str, allowed: Iterable[str]) -> bool:
    return any(namespace == prefix or namespace.startswith(prefix + ".") for prefix in allowed)


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

CREATE TABLE IF NOT EXISTS lifehub_workspace_widgets (
    workspace_id TEXT NOT NULL,
    plugin_id TEXT NOT NULL,
    widget_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    visible INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(workspace_id, plugin_id, widget_id)
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

    def scoped(self, manifest: PluginManifest) -> ScopedStore:
        return ScopedStore(self, manifest)

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
        observed = observed_at or now
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT OR IGNORE INTO lifehub_records(
                    plugin_id, namespace, record_key, payload_json,
                    observed_at, source, content_hash, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (plugin_id, namespace, record_key, canonical, observed, source, digest, now),
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

    def sync_workspace(self, bundles: Iterable[PluginBundle], workspace_id: str = "home") -> None:
        existing = {
            (row["plugin_id"], row["widget_id"])
            for row in self.conn.execute(
                "SELECT plugin_id, widget_id FROM lifehub_workspace_widgets WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()
        }
        position_row = self.conn.execute(
            "SELECT COALESCE(MAX(position), -1) AS p FROM lifehub_workspace_widgets WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        position = int(position_row["p"]) + 1
        with self.conn:
            for bundle in bundles:
                for widget in bundle.manifest.widgets:
                    key = (bundle.manifest.id, widget.id)
                    if key in existing:
                        continue
                    self.conn.execute(
                        """
                        INSERT INTO lifehub_workspace_widgets(
                            workspace_id, plugin_id, widget_id, position, width, height, visible
                        ) VALUES (?, ?, ?, ?, ?, ?, 1)
                        """,
                        (
                            workspace_id,
                            bundle.manifest.id,
                            widget.id,
                            position,
                            widget.width,
                            widget.height,
                        ),
                    )
                    position += 1

    def workspace_layout(self, workspace_id: str = "home") -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT plugin_id, widget_id, position, width, height, visible, config_json
            FROM lifehub_workspace_widgets
            WHERE workspace_id = ?
            ORDER BY position, plugin_id, widget_id
            """,
            (workspace_id,),
        ).fetchall()
        return [dict(row) | {"config": json.loads(row["config_json"])} for row in rows]

    def save_workspace_layout(self, items: list[dict[str, Any]], workspace_id: str = "home") -> None:
        with self.conn:
            for position, item in enumerate(items):
                self.conn.execute(
                    """
                    UPDATE lifehub_workspace_widgets
                    SET position = ?, width = ?, height = ?, visible = ?
                    WHERE workspace_id = ? AND plugin_id = ? AND widget_id = ?
                    """,
                    (
                        position,
                        max(1, min(3, int(item.get("width", 1)))),
                        max(1, min(3, int(item.get("height", 1)))),
                        1 if item.get("visible", True) else 0,
                        workspace_id,
                        str(item["plugin_id"]),
                        str(item["widget_id"]),
                    ),
                )

    def network_audit(self, *, plugin_id: str, method: str, host: str, path: str, allowed: bool) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO lifehub_network_audit(plugin_id, method, host, path, allowed, checked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (plugin_id, method, host, path, 1 if allowed else 0, datetime.now(UTC).isoformat()),
            )


class ScopedStore:
    def __init__(self, store: LifeStore, manifest: PluginManifest) -> None:
        self._store = store
        self._manifest = manifest

    def append(
        self,
        namespace: str,
        record_key: str,
        payload: dict[str, Any],
        *,
        observed_at: str | None = None,
        source: str | None = None,
    ) -> bool:
        if not _namespace_allowed(namespace, self._manifest.permissions.storage_write):
            raise PermissionError(
                f"plugin {self._manifest.id} cannot write namespace {namespace!r}"
            )
        return self._store.append_record(
            plugin_id=self._manifest.id,
            namespace=namespace,
            record_key=record_key,
            payload=payload,
            observed_at=observed_at,
            source=source,
        )


class EgressGateway:
    """Host-owned outbound gateway.

    The gateway deliberately supports retrieval-only HTTP semantics: GET/HEAD, no body,
    and manifest-declared destinations. It is a platform boundary for trusted/declarative
    plugins, not an OS sandbox for arbitrary Python code.
    """

    def __init__(self, store: LifeStore, manifest: PluginManifest) -> None:
        self.store = store
        self.manifest = manifest

    def authorize(self, url: str, *, method: str = "GET") -> None:
        parsed = urlparse(url)
        normalized_method = method.upper()
        host = (parsed.hostname or "").lower()
        allowed = False
        try:
            if normalized_method not in {"GET", "HEAD"}:
                raise PermissionError("LifeHub egress is retrieval-only; request bodies are not allowed")
            if parsed.username or parsed.password:
                raise PermissionError("credentials embedded in URLs are not allowed")
            if not host:
                raise PermissionError("network request has no host")
            if host in {"127.0.0.1", "localhost", "::1"}:
                if parsed.scheme != "http":
                    raise PermissionError("localhost service access must use http")
                port = parsed.port or 80
                if port not in self.manifest.permissions.localhost_ports:
                    raise PermissionError(f"localhost port {port} is not permitted")
            else:
                if parsed.scheme != "https":
                    raise PermissionError("external network access must use https")
                if not any(_host_matches(host, pattern) for pattern in self.manifest.permissions.network_hosts):
                    raise PermissionError(f"host {host!r} is not allowlisted")
            allowed = True
        finally:
            self.store.network_audit(
                plugin_id=self.manifest.id,
                method=normalized_method,
                host=host,
                path=parsed.path or "/",
                allowed=allowed,
            )

    def fetch(self, url: str, *, method: str = "GET", timeout: float = 15.0) -> bytes:
        self.authorize(url, method=method)
        request = Request(url, method=method.upper(), headers={"User-Agent": "LifeHub/0.1"})
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read()


def _host_matches(host: str, pattern: str) -> bool:
    normalized = pattern.strip().lower()
    if normalized.startswith("*."):
        suffix = normalized[2:]
        return host != suffix and host.endswith("." + suffix)
    return fnmatch.fnmatchcase(host, normalized)


class LifeHub:
    def __init__(
        self,
        *,
        db_path: str | Path = "data/lifehub.db",
        plugins_path: str | Path = "lifehub_plugins",
    ) -> None:
        self.registry = PluginRegistry(plugins_path)
        self.store = LifeStore(db_path)
        self.bundles = self.registry.discover()
        self.store.sync_workspace(self.bundles)

    def close(self) -> None:
        self.store.close()

    def bundle(self, plugin_id: str) -> PluginBundle:
        for bundle in self.bundles:
            if bundle.manifest.id == plugin_id:
                return bundle
        raise KeyError(plugin_id)

    def seed_declared_data(self) -> int:
        inserted = 0
        for bundle in self.bundles:
            if not bundle.seed_file.exists():
                continue
            payload = json.loads(bundle.seed_file.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError(f"{bundle.seed_file} must contain a JSON list")
            scoped = self.store.scoped(bundle.manifest)
            for item in payload:
                if not isinstance(item, dict):
                    raise ValueError(f"invalid seed item in {bundle.seed_file}")
                inserted += int(
                    scoped.append(
                        str(item["namespace"]),
                        str(item["record_key"]),
                        dict(item["payload"]),
                        observed_at=item.get("observed_at"),
                        source=item.get("source"),
                    )
                )
        return inserted
