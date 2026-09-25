from __future__ import annotations

import json

import requests

from academicos.sources.mail.graph import GraphMailClient


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = 0

    def get(self, url, params=None, timeout=30):
        self.calls += 1
        return self.responses.pop(0)


def response(status: int, payload: dict, **headers) -> requests.Response:
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers)
    result._content = json.dumps(payload).encode("utf-8")
    result.url = "https://graph.microsoft.com/v1.0/me"
    return result


def test_graph_retries_429_using_retry_after() -> None:
    session = FakeSession(
        [
            response(429, {"error": "throttled"}, **{"Retry-After": "2"}),
            response(200, {"id": "user-1"}),
        ]
    )
    sleeps = []
    client = GraphMailClient(
        access_token="token",
        session=session,
        sleep=sleeps.append,
    )

    assert client.me()["id"] == "user-1"
    assert session.calls == 2
    assert sleeps == [2.0]


def test_graph_retries_transient_503_with_exponential_fallback() -> None:
    session = FakeSession(
        [
            response(503, {"error": "unavailable"}),
            response(200, {"id": "user-1"}),
        ]
    )
    sleeps = []
    client = GraphMailClient(
        access_token="token",
        session=session,
        sleep=sleeps.append,
    )

    assert client.me()["id"] == "user-1"
    assert sleeps == [1.0]
