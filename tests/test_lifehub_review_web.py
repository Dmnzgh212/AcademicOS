from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from academicos.lifehub.effects import EffectRequest
from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.proposals import ProposedChange
from academicos.lifehub.store import LifeStore
from academicos.lifehub.web import make_handler, render_workspace


def _seed(tmp_path: Path) -> tuple[Path, Path, int, int]:
    root, db = tmp_path / "installed", tmp_path / "hub.db"
    archive = tmp_path / "review.zip"
    manifest = b"""manifest_version = 1
api = "lifehub@1"
id = "demo.review"
name = "Review"
version = "1.0.0"
[permissions]
storage_read = []
storage_write = ["tasks"]
network_retrieval = []
localhost_ports = []
[[permissions.effect_request]]
kind = "test.record"
destination = "demo.outbox"
[[contributes]]
id = "worker"
point = "task.worker"
entrypoint = "lifehub.wasm"
[contributes.config]
module = "worker.wasm"
"""
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("plugin.toml", manifest)
        output.writestr("worker.wasm", b"\0asm\1\0\0\0")
    store = LifeStore(db)
    try:
        installer = PackageInstaller(root, store)
        installer.install(archive, approved_hash=installer.review(archive).content_hash)
    finally:
        store.close()
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        digest = hub.store.conn.execute(
            "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id='demo.review'"
        ).fetchone()[0]
        ref = "demo.review:worker"
        proposal_id = hub.proposals.submit(
            "demo.review",
            digest,
            ref,
            [ProposedChange("tasks.today", "plan", {"title": "<script>alert(1)</script>"}, None)],
        )[0]
        effect_id = hub.effects.submit(
            hub.manifest("demo.review"),
            digest,
            ref,
            [
                EffectRequest(
                    "test.record", "demo.outbox", "Share chosen summary", {"private": "secret"}
                )
            ],
        )[0]
    finally:
        hub.close()
    return root, db, proposal_id, effect_id


def _request(
    handler,
    payload: dict | None = None,
    *,
    token: str = "review-token",
    headers: dict | None = None,
):
    data = None if payload is None else json.dumps(payload).encode()
    request_headers = {"Host": "127.0.0.1:8844"}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
        request_headers["Content-Length"] = str(len(data))
        if token:
            request_headers["X-LifeHub-Token"] = token
        request_headers["Origin"] = "http://127.0.0.1:8844"
    request_headers.update(headers or {})
    method, path = ("GET", "/") if data is None else ("POST", "/api/decision")
    raw = f"{method} {path} HTTP/1.1\r\n".encode()
    raw += b"".join(f"{key}: {value}\r\n".encode() for key, value in request_headers.items())
    raw += b"\r\n" + (data or b"")

    class MemoryConnection:
        def __init__(self):
            self.response = bytearray()

        def makefile(self, mode, buffering=-1):
            return BytesIO(raw)

        def sendall(self, chunk):
            self.response.extend(chunk)

    connection = MemoryConnection()
    handler(connection, ("127.0.0.1", 12345), SimpleNamespace(server_port=8844))
    head, body = bytes(connection.response).split(b"\r\n\r\n", 1)
    return int(head.split(b" ")[1]), body.decode()


def test_review_inbox_discloses_full_payload_and_escapes_markup(tmp_path: Path) -> None:
    root, db, proposal_id, effect_id = _seed(tmp_path)
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        page = render_workspace(hub, token="review-token")
        assert "Review inbox" in page
        assert 'data-type="proposal" data-decision="approve"' in page
        assert f'data-id="{proposal_id}"' in page
        assert f'data-id="{effect_id}"' in page
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
        assert "<script>alert(1)</script>" not in page
        assert "&quot;private&quot;: &quot;secret&quot;" in page
        assert "Share chosen summary" in page
    finally:
        hub.close()


def test_review_http_decisions_require_local_origin_and_separate_dispatch(tmp_path: Path) -> None:
    root, db, proposal_id, effect_id = _seed(tmp_path)
    handler = make_handler(db_path=db, plugins_path=root, token="review-token")
    assert _request(handler)[0] == 200
    proposal = {"type": "proposal", "action": "approve", "id": proposal_id}
    assert _request(handler, proposal, token="")[0] == 403
    assert _request(handler, proposal, headers={"Origin": "http://evil.example"})[0] == 403
    assert _request(handler, proposal, headers={"Host": "evil.example"})[0] == 403
    assert _request(handler, proposal)[1] == "committed\n"
    assert _request(handler, proposal)[0] == 400
    effect = {"type": "effect", "action": "approve", "id": effect_id}
    assert _request(handler, effect)[1] == "approved\n"
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        assert hub.effects.get(effect_id)["status"] == "approved"
        assert (
            hub.store.latest_records("tasks.today")[0]["payload"]["title"]
            == "<script>alert(1)</script>"
        )
        assert (
            hub.store.conn.execute(
                "SELECT count(*) FROM lifehub_fake_effect_deliveries"
            ).fetchone()[0]
            == 0
        )
    finally:
        hub.close()
    effect["action"] = "dispatch_fake"
    assert _request(handler, effect)[1] == "succeeded\n"
    assert _request(handler, effect)[0] == 400
    assert _request(handler, {**effect, "id": True})[0] == 400
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        assert (
            hub.store.conn.execute(
                "SELECT count(*) FROM lifehub_fake_effect_deliveries"
            ).fetchone()[0]
            == 1
        )
    finally:
        hub.close()
