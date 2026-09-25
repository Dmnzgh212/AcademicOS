from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class GraphDeltaPage:
    items: tuple[dict, ...]
    delta_link: str | None
    complete: bool


class GraphMailClient:
    """Minimal GET-only Microsoft Graph mail client for uOttawa/M365 mail acquisition."""

    def __init__(
        self,
        *,
        access_token: str,
        session: requests.Session | None = None,
        base_url: str = "https://graph.microsoft.com/v1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "AcademicOS/0.1",
            }
        )

    def _get_url(self, url: str, params: dict[str, Any] | None = None) -> dict:
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        return self._get_url(f"{self.base_url}{path}", params=params)

    @staticmethod
    def _message_select() -> str:
        return ",".join(
            [
                "id",
                "internetMessageId",
                "subject",
                "receivedDateTime",
                "sentDateTime",
                "lastModifiedDateTime",
                "from",
                "sender",
                "toRecipients",
                "ccRecipients",
                "bodyPreview",
                "body",
                "hasAttachments",
                "importance",
                "isRead",
                "webLink",
            ]
        )

    def me(self) -> dict:
        return self._get("/me", {"$select": "id,displayName,mail,userPrincipalName"})

    def inbox_messages(
        self,
        *,
        since: str | None = None,
        top: int = 100,
        max_pages: int = 20,
    ) -> list[dict]:
        """List Inbox messages, following Graph pagination with a bounded page count."""
        params: dict[str, Any] = {
            "$select": self._message_select(),
            "$orderby": "receivedDateTime desc",
            "$top": min(max(top, 1), 1000),
        }
        if since:
            params["$filter"] = f"receivedDateTime ge {since}"

        url = f"{self.base_url}/me/mailFolders/inbox/messages"
        items: list[dict] = []
        page = 0
        while url and page < max_pages:
            data = self._get_url(url, params=params if page == 0 else None)
            batch = data.get("value", [])
            if isinstance(batch, list):
                items.extend(item for item in batch if isinstance(item, dict))
            next_url = data.get("@odata.nextLink")
            url = next_url if isinstance(next_url, str) else ""
            params = None
            page += 1
        return items

    def inbox_delta(
        self,
        *,
        delta_link: str | None = None,
        max_pages: int = 50,
    ) -> GraphDeltaPage:
        """Return Inbox changes and the next durable Graph deltaLink.

        The first call starts a delta session. Subsequent calls should pass the exact
        opaque deltaLink returned by Graph. The cursor is considered durable only when
        the full page chain reaches ``@odata.deltaLink``. If ``max_pages`` is exhausted,
        ``complete`` is False and callers must not advance their stored cursor.
        """
        if delta_link:
            url = delta_link
            params = None
        else:
            url = f"{self.base_url}/me/mailFolders/inbox/messages/delta"
            params = {"$select": self._message_select()}

        items: list[dict] = []
        final_delta: str | None = None
        page = 0

        while url and page < max_pages:
            data = self._get_url(url, params=params if page == 0 and not delta_link else None)
            batch = data.get("value", [])
            if isinstance(batch, list):
                items.extend(item for item in batch if isinstance(item, dict))

            delta = data.get("@odata.deltaLink")
            if isinstance(delta, str) and delta:
                final_delta = delta
                url = ""
                break

            next_url = data.get("@odata.nextLink")
            url = next_url if isinstance(next_url, str) else ""
            params = None
            page += 1

        return GraphDeltaPage(
            items=tuple(items),
            delta_link=final_delta,
            complete=final_delta is not None,
        )

    def message_attachments(self, message_id: str) -> list[dict]:
        data = self._get(
            f"/me/messages/{message_id}/attachments",
            {"$select": "id,name,contentType,size,isInline,lastModifiedDateTime"},
        )
        value = data.get("value", [])
        return value if isinstance(value, list) else []

    def message_attachment(self, message_id: str, attachment_id: str) -> dict:
        """Fetch one attachment object. File attachments include base64 contentBytes."""
        return self._get(f"/me/messages/{message_id}/attachments/{attachment_id}")
