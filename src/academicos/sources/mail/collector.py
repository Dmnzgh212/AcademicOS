from __future__ import annotations

import html
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from academicos.calendar.models import SourceItem, SourceType
from academicos.sources.mail.graph import GraphMailClient
from academicos.sources.store import canonical_hash, source_item_id, upsert_source_item


@dataclass(frozen=True)
class MailCollectionReport:
    fetched: int
    changed: int
    unchanged: int
    attachment_metadata: int


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _body_text(message: dict[str, Any]) -> str:
    subject = str(message.get("subject") or "").strip()
    body = message.get("body")
    body_value = body.get("content", "") if isinstance(body, dict) else ""
    body_text = re.sub(r"<[^>]+>", " ", str(body_value))
    body_text = " ".join(html.unescape(body_text).split())
    preview = " ".join(str(message.get("bodyPreview") or "").split())

    parts = [part for part in (subject, body_text or preview) if part]
    return "\n".join(parts)


def _normalize_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _infer_course_id(conn: sqlite3.Connection, text: str) -> str | None:
    haystack = _normalize_code(text)
    matches: list[str] = []
    for row in conn.execute("SELECT id, code FROM courses").fetchall():
        code = _normalize_code(row["code"])
        if code and code in haystack:
            matches.append(row["id"])
    return matches[0] if len(matches) == 1 else None


def collect_inbox(
    conn: sqlite3.Connection,
    client: GraphMailClient,
    *,
    since: str | None = None,
    include_attachment_metadata: bool = True,
    max_pages: int = 20,
) -> MailCollectionReport:
    """Collect Inbox mail into local source_items without changing the mailbox."""
    messages = client.inbox_messages(since=since, max_pages=max_pages)
    changed = 0
    unchanged = 0
    attachment_metadata = 0

    for message in messages:
        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id:
            continue

        raw = dict(message)
        if include_attachment_metadata and message.get("hasAttachments"):
            try:
                attachments = client.message_attachments(message_id)
            except Exception:
                attachments = []
            raw["_attachmentMetadata"] = attachments
            attachment_metadata += len(attachments)

        text = _body_text(raw)
        course_id = _infer_course_id(conn, text)
        source_key = f"m365:{message_id}"
        item = SourceItem(
            id=source_item_id(SourceType.EMAIL, source_key),
            source_type=SourceType.EMAIL,
            source_id=source_key,
            course_id=course_id,
            source_url=raw.get("webLink") if isinstance(raw.get("webLink"), str) else None,
            source_timestamp=_parse_datetime(raw.get("receivedDateTime")),
            fetched_at=datetime.now(UTC),
            content_hash=canonical_hash(raw),
            raw_text=text or None,
            raw_json=raw,
        )
        if upsert_source_item(conn, item):
            changed += 1
        else:
            unchanged += 1

    return MailCollectionReport(
        fetched=len(messages),
        changed=changed,
        unchanged=unchanged,
        attachment_metadata=attachment_metadata,
    )
