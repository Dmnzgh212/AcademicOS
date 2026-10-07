"""Persistence owned by the optional reference Web shell.

This module is deliberately outside the LifeHub platform store. Workspace layout
is presentation state, not engine state.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from academicos.lifehub.registry import PluginRegistry


_SCHEMA = """
CREATE TABLE IF NOT EXISTS lifehub_reference_web_workspace_items (
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
"""


class ReferenceWorkspaceStore:
    """Shell-owned layout persistence backed by the caller's local SQLite database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.executescript(_SCHEMA)
        self._migrate_legacy_layout()
        self.conn.commit()

    def sync_extensions(
        self,
        registry: PluginRegistry,
        workspace_id: str = "home",
        breakpoint: str = "lg",
    ) -> tuple[str, ...]:
        existing = {
            row["extension_ref"]
            for row in self.conn.execute(
                """
                SELECT extension_ref
                FROM lifehub_reference_web_workspace_items
                WHERE workspace_id=? AND breakpoint=?
                """,
                (workspace_id, breakpoint),
            ).fetchall()
        }
        invalid: list[str] = []
        index = len(existing)
        with self.conn:
            for extension in registry.extensions("workspace.widget"):
                if extension.ref in existing:
                    continue
                config = extension.contribution.config
                if config.get("default_workspace", True) is False:
                    continue
                try:
                    width = max(1, min(12, int(config.get("width", 4))))
                    height = max(1, min(100, int(config.get("height", 3))))
                except (TypeError, ValueError, OverflowError):
                    invalid.append(extension.ref)
                    continue
                x = (index * 4) % 12
                y = (index * 4) // 12 * 3
                if x + width > 12:
                    x = 0
                    y += 3
                self.conn.execute(
                    """
                    INSERT INTO lifehub_reference_web_workspace_items(
                        workspace_id, extension_ref, breakpoint, x, y, width, height, visible
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (workspace_id, extension.ref, breakpoint, x, y, width, height),
                )
                index += 1
        return tuple(invalid)

    def layout(
        self, workspace_id: str = "home", breakpoint: str = "lg"
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT extension_ref, x, y, width, height, visible, config_json
            FROM lifehub_reference_web_workspace_items
            WHERE workspace_id=? AND breakpoint=?
            ORDER BY y, x, extension_ref
            """,
            (workspace_id, breakpoint),
        ).fetchall()
        return [dict(row) | {"config": json.loads(row["config_json"])} for row in rows]

    def save_layout(
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
                    UPDATE lifehub_reference_web_workspace_items
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

    def _migrate_legacy_layout(self) -> None:
        legacy = self.conn.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='lifehub_workspace_items'
            """
        ).fetchone()
        if legacy is None:
            return
        with self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO lifehub_reference_web_workspace_items(
                    workspace_id, extension_ref, breakpoint, x, y,
                    width, height, visible, config_json
                )
                SELECT workspace_id, extension_ref, breakpoint, x, y,
                       width, height, visible, config_json
                FROM lifehub_workspace_items
                """
            )
