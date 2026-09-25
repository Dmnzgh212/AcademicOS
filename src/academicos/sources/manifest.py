from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class ManifestEntry:
    source_key: str
    local_path: str
    remote_fingerprint: str | None
    local_sha256: str | None
    size_bytes: int | None
    etag: str | None
    last_modified: str | None
    last_checked_at: str
    last_downloaded_at: str | None


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_manifest(conn: sqlite3.Connection, source_key: str) -> ManifestEntry | None:
    row = conn.execute(
        "SELECT * FROM file_manifest WHERE source_key = ?",
        (source_key,),
    ).fetchone()
    if row is None:
        return None
    return ManifestEntry(
        source_key=row["source_key"],
        local_path=row["local_path"],
        remote_fingerprint=row["remote_fingerprint"],
        local_sha256=row["local_sha256"],
        size_bytes=row["size_bytes"],
        etag=row["etag"],
        last_modified=row["last_modified"],
        last_checked_at=row["last_checked_at"],
        last_downloaded_at=row["last_downloaded_at"],
    )


def manifest_current(
    conn: sqlite3.Connection,
    *,
    source_key: str,
    destination: Path,
    remote_fingerprint: str | None,
) -> bool:
    entry = get_manifest(conn, source_key)
    if entry is None or not destination.exists():
        return False
    if remote_fingerprint is None or entry.remote_fingerprint != remote_fingerprint:
        return False
    try:
        stat = destination.stat()
    except OSError:
        return False
    if entry.size_bytes is not None and stat.st_size != entry.size_bytes:
        return False
    return True


def record_manifest(
    conn: sqlite3.Connection,
    *,
    source_key: str,
    destination: Path,
    remote_fingerprint: str | None,
    payload: bytes,
    etag: str | None = None,
    last_modified: str | None = None,
) -> None:
    now = datetime.now(UTC).isoformat()
    with conn:
        conn.execute(
            """
            INSERT INTO file_manifest(
                source_key, local_path, remote_fingerprint, local_sha256,
                size_bytes, etag, last_modified, last_checked_at, last_downloaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                local_path=excluded.local_path,
                remote_fingerprint=excluded.remote_fingerprint,
                local_sha256=excluded.local_sha256,
                size_bytes=excluded.size_bytes,
                etag=excluded.etag,
                last_modified=excluded.last_modified,
                last_checked_at=excluded.last_checked_at,
                last_downloaded_at=excluded.last_downloaded_at
            """,
            (
                source_key,
                str(destination),
                remote_fingerprint,
                sha256_bytes(payload),
                len(payload),
                etag,
                last_modified,
                now,
                now,
            ),
        )


def touch_manifest(conn: sqlite3.Connection, source_key: str) -> None:
    with conn:
        conn.execute(
            "UPDATE file_manifest SET last_checked_at = ? WHERE source_key = ?",
            (datetime.now(UTC).isoformat(), source_key),
        )
