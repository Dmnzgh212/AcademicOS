from __future__ import annotations

from pathlib import Path

import requests

from academicos.sources.brightspace.collector import (
    collect_course_data,
    download_course_files,
    persist_dataset,
)
from academicos.storage.db import connect_db, initialize_db


class FakeResponse:
    def __init__(self, content: bytes, filename: str) -> None:
        self.content = content
        self.headers = {"Content-Disposition": f'attachment; filename="{filename}"'}


class FakeClient:
    def assignments(self, org_id):
        return [
            {
                "Id": 10,
                "Name": "Assignment 1",
                "DueDate": "2026-10-01T23:59:00Z",
                "Attachments": [{"FileId": 91, "FileName": "starter.zip"}],
            }
        ]

    def quizzes(self, org_id):
        return [{"Id": 20, "Name": "Quiz 1", "EndDate": "2026-10-03T20:00:00Z"}]

    def content_toc(self, org_id):
        return {
            "Modules": [
                {
                    "Id": 30,
                    "Title": "Week 1",
                    "Topics": [{"Id": 31, "Title": "slides.pdf", "TopicType": 1}],
                }
            ]
        }

    def grades(self, org_id):
        return {"Objects": [{"GradeObjectIdentifier": 40, "GradeObjectName": "A1"}]}

    def final_grade(self, org_id):
        return {"GradeObjectIdentifier": "final", "DisplayedGrade": "A-"}

    def calendar_events(self, org_id, *, start=None, end=None):
        return [{"Id": 50, "Title": "Midterm", "StartDateTime": start, "EndDateTime": end}]

    def due_items(self, *, org_ids_csv=None, start=None, end=None):
        return [{"Id": 60, "Title": "Due item", "DueDate": end}]

    def overdue_items(self, *, org_ids_csv=None):
        return []

    def updates(self, org_id):
        return {"Objects": [{"Id": 70, "Title": "Updated content"}]}

    def content_topic_file(self, org_id, topic_id):
        return FakeResponse(b"pdf-data", "../slides.pdf")

    def assignment_attachment(self, org_id, folder_id, file_id):
        return FakeResponse(b"zip-data", "starter.zip")


class PartiallyBlockedClient(FakeClient):
    def quizzes(self, org_id):
        response = requests.Response()
        response.status_code = 403
        response.url = "https://example.test/quizzes"
        raise requests.HTTPError("forbidden", response=response)


def make_conn():
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
        ("c1", "CEG2136", "Computer Architecture I", "20269", "A00"),
    )
    conn.commit()
    return conn


def test_persist_dataset_is_incremental() -> None:
    conn = make_conn()
    payload = [{"Id": 1, "Name": "Assignment", "DueDate": "2026-10-01T23:59:00Z"}]

    first = persist_dataset(
        conn,
        dataset="assignments",
        payload=payload,
        course_id="c1",
        org_unit_id="123",
    )
    second = persist_dataset(
        conn,
        dataset="assignments",
        payload=payload,
        course_id="c1",
        org_unit_id="123",
    )

    assert first == {"fetched": 1, "changed": 1, "unchanged": 0}
    assert second == {"fetched": 1, "changed": 0, "unchanged": 1}
    assert conn.execute("SELECT COUNT(*) FROM source_items").fetchone()[0] == 1


def test_course_collection_isolates_disabled_endpoints() -> None:
    conn = make_conn()
    report = collect_course_data(
        conn,
        PartiallyBlockedClient(),
        course_id="c1",
        org_unit_id="123",
        include={"assignments", "quizzes", "content", "grades"},
    )

    assert report.datasets["assignments"]["changed"] == 1
    assert report.datasets["content"]["changed"] == 1
    assert report.datasets["grades"]["changed"] == 1
    assert "quizzes" in report.errors
    assert "403" in report.errors["quizzes"]


def test_download_course_files_mirrors_content_and_assignment_attachments(tmp_path: Path) -> None:
    result = download_course_files(FakeClient(), org_unit_id="123", out_dir=tmp_path)

    assert result == {"downloaded": 2, "unchanged": 0, "failed": 0}
    assert (tmp_path / "content" / "31_slides.pdf").read_bytes() == b"pdf-data"
    assert (
        tmp_path / "assignments" / "10_Assignment 1" / "91_starter.zip"
    ).read_bytes() == b"zip-data"

    second = download_course_files(FakeClient(), org_unit_id="123", out_dir=tmp_path)
    assert second == {"downloaded": 0, "unchanged": 2, "failed": 0}
