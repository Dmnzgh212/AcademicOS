from __future__ import annotations

from typing import Any

from academicos.sources.mail.graph import GraphMailClient


class FakeResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "value": [
                {
                    "id": "m1",
                    "receivedDateTime": "2026-09-25T12:00:00Z",
                    "hasAttachments": False,
                }
            ]
        }


class RecordingSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, url: str, *, params=None, timeout: int = 30):  # noqa: ANN001, ANN201
        assert timeout == 30
        self.calls.append((url, params))
        return FakeResponse()


def test_inbox_probe_requests_metadata_only() -> None:
    session = RecordingSession()
    client = GraphMailClient(access_token="secret", session=session)

    items = client.inbox_probe(top=1)

    assert len(items) == 1
    assert len(session.calls) == 1
    url, params = session.calls[0]
    assert url.endswith("/me/mailFolders/inbox/messages")
    assert params is not None
    selected = set(str(params["$select"]).split(","))
    assert selected == {
        "id",
        "receivedDateTime",
        "lastModifiedDateTime",
        "hasAttachments",
    }
    forbidden = {"subject", "body", "bodyPreview", "from", "sender", "toRecipients", "ccRecipients"}
    assert selected.isdisjoint(forbidden)
