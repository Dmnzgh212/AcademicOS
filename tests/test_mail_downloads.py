from __future__ import annotations

import base64
import json
from pathlib import Path

from academicos.sources.mail.downloads import download_delta_attachments
from academicos.storage.db import connect_db, initialize_db


class FakeClient:
    calls = 0

    def message_attachment(self, message_id, attachment_id):
        self.calls += 1
        assert message_id == "m1"
        assert attachment_id == "a1"
        return {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "notes.pdf",
            "contentBytes": base64.b64encode(b"pdf-data").decode("ascii"),
        }


def make_conn():
    conn = connect_db(":memory:")
    initialize_db(conn)
    raw = {
        "id": "m1",
        "_attachmentMetadata": [
            {
                "id": "a1",
                "name": "notes.pdf",
                "size": 8,
                "isInline": False,
                "lastModifiedDateTime": "2026-09-25T12:00:00Z",
            }
        ],
    }
    conn.execute(
        """
        INSERT INTO source_items(
            id, source_type, source_id, fetched_at, content_hash, raw_json
        ) VALUES (?, 'email', ?, ?, ?, ?)
        """,
        ("s1", "m365:m1", "2026-09-25T12:00:00+00:00", "hash", json.dumps(raw)),
    )
    conn.commit()
    return conn


def test_delta_attachment_download_uses_manifest_on_second_run(tmp_path: Path) -> None:
    conn = make_conn()
    client = FakeClient()

    first = download_delta_attachments(
        conn,
        client,
        message_ids=("m1",),
        out_dir=tmp_path,
    )
    second = download_delta_attachments(
        conn,
        client,
        message_ids=("m1",),
        out_dir=tmp_path,
    )

    assert first["downloaded"] == 1
    assert second["unchanged"] == 1
    assert client.calls == 1
    assert len(list(tmp_path.rglob("*.pdf"))) == 1
