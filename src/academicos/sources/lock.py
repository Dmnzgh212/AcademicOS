from __future__ import annotations

import json
import os
import socket
import time
from contextlib import contextmanager
from pathlib import Path


class SyncAlreadyRunning(RuntimeError):
    pass


def _lock_payload() -> bytes:
    return json.dumps(
        {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "created_at": time.time(),
        },
        sort_keys=True,
    ).encode("utf-8")


def _is_stale(path: Path, *, stale_seconds: int) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        created_at = float(payload.get("created_at", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        try:
            created_at = path.stat().st_mtime
        except OSError:
            return True
    return time.time() - created_at > stale_seconds


def acquire_lock(path: Path, *, stale_seconds: int = 7200) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if attempt == 0 and _is_stale(path, stale_seconds=stale_seconds):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                continue
            raise SyncAlreadyRunning(f"source sync lock already exists: {path}")
        else:
            try:
                os.write(fd, _lock_payload())
            finally:
                os.close(fd)
            return
    raise SyncAlreadyRunning(f"could not acquire source sync lock: {path}")


def release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


@contextmanager
def sync_lock(path: Path, *, stale_seconds: int = 7200):
    acquire_lock(path, stale_seconds=stale_seconds)
    try:
        yield
    finally:
        release_lock(path)
