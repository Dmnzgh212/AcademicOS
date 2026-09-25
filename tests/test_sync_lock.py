from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from academicos.sources.lock import SyncAlreadyRunning, acquire_lock, release_lock, sync_lock


def test_second_lock_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sync.lock"
    acquire_lock(path)
    try:
        with pytest.raises(SyncAlreadyRunning):
            acquire_lock(path)
    finally:
        release_lock(path)


def test_stale_lock_is_recovered(tmp_path: Path) -> None:
    path = tmp_path / "sync.lock"
    path.write_text(
        json.dumps({"pid": 1, "host": "old", "created_at": time.time() - 100}),
        encoding="utf-8",
    )

    acquire_lock(path, stale_seconds=10)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["host"] != "old" or payload["created_at"] > time.time() - 10
    finally:
        release_lock(path)


def test_context_manager_releases_lock(tmp_path: Path) -> None:
    path = tmp_path / "sync.lock"
    with sync_lock(path):
        assert path.exists()
    assert not path.exists()
