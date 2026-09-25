from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import academicos.sources.run_ledger as run_ledger
from academicos.sources.run_ledger import (
    latest_sync_run,
    list_sync_runs,
    record_sync_run,
    run_tracked_sync,
    sync_run_sources,
)
from academicos.sources.sync import SyncReport
from academicos.storage.db import connect_db, initialize_db


def _conn():
    conn = connect_db(":memory:")
    initialize_db(conn)
    return conn


def test_all_failed_sources_classify_run_as_failed() -> None:
    conn = _conn()
    entry = record_sync_run(
        conn,
        SyncReport(errors={"brightspace": "auth failed", "mail": "auth failed"}),
        started_at=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
        finished_at=datetime(2026, 9, 25, 12, 1, tzinfo=UTC),
    )

    assert entry.status == "failed"
    assert entry.failed_count == 2
    assert entry.ok_count == 0


def test_mixed_source_results_classify_run_as_partial() -> None:
    conn = _conn()
    entry = record_sync_run(
        conn,
        SyncReport(
            changed=3,
            sources_ok=["brightspace:101", "mail:m365"],
            errors={"brightspace:101:grades": "403"},
        ),
        started_at=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
        finished_at=datetime(2026, 9, 25, 12, 1, tzinfo=UTC),
    )

    assert entry.status == "partial"
    assert entry.ok_count == 1
    assert entry.partial_count == 1
    assert entry.failed_count == 0


def test_history_and_source_rows_are_queryable_newest_first() -> None:
    conn = _conn()
    first = record_sync_run(
        conn,
        SyncReport(sources_ok=["brightspace:101"]),
        started_at=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
        finished_at=datetime(2026, 9, 25, 12, 1, tzinfo=UTC),
    )
    second = record_sync_run(
        conn,
        SyncReport(sources_ok=["brightspace:101", "mail:m365"], changed=2),
        started_at=datetime(2026, 9, 25, 13, 0, tzinfo=UTC),
        finished_at=datetime(2026, 9, 25, 13, 1, tzinfo=UTC),
    )

    history = list_sync_runs(conn, limit=10)
    assert [row["id"] for row in history] == [second.run_id, first.run_id]
    assert latest_sync_run(conn)["id"] == second.run_id
    assert [row["source_key"] for row in sync_run_sources(conn, second.run_id)] == [
        "brightspace:101",
        "mail:m365",
    ]


def test_top_level_sync_exception_records_failed_run(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    database = tmp_path / "academicos.db"
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            [
                "[app]",
                f'database = "{database.as_posix()}"',
                "[brightspace]",
                "enabled = false",
                "[mail]",
                "enabled = false",
            ]
        ),
        encoding="utf-8",
    )

    def explode(**kwargs):  # noqa: ANN003, ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(run_ledger, "sync_all", explode)

    with pytest.raises(RuntimeError, match="boom"):
        run_tracked_sync(config_path=config)

    conn = connect_db(database)
    initialize_db(conn)
    try:
        latest = latest_sync_run(conn)
        assert latest is not None
        assert latest["status"] == "failed"
        sources = sync_run_sources(conn, str(latest["id"]))
        assert sources == ({"source_key": "sync", "status": "failed", "error_count": 1},)
    finally:
        conn.close()
