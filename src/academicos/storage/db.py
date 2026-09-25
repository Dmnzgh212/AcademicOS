from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
MIGRATIONS_PATH = Path(__file__).with_name("migrations")
LATEST_SCHEMA_VERSION = 5


def connect_db(path: str | Path) -> sqlite3.Connection:
    """Open a SQLite database with AcademicOS safety defaults."""
    if str(path) != ":memory:":
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        target = str(db_path)
    else:
        target = ":memory:"

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _has_schema_meta(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'schema_meta'
        """
    ).fetchone()
    return row is not None


def schema_version(conn: sqlite3.Connection) -> int:
    if not _has_schema_meta(conn):
        raise RuntimeError("AcademicOS schema is not initialized")
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        raise RuntimeError("AcademicOS schema is missing schema_version")
    return int(row["value"])


def _migration_path(target_version: int) -> Path:
    matches = sorted(MIGRATIONS_PATH.glob(f"{target_version:03d}_*.sql"))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one migration for schema v{target_version}, found {len(matches)}"
        )
    return matches[0]


def initialize_db(conn: sqlite3.Connection) -> None:
    """Create or migrate the AcademicOS database to the latest schema."""
    if not _has_schema_meta(conn):
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
        return

    current = schema_version(conn)
    if current > LATEST_SCHEMA_VERSION:
        raise RuntimeError(
            f"database schema v{current} is newer than this AcademicOS build "
            f"(latest supported: v{LATEST_SCHEMA_VERSION})"
        )

    while current < LATEST_SCHEMA_VERSION:
        target = current + 1
        migration = _migration_path(target)
        conn.executescript(migration.read_text(encoding="utf-8"))
        conn.commit()
        current = schema_version(conn)

    if current != LATEST_SCHEMA_VERSION:
        raise RuntimeError(
            f"schema migration stopped at v{current}; expected v{LATEST_SCHEMA_VERSION}"
        )
