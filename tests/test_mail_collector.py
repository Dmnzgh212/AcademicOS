from __future__ import annotations

from academicos.sources.mail.collector import collect_inbox
from academicos.storage.db import connect_db, initialize_db


class FakeMailClient:
    def inbox_messages(self, *, since=None, top=100, max_pages=20):
        return [
            {
                "id": "m1",
                "internetMessageId": "<m1@example.test>",
                "subject": "CEG2136 lecture moved",
                "receivedDateTime": "2026-09-25T13:00:00Z",
                "bodyPreview": "Room update",
                "body": {
                    "contentType": "html",
                    "content": "<p>CEG 2136 lecture is now in SITE 5084.</p>",
                },
                "hasAttachments": True,
                "webLink": "https://outlook.office.com/mail/m1",
            }
        ]

    def message_attachments(self, message_id):
        assert message_id == "m1"
        return [{"id": "a1", "name": "map.pdf", "size": 1234, "isInline": False}]


def make_conn():
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
        ("c1", "CEG2136", "Computer Architecture I", "20269", "A00"),
    )
    conn.commit()
    return conn


def test_mail_collection_is_incremental_and_links_unique_course() -> None:
    conn = make_conn()

    first = collect_inbox(conn, FakeMailClient())
    second = collect_inbox(conn, FakeMailClient())

    assert first.fetched == 1
    assert first.changed == 1
    assert first.attachment_metadata == 1
    assert second.changed == 0
    assert second.unchanged == 1

    row = conn.execute(
        "SELECT source_type, source_id, course_id, raw_text, raw_json FROM source_items"
    ).fetchone()
    assert row["source_type"] == "email"
    assert row["source_id"] == "m365:m1"
    assert row["course_id"] == "c1"
    assert "SITE 5084" in row["raw_text"]
    assert "_attachmentMetadata" in row["raw_json"]
