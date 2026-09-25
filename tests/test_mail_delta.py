from __future__ import annotations

from academicos.sources.mail.delta import collect_inbox_delta
from academicos.sources.mail.graph import GraphDeltaPage
from academicos.storage.db import connect_db, initialize_db


class FakeDeltaClient:
    def inbox_delta(self, *, delta_link=None, max_pages=50):
        assert max_pages == 50
        return GraphDeltaPage(
            items=(
                {
                    "id": "m1",
                    "subject": "CEG2136 update",
                    "receivedDateTime": "2026-09-25T13:00:00Z",
                    "lastModifiedDateTime": "2026-09-25T13:05:00Z",
                    "body": {"content": "CEG 2136 lecture room update"},
                    "hasAttachments": False,
                },
                {
                    "id": "m2",
                    "@removed": {"reason": "deleted"},
                },
            ),
            delta_link="https://graph.microsoft.com/v1.0/delta?$deltatoken=abc",
            complete=True,
        )

    def message_attachments(self, message_id):
        raise AssertionError("no attachments expected")


def make_conn():
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
        ("c1", "CEG2136", "Computer Architecture I", "20269", "A00"),
    )
    conn.commit()
    return conn


def test_delta_persists_changes_and_removed_tombstone() -> None:
    conn = make_conn()
    report = collect_inbox_delta(conn, FakeDeltaClient(), delta_link=None)

    assert report.complete is True
    assert report.delta_link and "$deltatoken=abc" in report.delta_link
    assert report.fetched == 2
    assert report.changed == 2
    assert report.removed == 1

    rows = conn.execute(
        "SELECT source_id, course_id, raw_json FROM source_items ORDER BY source_id"
    ).fetchall()
    assert rows[0]["source_id"] == "m365:m1"
    assert rows[0]["course_id"] == "c1"
    assert rows[1]["source_id"] == "m365:m2"
    assert rows[1]["course_id"] is None
    assert '"_academicOSState": "removed"' in rows[1]["raw_json"]
