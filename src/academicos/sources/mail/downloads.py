from __future__ import annotations

import base64
import json
import re
import sqlite3
from pathlib import Path

from academicos.sources.mail.graph import GraphMailClient
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


def _metadata_for_message(conn: sqlite3.Connection, message_id: str) -> list[dict]:
    row = conn.execute(
        "SELECT raw_json FROM source_items WHERE source_type='email' AND source_id=?",
        (f"m365:{message_id}",),
    ).fetchone()
    if row is None or not row["raw_json"]:
        return []
    try:
        payload = json.loads(row["raw_json"])
    except json.JSONDecodeError:
        return []
    metadata = payload.get("_attachmentMetadata") if isinstance(payload, dict) else None
    return [item for item in metadata if isinstance(item, dict)] if isinstance(metadata, list) else []


def download_delta_attachments(
    conn: sqlite3.Connection,
    client: GraphMailClient,
    *,
    message_ids: tuple[str, ...],
    out_dir: Path,
) -> dict[str, int]:
    """Download only attachments belonging to messages changed by the current delta cycle."""
    totals = {"downloaded": 0, "unchanged": 0, "skipped": 0, "failed": 0}
    out_dir.mkdir(parents=True, exist_ok=True)

    for message_id in message_ids:
        metadata = _metadata_for_message(conn, message_id)
        if not metadata:
            continue
        message_dir = out_dir / re.sub(r"[^A-Za-z0-9._-]", "_", message_id)
        message_dir.mkdir(parents=True, exist_ok=True)

        for item in metadata:
            attachment_id = item.get("id")
            if not isinstance(attachment_id, str) or not attachment_id or item.get("isInline"):
                totals["skipped"] += 1
                continue

            safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", attachment_id)
            name = _safe_filename(item.get("name"), f"attachment_{safe_id}")
            destination = message_dir / f"{safe_id}_{name}"
            source_key = f"m365:{message_id}:attachment:{attachment_id}"
            fingerprint = canonical_hash(item)

            entry = get_manifest(conn, source_key)
            if entry is not None:
                recorded = Path(entry.local_path)
                if manifest_current(
                    conn,
                    source_key=source_key,
                    destination=recorded,
                    remote_fingerprint=fingerprint,
                ):
                    touch_manifest(conn, source_key)
                    totals["unchanged"] += 1
                    continue

            try:
                payload = client.message_attachment(message_id, attachment_id)
                content = payload.get("contentBytes")
                odata_type = str(payload.get("@odata.type") or "")
                if not isinstance(content, str) or "fileAttachment" not in odata_type:
                    totals["skipped"] += 1
                    continue
                raw = base64.b64decode(content, validate=True)
                actual_name = _safe_filename(payload.get("name") or item.get("name"), name)
                destination = message_dir / f"{safe_id}_{actual_name}"
                destination.write_bytes(raw)
                record_manifest(
                    conn,
                    source_key=source_key,
                    destination=destination,
                    remote_fingerprint=fingerprint,
                    payload=raw,
                    last_modified=str(item.get("lastModifiedDateTime") or "") or None,
                )
                totals["downloaded"] += 1
            except Exception:
                totals["failed"] += 1

    return totals
