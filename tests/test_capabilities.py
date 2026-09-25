from __future__ import annotations

from datetime import UTC, datetime, timedelta

import requests

from academicos.sources.brightspace.capability_collect import (
    collect_course_data_capability_aware,
)
from academicos.sources.capabilities import (
    capability_rows,
    record_failure,
    record_success,
    response_shape,
    should_probe,
)
from academicos.storage.db import connect_db, initialize_db, schema_version


def make_conn():
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
        ("c1", "CEG2136", "Computer Architecture I", "20269", "A00"),
    )
    conn.commit()
    return conn


def http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response.url = "https://example.invalid/endpoint"
    return requests.HTTPError(f"HTTP {status}", response=response)


def test_fresh_schema_is_v5_and_has_capability_table() -> None:
    conn = make_conn()
    assert schema_version(conn) == 5
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='endpoint_capabilities'"
    ).fetchone()
    assert row is not None


def test_v4_database_migrates_to_v5() -> None:
    conn = connect_db(":memory:")
    conn.execute("CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO schema_meta(key, value) VALUES ('schema_version', '4')")
    conn.commit()

    initialize_db(conn)

    assert schema_version(conn) == 5
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='endpoint_capabilities'"
    ).fetchone()


def test_response_shape_contains_structure_not_values() -> None:
    shape = response_shape([{"Id": 123, "Secret": "do-not-copy"}])
    assert shape == {"kind": "list", "count": 1, "item_keys": ["Id", "Secret"]}
    assert "do-not-copy" not in str(shape)


def test_unsupported_and_forbidden_endpoints_have_cooldowns() -> None:
    conn = make_conn()
    now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)

    record_failure(conn, "brightspace:1", "overview", http_error(404), now=now)
    assert not should_probe(conn, "brightspace:1", "overview", now=now + timedelta(days=1))
    assert should_probe(conn, "brightspace:1", "overview", now=now + timedelta(days=31))

    record_failure(conn, "brightspace:1", "grades", http_error(403), now=now)
    assert not should_probe(conn, "brightspace:1", "grades", now=now + timedelta(hours=1))
    assert should_probe(conn, "brightspace:1", "grades", now=now + timedelta(hours=13))


def test_auth_errors_are_not_cached_as_unavailable() -> None:
    conn = make_conn()
    now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    record_failure(conn, "brightspace:1", "grades", http_error(401), now=now)
    assert should_probe(conn, "brightspace:1", "grades", now=now)


def test_success_clears_previous_cooldown() -> None:
    conn = make_conn()
    now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    record_failure(conn, "brightspace:1", "assignments", http_error(404), now=now)
    record_success(
        conn,
        "brightspace:1",
        "assignments",
        [{"Id": 1, "Name": "Assignment"}],
        now=now + timedelta(days=31),
    )
    row = capability_rows(conn)[0]
    assert row["status"] == "supported"
    assert row["next_probe_at"] is None
    assert row["response_shape"]["item_keys"] == ["Id", "Name"]


class MissingAssignmentsClient:
    def __init__(self) -> None:
        self.calls = 0

    def assignments(self, org_id):
        self.calls += 1
        raise http_error(404)


def test_capability_aware_collector_stops_repeated_unsupported_calls() -> None:
    conn = make_conn()
    client = MissingAssignmentsClient()

    first = collect_course_data_capability_aware(
        conn,
        client,
        course_id="c1",
        org_unit_id="99",
        include={"assignments"},
    )
    second = collect_course_data_capability_aware(
        conn,
        client,
        course_id="c1",
        org_unit_id="99",
        include={"assignments"},
    )

    assert client.calls == 1
    assert "assignments" in first.errors
    assert "skipped:assignments" in second.datasets
