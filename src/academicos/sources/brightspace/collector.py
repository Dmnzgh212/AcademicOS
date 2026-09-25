from __future__ import annotations

import html
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from academicos.calendar.models import SourceItem, SourceType
from academicos.sources.brightspace.announcements import ingest_announcements
from academicos.sources.brightspace.client import BrightspaceClient
from academicos.sources.store import canonical_hash, source_item_id, upsert_source_item

_ID_FIELDS = (
    "Id",
    "Identifier",
    "ObjectId",
    "TopicId",
    "ModuleId",
    "FolderId",
    "QuizId",
    "EventId",
    "CalendarEventId",
    "GradeObjectIdentifier",
    "PostId",
    "ForumId",
    "AttemptId",
)
_TEXT_FIELDS = (
    "Title",
    "Name",
    "Subject",
    "Description",
    "Text",
    "Html",
    "Body",
    "Instructions",
    "Feedback",
)
_TIMESTAMP_FIELDS = (
    "LastModifiedDate",
    "ModifiedDate",
    "UpdatedDate",
    "DueDate",
    "EndDate",
    "StartDate",
    "CreatedDate",
    "PublicationDate",
    "DateSubmitted",
    "LastPostDate",
)


@dataclass
class CollectionReport:
    datasets: dict[str, dict[str, int]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def changed(self) -> int:
        return sum(item.get("changed", 0) for item in self.datasets.values())

    @property
    def unchanged(self) -> int:
        return sum(item.get("unchanged", 0) for item in self.datasets.values())


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _source_timestamp(payload: dict[str, Any]) -> datetime | None:
    for key in _TIMESTAMP_FIELDS:
        parsed = _parse_timestamp(payload.get(key))
        if parsed:
            return parsed
    return None


def _rich_text(value: object) -> str:
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        text = str(value.get("Text") or value.get("Html") or "")
    else:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def _raw_text(payload: dict[str, Any]) -> str | None:
    parts: list[str] = []
    for key in _TEXT_FIELDS:
        text = _rich_text(payload.get(key))
        if text and text not in parts:
            parts.append(text)
    return "\n".join(parts) if parts else None


def _stable_key(dataset: str, payload: dict[str, Any], ordinal: int) -> str:
    for key in _ID_FIELDS:
        value = payload.get(key)
        if value not in (None, ""):
            return f"{dataset}:{value}"

    identity_parts = []
    for key in ("Title", "Name", "Subject", "DueDate", "StartDate", "EndDate"):
        value = payload.get(key)
        if value not in (None, ""):
            identity_parts.append(f"{key}={value}")
    if identity_parts:
        return f"{dataset}:{canonical_hash(identity_parts)[:24]}"
    return f"{dataset}:ordinal:{ordinal}"


def _records(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("Objects", "Items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def persist_dataset(
    conn: sqlite3.Connection,
    *,
    dataset: str,
    payload: object,
    course_id: str | None,
    org_unit_id: str | int | None,
    fetched_at: datetime | None = None,
) -> dict[str, int]:
    """Persist one raw Brightspace dataset without interpreting academic meaning."""
    fetched_at = fetched_at or datetime.now(UTC)
    changed = 0
    unchanged = 0
    rows = _records(payload)

    for ordinal, raw in enumerate(rows):
        key = _stable_key(dataset, raw, ordinal)
        source_key = f"{org_unit_id or 'global'}:{key}"
        item = SourceItem(
            id=source_item_id(SourceType.BRIGHTSPACE, source_key),
            source_type=SourceType.BRIGHTSPACE,
            source_id=source_key,
            course_id=course_id,
            source_url=None,
            source_timestamp=_source_timestamp(raw),
            fetched_at=fetched_at,
            content_hash=canonical_hash(raw),
            raw_text=_raw_text(raw),
            raw_json=raw,
        )
        if upsert_source_item(conn, item):
            changed += 1
        else:
            unchanged += 1

    return {"fetched": len(rows), "changed": changed, "unchanged": unchanged}


def _http_error(exc: requests.HTTPError) -> str:
    status = exc.response.status_code if exc.response is not None else "HTTP"
    return f"{status}: {exc}"


def _module_ids(node: object) -> set[str]:
    result: set[str] = set()
    if isinstance(node, list):
        for child in node:
            result.update(_module_ids(child))
    elif isinstance(node, dict):
        module_id = node.get("ModuleId")
        if module_id is None and node.get("Type") == 0:
            module_id = node.get("Id")
        if module_id is not None:
            result.add(str(module_id))
        for key in ("Modules", "Topics"):
            result.update(_module_ids(node.get(key, [])))
    return result


def collect_course_data(
    conn: sqlite3.Connection,
    client: BrightspaceClient,
    *,
    course_id: str,
    org_unit_id: str | int,
    since: str | None = None,
    start: str | None = None,
    end: str | None = None,
    include: set[str] | None = None,
    auto_accept_announcements: bool = False,
    timezone_name: str = "America/Toronto",
) -> CollectionReport:
    """Collect student-readable Brightspace course data with per-endpoint isolation."""
    wanted = include or {
        "announcements",
        "assignments",
        "submissions",
        "quizzes",
        "quiz_attempts",
        "content",
        "content_structure",
        "grades",
        "grade_objects",
        "final_grade",
        "calendar",
        "due",
        "overdue",
        "updates",
        "discussions",
        "checklists",
        "overview",
    }
    report = CollectionReport()

    def persist(name: str, payload: object) -> None:
        report.datasets[name] = persist_dataset(
            conn,
            dataset=name,
            payload=payload,
            course_id=course_id,
            org_unit_id=org_unit_id,
        )

    def run(name: str, fetcher) -> object | None:
        if name not in wanted:
            return None
        try:
            payload = fetcher()
            persist(name, payload)
            return payload
        except requests.HTTPError as exc:
            report.errors[name] = _http_error(exc)
        except Exception as exc:
            report.errors[name] = f"{type(exc).__name__}: {exc}"
        return None

    if "announcements" in wanted:
        try:
            announcements = client.news(org_unit_id, since=since)
            result = ingest_announcements(
                conn,
                announcements,
                course_id=course_id,
                org_unit_id=str(org_unit_id),
                timezone_name=timezone_name,
                auto_accept=auto_accept_announcements,
            )
            report.datasets["announcements"] = {
                "fetched": result["fetched"],
                "changed": result["changed"],
                "unchanged": result["unchanged"],
            }
        except Exception as exc:
            report.errors["announcements"] = f"{type(exc).__name__}: {exc}"

    assignments = run("assignments", lambda: client.assignments(org_unit_id))
    if "submissions" in wanted and isinstance(assignments, list):
        for assignment in assignments:
            folder_id = assignment.get("Id") if isinstance(assignment, dict) else None
            if folder_id is None:
                continue
            name = f"submissions:{folder_id}"
            try:
                persist(name, client.my_submissions(org_unit_id, folder_id))
            except requests.HTTPError as exc:
                report.errors[name] = _http_error(exc)
            except Exception as exc:
                report.errors[name] = f"{type(exc).__name__}: {exc}"

    quizzes = run("quizzes", lambda: client.quizzes(org_unit_id))
    if "quiz_attempts" in wanted and isinstance(quizzes, list):
        for quiz in quizzes:
            quiz_id = quiz.get("Id") if isinstance(quiz, dict) else None
            if quiz_id is None:
                continue
            name = f"quiz_attempts:{quiz_id}"
            try:
                persist(name, client.quiz_attempts(org_unit_id, quiz_id))
            except requests.HTTPError as exc:
                report.errors[name] = _http_error(exc)
            except Exception as exc:
                report.errors[name] = f"{type(exc).__name__}: {exc}"

    toc = run("content", lambda: client.content_toc(org_unit_id))
    if "content_structure" in wanted:
        root = run("content_root", lambda: client.content_root(org_unit_id))
        module_ids = _module_ids(toc) | _module_ids(root)
        for module_id in sorted(module_ids):
            name = f"content_module:{module_id}"
            try:
                persist(name, client.content_module(org_unit_id, module_id))
            except requests.HTTPError as exc:
                report.errors[name] = _http_error(exc)
            except Exception as exc:
                report.errors[name] = f"{type(exc).__name__}: {exc}"

    run("grades", lambda: client.grades(org_unit_id))
    run("grade_objects", lambda: client.grade_objects(org_unit_id))
    run("final_grade", lambda: client.final_grade(org_unit_id))
    run("calendar", lambda: client.calendar_events(org_unit_id, start=start, end=end))
    run(
        "due",
        lambda: client.due_items(org_ids_csv=str(org_unit_id), start=start, end=end),
    )
    run("overdue", lambda: client.overdue_items(org_ids_csv=str(org_unit_id)))
    run("updates", lambda: client.updates(org_unit_id))
    run("checklists", lambda: client.checklists(org_unit_id))
    run("overview", lambda: client.course_overview(org_unit_id))

    if "discussions" in wanted:
        forums = run("discussion_forums", lambda: client.discussion_forums(org_unit_id))
        if isinstance(forums, list):
            for forum in forums:
                forum_id = forum.get("ForumId") or forum.get("Id") if isinstance(forum, dict) else None
                if forum_id is None:
                    continue
                topic_name = f"discussion_topics:{forum_id}"
                try:
                    topics = client.discussion_topics(org_unit_id, forum_id)
                    persist(topic_name, topics)
                except requests.HTTPError as exc:
                    report.errors[topic_name] = _http_error(exc)
                    continue
                except Exception as exc:
                    report.errors[topic_name] = f"{type(exc).__name__}: {exc}"
                    continue
                for topic in topics:
                    topic_id = topic.get("TopicId") or topic.get("Id") if isinstance(topic, dict) else None
                    if topic_id is None:
                        continue
                    post_name = f"discussion_posts:{forum_id}:{topic_id}"
                    try:
                        persist(
                            post_name,
                            client.discussion_posts(org_unit_id, forum_id, topic_id),
                        )
                    except requests.HTTPError as exc:
                        report.errors[post_name] = _http_error(exc)
                    except Exception as exc:
                        report.errors[post_name] = f"{type(exc).__name__}: {exc}"

    return report


def _safe_filename(name: object, fallback: str) -> str:
    candidate = Path(str(name or "").replace("\\", "/")).name.strip()
    if candidate in {"", ".", ".."}:
        return fallback
    return re.sub(r"[<>:\"/\\|?*]", "_", candidate)


def _response_filename(response: requests.Response, fallback: str) -> str:
    disposition = response.headers.get("Content-Disposition", "")
    match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, re.IGNORECASE)
    return _safe_filename(match.group(1).strip() if match else fallback, fallback)


def _walk_file_topics(node: object):
    if isinstance(node, list):
        for child in node:
            yield from _walk_file_topics(child)
        return
    if not isinstance(node, dict):
        return
    if node.get("TopicType") == 1:
        topic_id = node.get("Id") or node.get("TopicId")
        if topic_id is not None:
            yield node
    for key in ("Modules", "Topics"):
        yield from _walk_file_topics(node.get(key, []))


def download_course_files(
    client: BrightspaceClient,
    *,
    org_unit_id: str | int,
    out_dir: Path,
) -> dict[str, int]:
    """Mirror directly downloadable course-content and assignment files locally."""
    content_dir = out_dir / "content"
    assignment_dir = out_dir / "assignments"
    content_dir.mkdir(parents=True, exist_ok=True)
    assignment_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    unchanged = 0
    failed = 0

    try:
        toc = client.content_toc(org_unit_id)
        topics = list(_walk_file_topics(toc))
    except Exception:
        topics = []
        failed += 1

    for topic in topics:
        topic_id = topic.get("Id") or topic.get("TopicId")
        fallback = _safe_filename(topic.get("Title") or topic.get("Name"), f"topic_{topic_id}")
        try:
            response = client.content_topic_file(org_unit_id, topic_id)
            filename = _response_filename(response, fallback)
            destination = content_dir / f"{topic_id}_{filename}"
            payload = response.content
            if destination.exists() and destination.read_bytes() == payload:
                unchanged += 1
            else:
                destination.write_bytes(payload)
                downloaded += 1
        except Exception:
            failed += 1

    try:
        assignments = client.assignments(org_unit_id)
    except Exception:
        assignments = []
        failed += 1

    for assignment in assignments:
        folder_id = assignment.get("Id")
        if folder_id is None:
            continue
        folder_name = _safe_filename(assignment.get("Name"), f"assignment_{folder_id}")
        target = assignment_dir / f"{folder_id}_{folder_name}"
        target.mkdir(parents=True, exist_ok=True)
        for attachment in assignment.get("Attachments", []) or []:
            if not isinstance(attachment, dict) or attachment.get("FileId") is None:
                continue
            file_id = attachment["FileId"]
            filename = _safe_filename(attachment.get("FileName"), f"file_{file_id}")
            destination = target / f"{file_id}_{filename}"
            try:
                response = client.assignment_attachment(org_unit_id, folder_id, file_id)
                payload = response.content
                if destination.exists() and destination.read_bytes() == payload:
                    unchanged += 1
                else:
                    destination.write_bytes(payload)
                    downloaded += 1
            except Exception:
                failed += 1

    return {"downloaded": downloaded, "unchanged": unchanged, "failed": failed}
