from academicos.sources.capabilities import record_failure, record_success
from academicos.sources.coverage import CORE_BRIGHTSPACE_ENDPOINTS, brightspace_coverage
from academicos.sources.health import mark_success
from academicos.storage.db import connect_db, initialize_db


def make_conn():
    conn = connect_db(":memory:")
    initialize_db(conn)
    return conn


def test_coverage_distinguishes_supported_blocked_attention_and_unknown() -> None:
    conn = make_conn()
    mark_success(conn, "brightspace:CEG2136-A00", metadata={"org_id": "99"})
    record_success(conn, "brightspace:99", "announcements", [])
    record_success(conn, "brightspace:99", "assignments", [])
    record_failure(conn, "brightspace:99", "overview", RuntimeError("broken"))

    rows = brightspace_coverage(conn)

    assert len(rows) == 1
    row = rows[0]
    assert row.label == "CEG2136-A00"
    assert row.supported == 2
    assert row.blocked == 0
    assert row.attention == 1
    assert row.unknown == len(CORE_BRIGHTSPACE_ENDPOINTS) - 3
    assert row.coverage == 2 / len(CORE_BRIGHTSPACE_ENDPOINTS)


def test_coverage_ignores_non_core_endpoint_rows() -> None:
    conn = make_conn()
    record_success(conn, "brightspace:99", "custom_future_endpoint", [])

    assert brightspace_coverage(conn) == []
