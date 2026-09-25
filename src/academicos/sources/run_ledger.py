from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from academicos.sources.sync import SyncReport, load_sync_config, sync_all
from academicos.storage.db import connect_db, initialize_db


@dataclass(frozen=True)
class RunSourceResult:
    source_key: str
    status: str
    error_count: int


@dataclass(frozen=True)
class RunLedgerEntry:
    run_id: str
    status: str
    source_count: int
    ok_count: int
    partial_count: int
    failed_count: int


def classify_report_sources(report: SyncReport) -> tuple[RunSourceResult, ...]:
    """Convert a sync report into source-level completeness without copying source payloads."""
    successful = list(dict.fromkeys(report.sources_ok))
    results: list[RunSourceResult] = []
    covered_errors: set[str] = set()

    for source in sorted(successful, key=len, reverse=True):
        related = [
            key
            for key in report.errors
            if key == source or key.startswith(f"{source}:")
        ]
        covered_errors.update(related)
        results.append(
            RunSourceResult(
                source_key=source,
                status="partial" if related else "ok",
                error_count=len(related),
            )
        )

    for key in sorted(set(report.errors) - covered_errors):
        results.append(RunSourceResult(source_key=key, status="failed", error_count=1))

    return tuple(sorted(results, key=lambda item: item.source_key))


def _entry_status(sources: tuple[RunSourceResult, ...]) -> str:
    if not sources:
        return "empty"
    if all(item.status == "failed" for item in sources):
        return "failed"
    if any(item.status in {"partial", "failed"} for item in sources):
        return "partial"
    return "complete"


def _insert_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    mode: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    sources: tuple[RunSourceResult, ...],
    changed: int = 0,
    unchanged: int = 0,
    downloaded_files: int = 0,
) -> RunLedgerEntry:
    ok_count = sum(item.status == "ok" for item in sources)
    partial_count = sum(item.status == "partial" for item in sources)
    failed_count = sum(item.status == "failed" for item in sources)

    with conn:
        conn.execute(
            """
            INSERT INTO sync_runs(
                id, mode, started_at, finished_at, status, source_count,
                ok_count, partial_count, failed_count, items_changed,
                items_unchanged, downloaded_files
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                mode,
                started_at.astimezone(UTC).isoformat(),
                finished_at.astimezone(UTC).isoformat(),
                status,
                len(sources),
                ok_count,
                partial_count,
                failed_count,
                max(0, changed),
                max(0, unchanged),
                max(0, downloaded_files),
            ),
        )
        conn.executemany(
            """
            INSERT INTO sync_run_sources(run_id, source_key, status, error_count)
            VALUES (?, ?, ?, ?)
            """,
            [
                (run_id, item.source_key, item.status, item.error_count)
                for item in sources
            ],
        )

    return RunLedgerEntry(
        run_id=run_id,
        status=status,
        source_count=len(sources),
        ok_count=ok_count,
        partial_count=partial_count,
        failed_count=failed_count,
    )


def record_sync_run(
    conn: sqlite3.Connection,
    report: SyncReport,
    *,
    started_at: datetime,
    finished_at: datetime | None = None,
    mode: str = "full",
) -> RunLedgerEntry:
    finished_at = finished_at or datetime.now(UTC)
    sources = classify_report_sources(report)
    return _insert_run(
        conn,
        run_id=str(uuid4()),
        mode=mode,
        started_at=started_at,
        finished_at=finished_at,
        status=_entry_status(sources),
        sources=sources,
        changed=report.changed,
        unchanged=report.unchanged,
        downloaded_files=report.downloaded_files,
    )


def record_failed_sync_run(
    conn: sqlite3.Connection,
    *,
    started_at: datetime,
    finished_at: datetime | None = None,
    mode: str = "full",
    source_key: str = "sync",
) -> RunLedgerEntry:
    """Record a top-level sync failure without persisting exception text or source content."""
    finished_at = finished_at or datetime.now(UTC)
    sources = (RunSourceResult(source_key=source_key, status="failed", error_count=1),)
    return _insert_run(
        conn,
        run_id=str(uuid4()),
        mode=mode,
        started_at=started_at,
        finished_at=finished_at,
        status="failed",
        sources=sources,
    )


def latest_sync_run(conn: sqlite3.Connection) -> dict[str, object] | None:
    rows = list_sync_runs(conn, limit=1)
    return rows[0] if rows else None


def list_sync_runs(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
) -> tuple[dict[str, object], ...]:
    safe_limit = max(1, min(int(limit), 100))
    rows = conn.execute(
        """
        SELECT id, mode, started_at, finished_at, status, source_count,
               ok_count, partial_count, failed_count, items_changed,
               items_unchanged, downloaded_files
        FROM sync_runs
        ORDER BY finished_at DESC
        LIMIT ?
        """,
        (safe_limit,),
    ).fetchall()
    return tuple(dict(row) for row in rows)


def sync_run_sources(
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[dict[str, object], ...]:
    rows = conn.execute(
        """
        SELECT source_key, status, error_count
        FROM sync_run_sources
        WHERE run_id = ?
        ORDER BY source_key
        """,
        (run_id,),
    ).fetchall()
    return tuple(dict(row) for row in rows)


def run_tracked_sync(
    *,
    config_path: Path,
    db_path: Path | None = None,
    interactive_mail_auth: bool = False,
) -> tuple[SyncReport, RunLedgerEntry]:
    """Run the normal collector and persist a content-free completeness ledger entry."""
    config = load_sync_config(config_path)
    app_config = config.get("app", {})
    effective_db = db_path or Path(app_config.get("database", "data/academicos.db"))
    conn = connect_db(effective_db)
    initialize_db(conn)
    started_at = datetime.now(UTC)

    try:
        try:
            report = sync_all(
                config_path=config_path,
                db_path=db_path,
                interactive_mail_auth=interactive_mail_auth,
            )
        except Exception:
            record_failed_sync_run(
                conn,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                mode="full",
            )
            raise

        entry = record_sync_run(
            conn,
            report,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            mode="full",
        )
        return report, entry
    finally:
        conn.close()
