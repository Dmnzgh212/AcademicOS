from __future__ import annotations

import requests

from academicos.sources.staged_sync import STAGED_BRIGHTSPACE_ENDPOINTS, stage_brightspace
from academicos.storage.db import connect_db, initialize_db


class FakeBrightspaceClient:
    def __init__(self, *, fail_assignments: bool = False) -> None:
        self.fail_assignments = fail_assignments
        self.assignment_calls = 0
        self.calendar_calls: list[tuple[object, str, str]] = []

    def my_enrollments(self, *, active_only: bool = True):  # noqa: ANN201
        assert active_only is True
        return [
            {
                "OrgUnit": {
                    "Id": 12345,
                    "Code": "CEG2136-A00-20269",
                    "Name": "Computer Architecture I",
                    "Type": {"Name": "Course Offering"},
                }
            }
        ]

    def whoami(self):  # noqa: ANN201
        return {"Identifier": "student"}

    def news(self, org_id):  # noqa: ANN001, ANN201
        return [{"Id": 1, "Title": "Welcome", "Body": {"Text": "Hello"}}]

    def assignments(self, org_id):  # noqa: ANN001, ANN201
        self.assignment_calls += 1
        if self.fail_assignments:
            response = requests.Response()
            response.status_code = 404
            response.url = "https://example.invalid/assignments"
            raise requests.HTTPError("not found", response=response)
        return [{"Id": 2, "Name": "A1"}]

    def quizzes(self, org_id):  # noqa: ANN001, ANN201
        return [{"QuizId": 3, "Name": "Q1"}]

    def content_toc(self, org_id):  # noqa: ANN001, ANN201
        return [{"ModuleId": 4, "Title": "Week 1"}]

    def grades(self, org_id):  # noqa: ANN001, ANN201
        return [{"GradeObjectIdentifier": 5, "Name": "A1"}]

    def calendar_events(self, org_id, *, start: str, end: str):  # noqa: ANN001, ANN201
        self.calendar_calls.append((org_id, start, end))
        return [{"CalendarEventId": 6, "Title": "Lecture"}]

    def updates(self, org_id):  # noqa: ANN001, ANN201
        return [{"Id": 7, "Title": "Update"}]


def _conn():  # noqa: ANN202
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
        ("c1", "CEG2136", "Computer Architecture I", "20269", "A00"),
    )
    conn.execute(
        """
        INSERT INTO course_sessions(
            id, course_id, session_type, weekday,
            start_time, end_time, start_date, end_date,
            location, delivery_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "s1",
            "c1",
            "lecture",
            1,
            "14:30",
            "15:50",
            "2026-09-09",
            "2026-12-09",
            "SITE",
            "in_person",
        ),
    )
    conn.commit()
    return conn


def test_staged_sync_does_not_advance_state_or_create_calendar_candidates() -> None:
    conn = _conn()
    client = FakeBrightspaceClient()

    report = stage_brightspace(conn, client, brightspace={})

    assert report.courses_checked == 1
    assert report.endpoints_checked == len(STAGED_BRIGHTSPACE_ENDPOINTS)
    assert report.endpoints_skipped == 0
    assert report.errors == {}
    assert report.cursors_advanced == 0
    assert report.downloaded_files == 0
    assert client.calendar_calls == [
        ("12345", "2026-08-26T00:00:00Z", "2026-12-24T00:00:00Z")
    ]
    assert conn.execute("SELECT COUNT(*) FROM sync_state").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM file_manifest").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM candidate_events").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM endpoint_capabilities").fetchone()[0] == len(
        STAGED_BRIGHTSPACE_ENDPOINTS
    )


def test_staged_sync_respects_endpoint_cooldown_after_404() -> None:
    conn = _conn()
    client = FakeBrightspaceClient(fail_assignments=True)

    first = stage_brightspace(conn, client, brightspace={})
    second = stage_brightspace(conn, client, brightspace={})

    assert client.assignment_calls == 1
    assert first.endpoints_checked == len(STAGED_BRIGHTSPACE_ENDPOINTS)
    assert "brightspace:CEG2136-A00:assignments" in first.errors
    assert second.endpoints_checked == len(STAGED_BRIGHTSPACE_ENDPOINTS) - 1
    assert second.endpoints_skipped == 1
