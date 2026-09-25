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

    # More-specific source names are checked first so one course cannot be mistaken for
    # another source that happens to share a broad prefix.
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

    # Errors for sources that never reached sources_ok (for example authentication,
    # mapping, or an exception before a course completed) become explicit failed rows.
    for key in sorted(set(report.errors) - covered_errors):
        results.append(RunSourceResult(source_key=key, status="failed", error_count=1))

    return tuple(sorted(results, key=lambda item: item.source_key))


def _entry_status(sources: tuple[RunSourceResult, ...]) -> str:
    if not sources:
        return "empty"
    if any(item.status in {"partial", "failed"} for item in sources):
        return "partial"
    return "complete"


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
    ok_count = sum(item.status == "ok" for item in sources)
    partial_count = sum(item.status == "partial" for item in sources)
    failed_count = sum(item.status == "failed" for item in sources)
    status = _entry_status(sources)
    run_id = str(uuid4())

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
                max(0, report.changed),
                max(0, report.unchanged),
                max(0, report.downloaded_files),
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


def latest_sync_run(conn: sqlite3.Connection) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT id, mode, started_at, finished_at, status, source_count,
               ok_count, partial_count, failed_count, items_changed,
               items_unchanged, downloaded_files
        FROM sync_runs
        ORDER BY finished_at DESC
        LIMIT 1
        """
    ).fetchone()
    return dict(row) if row is not None else None


def run_tracked_sync(
    *,
    config_path: Path,
    db_path: Path | None = None,
    interactive_mail_auth: bool = False,
) -> tuple[SyncReport, RunLedgerEntry]:
    """Run the normal collector and persist a content-free completeness ledger entry."""
    started_at = datetime.now(UTC)
    report = sync_all(
        config_path=config_path,
        db_path=db_path,
        interactive_mail_auth=interactive_mail_auth,
    )
    finished_at = datetime.now(UTC)

    config = load_sync_config(config_path)
    app_config = config.get("app", {})
    effective_db = db_path or Path(app_config.get("database", "data/academicos.db"))
    conn = connect_db(effective_db)
    initialize_db(conn)
    try:
        entry = record_sync_run(
            conn,
            report,
            started_at=started_at,
            finished_at=finished_at,
            mode="full",
        )
    finally:
        conn.close()
    return report, entry
