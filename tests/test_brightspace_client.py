from __future__ import annotations

from academicos.sources.brightspace.client import BrightspaceClient


class FakeResponse:
    def __init__(self, status_code: int, payload, headers=None) -> None:  # noqa: ANN001
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):  # noqa: ANN201
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.headers: dict[str, str] = {}
        self.responses = list(responses)
        self.calls: list[tuple[str, dict | None, int]] = []

    def get(self, url: str, *, params=None, timeout: int = 30):  # noqa: ANN001, ANN201
        self.calls.append((url, params, timeout))
        return self.responses.pop(0)


def test_news_uses_valence_endpoint_and_bearer_token() -> None:
    session = FakeSession([FakeResponse(200, [{"Id": 1, "Title": "Hello"}])])
    client = BrightspaceClient(
        host="https://example.brightspace.com/",
        bearer_token="secret",
        le_version="1.75",
        session=session,  # type: ignore[arg-type]
        sleep=lambda _: None,
    )

    result = client.news(987, since="2026-09-25T00:00:00Z")

    assert result[0]["Id"] == 1
    assert session.headers["Authorization"] == "Bearer secret"
    assert session.calls == [
        (
            "https://example.brightspace.com/d2l/api/le/1.75/987/news/",
            {"since": "2026-09-25T00:00:00Z"},
            30,
        )
    ]


def test_news_retries_429_using_retry_after() -> None:
    session = FakeSession(
        [
            FakeResponse(429, {}, {"Retry-After": "2"}),
            FakeResponse(200, [{"Id": 2}]),
        ]
    )
    sleeps: list[float] = []
    client = BrightspaceClient(
        host="https://example.brightspace.com",
        bearer_token="secret",
        session=session,  # type: ignore[arg-type]
        sleep=sleeps.append,
    )

    assert client.news("123") == [{"Id": 2}]
    assert sleeps == [2.0]
    assert len(session.calls) == 2


def test_calendar_events_sends_required_window_and_reads_object_list_page() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "Items": [{"CalendarEventId": 9, "Title": "Midterm"}],
                    "PagingInfo": {"HasMoreItems": False},
                },
            )
        ]
    )
    client = BrightspaceClient(
        host="https://example.brightspace.com",
        bearer_token="secret",
        le_version="1.75",
        session=session,  # type: ignore[arg-type]
        sleep=lambda _: None,
    )

    result = client.calendar_events(
        987,
        start="2026-08-26T00:00:00Z",
        end="2026-12-24T00:00:00Z",
    )

    assert result == [{"CalendarEventId": 9, "Title": "Midterm"}]
    assert session.calls == [
        (
            "https://example.brightspace.com/d2l/api/le/1.75/987/calendar/events/myEvents/",
            {
                "startDateTime": "2026-08-26T00:00:00Z",
                "endDateTime": "2026-12-24T00:00:00Z",
            },
            30,
        )
    ]
