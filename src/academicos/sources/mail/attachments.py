from __future__ import annotations

import base64
import re
from pathlib import Path

from academicos.sources.mail.graph import GraphMailClient


def _safe_filename(name: object, fallback: str) -> str:
    candidate = Path(str(name or "").replace("\\", "/")).name.strip()
    if candidate in {"", ".", ".."}:
        return fallback
    return re.sub(r"[<>:\"/\\|?*]", "_", candidate)


def download_message_attachments(
    client: GraphMailClient,
    *,
    message_id: str,
    metadata: list[dict],
    out_dir: Path,
) -> dict[str, int]:
    """Download non-inline file attachments for one message.

    Unsupported attachment types (item/reference attachments) are left as metadata
    only; the collector never mutates the mailbox.
    """
    target = out_dir / re.sub(r"[^A-Za-z0-9._-]", "_", message_id)
    target.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    unchanged = 0
    skipped = 0
    failed = 0

    for item in metadata:
        attachment_id = item.get("id")
        if not isinstance(attachment_id, str) or not attachment_id:
            skipped += 1
            continue
        if bool(item.get("isInline")):
            skipped += 1
            continue

        try:
            payload = client.message_attachment(message_id, attachment_id)
            content = payload.get("contentBytes")
            odata_type = str(payload.get("@odata.type") or "")
            if not isinstance(content, str) or "fileAttachment" not in odata_type:
                skipped += 1
                continue
            raw = base64.b64decode(content, validate=True)
            safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", attachment_id)
            name = _safe_filename(
                payload.get("name") or item.get("name"),
                f"attachment_{safe_id}",
            )
            destination = target / f"{safe_id}_{name}"
            if destination.exists() and destination.read_bytes() == raw:
                unchanged += 1
            else:
                destination.write_bytes(raw)
                downloaded += 1
        except Exception:
            failed += 1

    return {
        "downloaded": downloaded,
        "unchanged": unchanged,
        "skipped": skipped,
        "failed": failed,
    }


def download_inbox_attachments(
    client: GraphMailClient,
    *,
    out_dir: Path,
    since: str | None = None,
    max_pages: int = 20,
) -> dict[str, int]:
    """Mirror attachments for messages in the bounded incremental Inbox window."""
    totals = {"downloaded": 0, "unchanged": 0, "skipped": 0, "failed": 0}
    for message in client.inbox_messages(since=since, max_pages=max_pages):
        if not message.get("hasAttachments"):
            continue
        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id:
            continue
        try:
            metadata = client.message_attachments(message_id)
            result = download_message_attachments(
                client,
                message_id=message_id,
                metadata=metadata,
                out_dir=out_dir,
            )
        except Exception:
            totals["failed"] += 1
            continue
        for key in totals:
            totals[key] += result[key]
    return totals
