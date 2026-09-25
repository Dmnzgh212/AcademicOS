from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from academicos.sources.state import get_cursor, set_sync_state
from academicos.sources.sync import (
    _announcement_cursor,
    _announcement_state_key,
    _course_specs,
    load_sync_config,
)
from academicos.storage.db import connect_db, initialize_db


def test_load_sync_config_preserves_course_source_mappings(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        """
[app]
timezone = "America/Toronto"
database = "data/test.db"

[brightspace]
enabled = true
host = "https://example.brightspace.com"

[[brightspace.courses]]
code = "CEG2136"
section = "A00"
org_id = "12345"
download_files = true

[mail]
enabled = false
client_id = "example-client-id"
""".strip(),
        encoding="utf-8",
    )

    loaded = load_sync_config(config)

    assert loaded["brightspace"]["host"] == "https://example.brightspace.com"
    assert loaded["brightspace"]["courses"][0]["code"] == "CEG2136"
    assert loaded["brightspace"]["courses"][0]["org_id"] == "12345"
    assert loaded["brightspace"]["courses"][0]["download_files"] is True
    assert loaded["mail"]["enabled"] is False


def _course_db():
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
        ("course-ceg", "CEG2136", "Computer Architecture I", "2026F", "A00"),
    )
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
        ("course-csi", "CSI2110", "Data Structures", "2026F", "A00"),
    )
    conn.commit()
    return conn


def test_course_specs_auto_discovers_org_ids_when_config_has_no_course_list() -> None:
    conn = _course_db()
    enrollments = [
        {
            "OrgUnit": {
                "Id": 101,
                "Code": "CEG2136-A00-20269",
                "Name": "Computer Architecture I",
                "Type": {"Name": "Course Offering"},
            }
        },
        {
            "OrgUnit": {
                "Id": 202,
                "Code": "CSI2110-A00-20269",
                "Name": "Data Structures",
                "Type": {"Name": "Course Offering"},
            }
        },
    ]

    specs, errors = _course_specs(
        conn,
        {"host": "https://example.brightspace.com", "download_files": True},
        enrollments,
    )

    assert errors == {}
    assert {(item["code"], item["org_id"]) for item in specs} == {
        ("CEG2136", "101"),
        ("CSI2110", "202"),
    }
    assert all(item["download_files"] is True for item in specs)


def test_course_specs_fills_missing_org_id_but_keeps_explicit_mapping() -> None:
    conn = _course_db()
    enrollments = [
        {
            "OrgUnit": {
                "Id": 101,
                "Code": "CEG2136-A00-20269",
                "Name": "Computer Architecture I",
                "Type": {"Name": "Course Offering"},
            }
        },
        {
            "OrgUnit": {
                "Id": 202,
                "Code": "CSI2110-A00-20269",
                "Name": "Data Structures",
                "Type": {"Name": "Course Offering"},
            }
        },
    ]
    config = {
        "courses": [
            {"code": "CEG2136", "section": "A00"},
            {"code": "CSI2110", "section": "A00", "org_id": "999"},
        ]
    }

    specs, errors = _course_specs(conn, config, enrollments)

    assert errors == {}
    by_code = {item["code"]: item for item in specs}
    assert by_code["CEG2136"]["org_id"] == "101"
    assert by_code["CSI2110"]["org_id"] == "999"


def test_sync_state_round_trip_can_be_used_as_incremental_cursor() -> None:
    conn = _course_db()
    cursor = "2026-09-25T15:00:00+00:00"

    set_sync_state(
        conn,
        "brightspace:101:course",
        cursor=cursor,
        metadata={"org_id": "101"},
        success_at=datetime(2026, 9, 25, 15, 0, tzinfo=UTC),
    )

    assert get_cursor(conn, "brightspace:101:course") == cursor
    assert get_cursor(conn, "missing") is None


def test_announcement_cursor_prefers_new_key_and_falls_back_to_legacy_key() -> None:
    conn = _course_db()
    legacy = "2026-09-25T14:00:00+00:00"
    current = "2026-09-25T15:00:00+00:00"

    set_sync_state(conn, "brightspace:101:course", cursor=legacy)
    assert _announcement_cursor(conn, "101") == legacy

    set_sync_state(conn, _announcement_state_key("101"), cursor=current)
    assert _announcement_cursor(conn, "101") == current
