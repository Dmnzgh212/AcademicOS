from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import academicos.sources.sync as sync_module
from academicos.sources.state import get_cursor, set_sync_state
from academicos.sources.sync import SyncReport, _announcement_state_key, _sync_brightspace
from academicos.storage.db import connect_db, initialize_db


class FakeBrightspaceClient:
    def my_enrollments(self, *, active_only: bool = True):  # noqa: ANN201
        assert active_only is True
        return [
            {
                "OrgUnit": {
                    "Id": 101,
                    "Code": "CEG2136-A00-20269",
                    "Name": "Computer Architecture I",
                    "Type": {"Name": "Course Offering"},
                }
            }
        ]

    def user_feed(self, *, since=None):  # noqa: ANN001, ANN201
        return []

    def whoami(self):  # noqa: ANN201
        return {"Identifier": "student"}


def _conn():  # noqa: ANN202
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
        ("c1", "CEG2136", "Computer Architecture I", "20269", "A00"),
    )
    conn.commit()
    return conn


def _patch_client(monkeypatch, client: FakeBrightspaceClient) -> None:  # noqa: ANN001
    monkeypatch.setattr(sync_module, "_brightspace_token", lambda *args, **kwargs: "token")
    monkeypatch.setattr(sync_module, "BrightspaceClient", lambda **kwargs: client)


def test_announcement_cursor_does_not_advance_when_announcement_fetch_failed(
    monkeypatch,
    tmp_path,
) -> None:  # noqa: ANN001
    conn = _conn()
    _patch_client(monkeypatch, FakeBrightspaceClient())

    def fake_collect(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return SimpleNamespace(
            changed=0,
            unchanged=0,
            datasets={"assignments": {"fetched": 0, "changed": 0, "unchanged": 0}},
            errors={"announcements": "500: simulated failure"},
        )

    monkeypatch.setattr(sync_module, "collect_course_data_capability_aware", fake_collect)

    _sync_brightspace(
        conn,
        SyncReport(),
        brightspace={"host": "https://example.invalid", "download_files": False},
        app_config={"timezone": "America/Toronto"},
        data_dir=tmp_path,
    )

    assert get_cursor(conn, _announcement_state_key("101")) is None


def test_successful_announcement_cursor_uses_request_start_and_legacy_cursor_as_input(
    monkeypatch,
    tmp_path,
) -> None:  # noqa: ANN001
    conn = _conn()
    _patch_client(monkeypatch, FakeBrightspaceClient())
    legacy = "2026-09-25T15:00:00+00:00"
    set_sync_state(conn, "brightspace:101:course", cursor=legacy)

    feed_start = datetime(2026, 9, 25, 16, 0, tzinfo=UTC)
    announcement_start = datetime(2026, 9, 25, 16, 1, tzinfo=UTC)

    class SequencedDateTime:
        values = [feed_start, announcement_start]

        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            assert tz is UTC
            return cls.values.pop(0)

    monkeypatch.setattr(sync_module, "datetime", SequencedDateTime)
    seen: dict[str, str | None] = {}

    def fake_collect(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        seen["since"] = kwargs.get("since")
        return SimpleNamespace(
            changed=0,
            unchanged=0,
            datasets={"announcements": {"fetched": 0, "changed": 0, "unchanged": 0}},
            errors={"grades": "403: simulated partial failure"},
        )

    monkeypatch.setattr(sync_module, "collect_course_data_capability_aware", fake_collect)

    _sync_brightspace(
        conn,
        SyncReport(),
        brightspace={"host": "https://example.invalid", "download_files": False},
        app_config={"timezone": "America/Toronto"},
        data_dir=tmp_path,
    )

    assert seen["since"] == legacy
    assert get_cursor(conn, "brightspace:activity_feed") == feed_start.isoformat()
    assert get_cursor(conn, _announcement_state_key("101")) == announcement_start.isoformat()
