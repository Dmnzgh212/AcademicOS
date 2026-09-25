from __future__ import annotations

from pathlib import Path

from academicos.sources.health import list_health, mark_failure, mark_success
from academicos.sources.manifest import manifest_current, record_manifest
from academicos.storage.db import connect_db, initialize_db


def make_conn():
    conn = connect_db(":memory:")
    initialize_db(conn)
    return conn


def test_health_resets_failure_count_after_success() -> None:
    conn = make_conn()
    mark_failure(conn, "mail:m365", "temporary error")
    mark_failure(conn, "mail:m365", "temporary error again")

    failed = list_health(conn)[0]
    assert failed.status == "error"
    assert failed.consecutive_failures == 2

    mark_success(conn, "mail:m365", changed=3, unchanged=7)
    healthy = list_health(conn)[0]
    assert healthy.status == "ok"
    assert healthy.consecutive_failures == 0
    assert healthy.items_changed == 3
    assert healthy.items_unchanged == 7
    assert healthy.last_error is None


def test_manifest_skips_existing_file_with_same_remote_fingerprint(tmp_path: Path) -> None:
    conn = make_conn()
    destination = tmp_path / "lecture.pdf"
    payload = b"academic-content"
    destination.write_bytes(payload)

    record_manifest(
        conn,
        source_key="brightspace:1:content:2",
        destination=destination,
        remote_fingerprint="fingerprint-v1",
        payload=payload,
    )

    assert manifest_current(
        conn,
        source_key="brightspace:1:content:2",
        destination=destination,
        remote_fingerprint="fingerprint-v1",
    )
    assert not manifest_current(
        conn,
        source_key="brightspace:1:content:2",
        destination=destination,
        remote_fingerprint="fingerprint-v2",
    )
