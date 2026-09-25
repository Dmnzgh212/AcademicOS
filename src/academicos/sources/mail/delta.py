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
class MailDeltaReport:
    fetched: int
    changed: int
    unchanged: int
    removed: int
    attachment_metadata: int
    delta_link: str | None
    complete: bool
    attachment_message_ids: tuple[str, ...] = ()


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
    return "\n".join(part for part in (subject, body_text or preview) if part)


def _normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _course_id(conn: sqlite3.Connection, text: str) -> str | None:
    haystack = _normalize(text)
    matches = []
    for row in conn.execute("SELECT id, code FROM courses").fetchall():
        code = _normalize(row["code"])
        if code and code in haystack:
            matches.append(row["id"])
    return matches[0] if len(matches) == 1 else None


def collect_inbox_delta(
    conn: sqlite3.Connection,
    client: GraphMailClient,
    *,
    delta_link: str | None,
    include_attachment_metadata: bool = True,
    max_pages: int = 50,
) -> MailDeltaReport:
    page = client.inbox_delta(delta_link=delta_link, max_pages=max_pages)
    changed = 0
    unchanged = 0
    removed = 0
    attachment_metadata = 0
    attachment_message_ids: list[str] = []

    for message in page.items:
        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id:
            continue

        raw = dict(message)
        is_removed = isinstance(raw.get("@removed"), dict)
        if is_removed:
            raw["_academicOSState"] = "removed"
            removed += 1
        elif include_attachment_metadata and raw.get("hasAttachments"):
            try:
                metadata = client.message_attachments(message_id)
            except Exception:
                metadata = []
            raw["_attachmentMetadata"] = metadata
            attachment_metadata += len(metadata)
            if metadata:
                attachment_message_ids.append(message_id)

        text = "" if is_removed else _body_text(raw)
        source_key = f"m365:{message_id}"
        item = SourceItem(
            id=source_item_id(SourceType.EMAIL, source_key),
            source_type=SourceType.EMAIL,
            source_id=source_key,
            course_id=None if is_removed else _course_id(conn, text),
            source_url=raw.get("webLink") if isinstance(raw.get("webLink"), str) else None,
            source_timestamp=_parse_datetime(
                raw.get("lastModifiedDateTime") or raw.get("receivedDateTime")
            ),
            fetched_at=datetime.now(UTC),
            content_hash=canonical_hash(raw),
            raw_text=text or None,
            raw_json=raw,
        )
        if upsert_source_item(conn, item):
            changed += 1
        else:
            unchanged += 1

    return MailDeltaReport(
        fetched=len(page.items),
        changed=changed,
        unchanged=unchanged,
        removed=removed,
        attachment_metadata=attachment_metadata,
        delta_link=page.delta_link,
        complete=page.complete,
        attachment_message_ids=tuple(attachment_message_ids),
    )
