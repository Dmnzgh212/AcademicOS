from __future__ import annotations

import time
from collections.abc import Callable

import requests


class BrightspaceClient:
    """Minimal read-only Brightspace Valence client for AcademicOS source sync."""

    MAX_RETRIES = 3

    def __init__(
        self,
        *,
        host: str,
        bearer_token: str,
        le_version: str = "1.75",
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.host = host.rstrip("/")
        self.le_version = le_version
        self.session = session or requests.Session()
        self.sleep = sleep
        self.session.headers.update({"Authorization": f"Bearer {bearer_token}"})

    def _get(self, path: str, params: dict[str, str] | None = None):
        response = None
        for attempt in range(self.MAX_RETRIES):
            response = self.session.get(f"{self.host}{path}", params=params, timeout=30)
            if response.status_code != 429:
                break
            if attempt < self.MAX_RETRIES - 1:
                retry_after = float(response.headers.get("Retry-After", "5"))
                self.sleep(retry_after)

        assert response is not None
        response.raise_for_status()
        return response.json()

    def le(self, path: str) -> str:
        return f"/d2l/api/le/{self.le_version}{path}"

    def news(self, org_id: str | int, *, since: str | None = None) -> list[dict]:
        params = {"since": since} if since else None
        data = self._get(self.le(f"/{org_id}/news/"), params=params)
        return data if isinstance(data, list) else []
