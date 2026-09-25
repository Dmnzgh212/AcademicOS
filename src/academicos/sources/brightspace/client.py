from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import requests


class BrightspaceClient:
    """Read-only Brightspace Valence client used by AcademicOS collectors.

    Academic-data methods in this client are GET-only. Authentication refresh is
    isolated in ``brightspace.auth`` so scheduled collection cannot mutate courses.
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        *,
        host: str,
        bearer_token: str,
        le_version: str = "1.75",
        lp_version: str = "1.51",
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.host = host.rstrip("/")
        self.le_version = le_version
        self.lp_version = lp_version
        self.session = session or requests.Session()
        self.sleep = sleep
        self.session.headers.update(
            {
                "Authorization": f"Bearer {bearer_token}",
                "Origin": self.host,
                "Referer": f"{self.host}/",
                "User-Agent": "AcademicOS/0.1",
            }
        )

    def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> requests.Response:
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
        return response

    def _get(self, path: str, params: dict[str, Any] | None = None):
        return self._request(path, params=params).json()

    def _get_raw(self, path: str, params: dict[str, Any] | None = None) -> requests.Response:
        return self._request(path, params=params)

    def le(self, path: str) -> str:
        return f"/d2l/api/le/{self.le_version}{path}"

    def lp(self, path: str) -> str:
        return f"/d2l/api/lp/{self.lp_version}{path}"

    def paginate_bookmark(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        items: list[dict] = []
        page_params = dict(params or {})
        page_params["bookmark"] = ""
        while True:
            data = self._get(path, page_params)
            if not isinstance(data, dict):
                break
            batch = data.get("Items", [])
            if isinstance(batch, list):
                items.extend(item for item in batch if isinstance(item, dict))
            paging = data.get("PagingInfo", {})
            if not isinstance(paging, dict) or not paging.get("HasMoreItems"):
                break
            page_params["bookmark"] = paging.get("Bookmark", "")
        return items

    def paginate_pages(
        self,
        path: str,
        *,
        page_size: int = 50,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        items: list[dict] = []
        page_params = dict(params or {})
        page_params["pageSize"] = page_size
        page = 1
        while True:
            page_params["pageNumber"] = page
            data = self._get(path, page_params)
            batch = data if isinstance(data, list) else []
            if not batch:
                break
            items.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < page_size:
                break
            page += 1
        return items

    def whoami(self) -> dict:
        data = self._get(self.lp("/users/whoami"))
        return data if isinstance(data, dict) else {}

    def my_enrollments(self, *, active_only: bool = True) -> list[dict]:
        params: dict[str, Any] = {"sortBy": "-StartDate"}
        if active_only:
            params.update({"isActive": "true", "canAccess": "true"})
        return self.paginate_bookmark(self.lp("/enrollments/myenrollments/"), params)

    def news(self, org_id: str | int, *, since: str | None = None) -> list[dict]:
        params = {"since": since} if since else None
        data = self._get(self.le(f"/{org_id}/news/"), params=params)
        return data if isinstance(data, list) else []

    def assignments(self, org_id: str | int) -> list[dict]:
        data = self._get(self.le(f"/{org_id}/dropbox/folders/"))
        return data if isinstance(data, list) else []

    def my_submissions(self, org_id: str | int, folder_id: str | int) -> list[dict]:
        data = self._get(
            self.le(f"/{org_id}/dropbox/folders/{folder_id}/submissions/mysubmissions/")
        )
        return data if isinstance(data, list) else []

    def quizzes(self, org_id: str | int) -> list[dict]:
        data = self._get(self.le(f"/{org_id}/quizzes/"))
        if isinstance(data, dict) and isinstance(data.get("Objects"), list):
            return data["Objects"]
        return data if isinstance(data, list) else []

    def quiz_attempts(self, org_id: str | int, quiz_id: str | int) -> list[dict]:
        data = self._get(self.le(f"/{org_id}/quizzes/{quiz_id}/attempts/"))
        if isinstance(data, dict) and isinstance(data.get("Objects"), list):
            return data["Objects"]
        return data if isinstance(data, list) else []

    def content_root(self, org_id: str | int) -> list[dict]:
        data = self._get(self.le(f"/{org_id}/content/root/"))
        return data if isinstance(data, list) else []

    def content_module(self, org_id: str | int, module_id: str | int):
        return self._get(self.le(f"/{org_id}/content/modules/{module_id}/structure/"))

    def content_toc(self, org_id: str | int):
        return self._get(self.le(f"/{org_id}/content/toc"))

    def grades(self, org_id: str | int):
        return self._get(self.le(f"/{org_id}/grades/values/myGradeValues/"))

    def grade_objects(self, org_id: str | int):
        return self._get(self.le(f"/{org_id}/grades/"))

    def final_grade(self, org_id: str | int):
        return self._get(self.le(f"/{org_id}/grades/final/values/myGradeValue"))

    def discussion_forums(self, org_id: str | int) -> list[dict]:
        data = self._get(self.le(f"/{org_id}/discussions/forums/"))
        return data if isinstance(data, list) else []

    def discussion_topics(self, org_id: str | int, forum_id: str | int) -> list[dict]:
        data = self._get(self.le(f"/{org_id}/discussions/forums/{forum_id}/topics/"))
        return data if isinstance(data, list) else []

    def discussion_posts(
        self,
        org_id: str | int,
        forum_id: str | int,
        topic_id: str | int,
    ) -> list[dict]:
        return self.paginate_pages(
            self.le(f"/{org_id}/discussions/forums/{forum_id}/topics/{topic_id}/posts/")
        )

    def checklists(self, org_id: str | int) -> list[dict]:
        data = self._get(self.le(f"/{org_id}/checklists/"))
        return data if isinstance(data, list) else []

    def course_overview(self, org_id: str | int):
        return self._get(self.le(f"/{org_id}/overview"))

    def calendar_events(
        self,
        org_id: str | int,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if start:
            params["startDateTime"] = start
        if end:
            params["endDateTime"] = end
        data = self._get(
            self.le(f"/{org_id}/calendar/events/myEvents/"),
            params=params or None,
        )
        return data if isinstance(data, list) else []

    def due_items(
        self,
        *,
        org_ids_csv: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if org_ids_csv:
            params["orgUnitIdsCSV"] = org_ids_csv
        if start:
            params["startDateTime"] = start
        if end:
            params["endDateTime"] = end
        data = self._get(self.le("/content/myItems/due/"), params=params or None)
        if isinstance(data, dict) and isinstance(data.get("Objects"), list):
            return data["Objects"]
        return data if isinstance(data, list) else []

    def overdue_items(self, *, org_ids_csv: str | None = None) -> list[dict]:
        params = {"orgUnitIdsCSV": org_ids_csv} if org_ids_csv else None
        data = self._get(self.le("/overdueItems/myItems"), params=params)
        if isinstance(data, dict) and isinstance(data.get("Objects"), list):
            return data["Objects"]
        return data if isinstance(data, list) else []

    def updates(self, org_id: str | int):
        return self._get(self.le(f"/{org_id}/updates/myUpdates"))

    def user_feed(
        self,
        *,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        data = self._get(self.lp("/feed/"), params=params or None)
        return data if isinstance(data, list) else []

    def content_topic_file(self, org_id: str | int, topic_id: str | int) -> requests.Response:
        return self._get_raw(self.le(f"/{org_id}/content/topics/{topic_id}/file"))

    def assignment_attachment(
        self,
        org_id: str | int,
        folder_id: str | int,
        file_id: str | int,
    ) -> requests.Response:
        return self._get_raw(
            self.le(f"/{org_id}/dropbox/folders/{folder_id}/attachments/{file_id}")
        )
