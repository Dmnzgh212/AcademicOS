from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from academicos.sources.brightspace.client import BrightspaceClient
from academicos.sources.manifest import (
    get_manifest,
    manifest_current,
    record_manifest,
    touch_manifest,
)
from academicos.sources.store import canonical_hash


def _safe_filename(name: object, fallback: str) -> str:
    candidate = Path(str(name or "").replace("\\", "/")).name.strip()
    if candidate in {"", ".", ".."}:
        return fallback
    return re.sub(r"[<>:\"/\\|?*]", "_", candidate)


def _response_filename(response, fallback: str) -> str:
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


def _manifest_skip(
    conn: sqlite3.Connection,
    *,
    source_key: str,
    remote_fingerprint: str,
) -> bool:
    entry = get_manifest(conn, source_key)
    if entry is None:
        return False
    destination = Path(entry.local_path)
    if manifest_current(
        conn,
        source_key=source_key,
        destination=destination,
        remote_fingerprint=remote_fingerprint,
    ):
        touch_manifest(conn, source_key)
        return True
    return False


def download_course_files_manifested(
    conn: sqlite3.Connection,
    client: BrightspaceClient,
    *,
    org_unit_id: str | int,
    out_dir: Path,
) -> dict[str, int]:
    """Mirror course files while skipping binaries whose metadata fingerprint is unchanged."""
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
        if topic_id is None:
            continue
        source_key = f"brightspace:{org_unit_id}:content:{topic_id}"
        fingerprint = canonical_hash(topic)
        if _manifest_skip(conn, source_key=source_key, remote_fingerprint=fingerprint):
            unchanged += 1
            continue

        fallback = _safe_filename(topic.get("Title") or topic.get("Name"), f"topic_{topic_id}")
        try:
            response = client.content_topic_file(org_unit_id, topic_id)
            filename = _response_filename(response, fallback)
            destination = content_dir / f"{topic_id}_{filename}"
            payload = response.content
            destination.write_bytes(payload)
            record_manifest(
                conn,
                source_key=source_key,
                destination=destination,
                remote_fingerprint=fingerprint,
                payload=payload,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )
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
            source_key = f"brightspace:{org_unit_id}:assignment:{folder_id}:{file_id}"
            fingerprint = canonical_hash(attachment)
            if _manifest_skip(conn, source_key=source_key, remote_fingerprint=fingerprint):
                unchanged += 1
                continue

            filename = _safe_filename(attachment.get("FileName"), f"file_{file_id}")
            destination = target / f"{file_id}_{filename}"
            try:
                response = client.assignment_attachment(org_unit_id, folder_id, file_id)
                payload = response.content
                destination.write_bytes(payload)
                record_manifest(
                    conn,
                    source_key=source_key,
                    destination=destination,
                    remote_fingerprint=fingerprint,
                    payload=payload,
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                )
                downloaded += 1
            except Exception:
                failed += 1

    return {"downloaded": downloaded, "unchanged": unchanged, "failed": failed}
