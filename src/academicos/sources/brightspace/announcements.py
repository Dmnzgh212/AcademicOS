from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from uuid import UUID, uuid5

from academicos.calendar.events import (
    CandidateConflictError,
    CandidateTransitionError,
    accept_candidate_event,
    persist_candidate_event,
)
from academicos.calendar.extract import extract_candidates_from_text
from academicos.calendar.models import Evidence, SourceItem, SourceType
from academicos.sources.store import (
    canonical_hash,
    delete_pending_candidates_for_source,
    evidence_id,
    source_item_id,
    upsert_evidence,
    upsert_source_item,
)

ACTIVITY_NAMESPACE = UUID("4e991cca-fb6c-4a16-b72f-651668c3d4ac")


class _HTMLTextExtractor(HTMLParser):
    BLOCK_TAGS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())


@dataclass(frozen=True)
class NormalizedAnnouncement:
    source_id: str
    title: str
    body: str
    published_at: datetime
    raw: dict


def _parse_datetime(value: object) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _rich_text(value: object) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return str(value).strip()

    plain = value.get("Text")
    if isinstance(plain, str) and plain.strip():
        return plain.strip()

    html = value.get("Html")
    if isinstance(html, str) and html.strip():
        parser = _HTMLTextExtractor()
        parser.feed(html)
        return parser.text()
    return ""


def normalize_announcement(raw: dict) -> NormalizedAnnouncement:
    title = str(raw.get("Title") or raw.get("title") or "Untitled announcement").strip()
    body = _rich_text(raw.get("Body") or raw.get("body"))
    published_at = (
        _parse_datetime(raw.get("StartDate"))
        or _parse_datetime(raw.get("CreatedDate"))
        or _parse_datetime(raw.get("PublicationDate"))
        or _parse_datetime(raw.get("LastModifiedDate"))
        or datetime.now(timezone.utc)
    )

    identifier = (
        raw.get("Id")
        or raw.get("NewsId")
        or raw.get("ID")
        or raw.get("Identifier")
    )
    if identifier is None:
        identifier = canonical_hash(
            {
                "title": title,
                "body": body,
                "published_at": published_at.isoformat(),
            }
        )[:24]

    return NormalizedAnnouncement(
        source_id=str(identifier),
        title=title,
        body=body,
        published_at=published_at,
        raw=raw,
    )


def _activity_id(source_item: str) -> str:
    return str(uuid5(ACTIVITY_NAMESPACE, f"announcement|{source_item}"))


def _record_activity(
    conn: sqlite3.Connection,
    *,
    course_id: str,
    source_item: str,
    title: str,
    occurred_at: datetime,
) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO activity_feed(id, course_id, source_item_id, kind, title, occurred_at)
            VALUES (?, ?, ?, 'announcement', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                occurred_at=excluded.occurred_at
            """,
            (
                _activity_id(source_item),
                course_id,
                source_item,
                title,
                occurred_at.isoformat(),
            ),
        )


def ingest_announcements(
    conn: sqlite3.Connection,
    announcements: list[dict],
    *,
    course_id: str,
    org_unit_id: str | int,
    fetched_at: datetime | None = None,
    timezone_name: str = "America/Toronto",
    auto_accept: bool = False,
    auto_threshold: float = 0.98,
) -> dict[str, int]:
    """Normalize, deduplicate, extract, and optionally accept Brightspace announcements."""
    fetched_at = fetched_at or datetime.now(timezone.utc)
    summary = {
        "fetched": len(announcements),
        "changed": 0,
        "unchanged": 0,
        "candidates": 0,
        "auto_accepted": 0,
        "auto_skipped": 0,
    }

    for raw in announcements:
        normalized = normalize_announcement(raw)
        external_id = f"news:{org_unit_id}:{normalized.source_id}"
        item_id = source_item_id(SourceType.BRIGHTSPACE, external_id)
        raw_text = f"{normalized.title}\n\n{normalized.body}".strip()
        content_hash = canonical_hash(
            {
                "title": normalized.title,
                "body": normalized.body,
                "published_at": normalized.published_at.isoformat(),
            }
        )

        source_item = SourceItem(
            id=item_id,
            source_type=SourceType.BRIGHTSPACE,
            source_id=external_id,
            course_id=course_id,
            source_timestamp=normalized.published_at,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_text=raw_text,
            raw_json=normalized.raw,
        )
        changed = upsert_source_item(conn, source_item)
        if not changed:
            summary["unchanged"] += 1
            continue

        summary["changed"] += 1
        delete_pending_candidates_for_source(conn, item_id)

        ev_id = evidence_id(item_id, "Title+Body")
        upsert_evidence(
            conn,
            Evidence(
                id=ev_id,
                source_item_id=item_id,
                excerpt=raw_text[:4000],
                field_path="Title+Body",
            ),
        )
        _record_activity(
            conn,
            course_id=course_id,
            source_item=item_id,
            title=normalized.title,
            occurred_at=normalized.published_at,
        )

        candidates = extract_candidates_from_text(
            conn,
            source_item_id=item_id,
            content_hash=content_hash,
            course_id=course_id,
            title=normalized.title,
            text=normalized.body,
            published_at=normalized.published_at,
            timezone_name=timezone_name,
        )
        for candidate in candidates:
            persist_candidate_event(conn, candidate, evidence_ids=(ev_id,))
            summary["candidates"] += 1
            if not auto_accept or candidate.confidence < auto_threshold:
                continue
            try:
                accept_candidate_event(
                    conn,
                    candidate.id,
                    automatic=True,
                    auto_threshold=auto_threshold,
                )
                summary["auto_accepted"] += 1
            except (
                CandidateConflictError,
                CandidateTransitionError,
                NotImplementedError,
                ValueError,
            ):
                summary["auto_skipped"] += 1

    return summary


def sync_announcements(
    conn: sqlite3.Connection,
    client,
    *,
    course_id: str,
    org_unit_id: str | int,
    since: str | None = None,
    timezone_name: str = "America/Toronto",
    auto_accept: bool = False,
) -> dict[str, int]:
    raw = client.news(org_unit_id, since=since)
    return ingest_announcements(
        conn,
        raw,
        course_id=course_id,
        org_unit_id=org_unit_id,
        timezone_name=timezone_name,
        auto_accept=auto_accept,
    )


def load_announcement_json(path) -> list[dict]:  # noqa: ANN001
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("Items", "Objects", "announcements", "news"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("announcement JSON must be a list or contain Items/Objects/announcements/news")
