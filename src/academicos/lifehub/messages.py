"""Shared byte and finite-number bounds for JSON service messages."""

from __future__ import annotations

import json
from typing import Any

MAX_IO_BYTES = 64 * 1024
MAX_MESSAGE_DEPTH = 64


def encode_message(value: Any) -> bytes:
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, (dict, list, tuple)):
            if depth >= MAX_MESSAGE_DEPTH:
                raise ValueError("service message nesting exceeds depth limit")
            children = item.values() if isinstance(item, dict) else item
            pending.extend((child, depth + 1) for child in children)
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    except RecursionError as exc:
        raise ValueError("service message nesting exceeds parser limit") from exc
    if len(raw) > MAX_IO_BYTES:
        raise ValueError("service message exceeds IO limit")
    return raw


def decode_message(raw: bytes) -> Any:
    if len(raw) > MAX_IO_BYTES:
        raise ValueError("service message exceeds IO limit")

    def reject_constant(value):
        raise ValueError(f"nonfinite JSON number: {value}")

    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
    except RecursionError as exc:
        raise ValueError("service message nesting exceeds parser limit") from exc
    # This also rejects exponent overflow (e.g. 1e400) and oversized canonical JSON.
    encode_message(value)
    return value
