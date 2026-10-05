from __future__ import annotations

import html
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlsplit

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.registry import RegisteredExtension


CSS = r"""
:root{color-scheme:light;--bg:#f4f3ef;--panel:#fff;--ink:#15171b;--muted:#747983;--line:#e6e4dd;--accent:#4b57d9;--soft:#eef0ff;--good:#13765e}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
.shell{max-width:1500px;margin:0 auto;padding:22px 24px 56px}.topbar{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:30px}.brand{display:flex;align-items:center;gap:10px;font-size:16px;font-weight:800}.mark{width:28px;height:28px;border-radius:9px;background:var(--ink);color:#fff;display:grid;place-items:center;font-size:10px}.topmeta{font-size:10px;color:var(--muted)}.actions{display:flex;gap:8px}.actions button{border:1px solid var(--line);background:#fff;border-radius:10px;padding:8px 11px;font-size:10px;cursor:pointer}.actions button.active{background:var(--ink);color:#fff;border-color:var(--ink)}
.hero{margin-bottom:22px}.eyebrow{font-size:9px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:800}.hero h1{font-size:clamp(34px,5vw,64px);line-height:.95;letter-spacing:-.055em;margin:9px 0 11px;max-width:900px}.hero p{font-size:12px;color:var(--muted);max-width:650px;line-height:1.6}.status{display:flex;gap:7px;flex-wrap:wrap;margin-top:14px}.pill{padding:6px 9px;border-radius:999px;background:#e7f4ef;color:var(--good);font-size:9px;font-weight:800}.pill.neutral{background:#ebeae5;color:#686c73}
.boardbar{display:flex;justify-content:space-between;align-items:end;margin:24px 0 10px}.boardbar h2{font-size:15px;margin:0}.hint{font-size:9px;color:var(--muted)}
.board{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));grid-auto-rows:54px;gap:10px;min-height:220px}.surface{background:var(--panel);border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:0 14px 35px rgba(25,27,32,.045);min-width:0}.surface.editing{outline:1px dashed #a6a9b8;outline-offset:2px}.surface-head{display:flex;justify-content:space-between;gap:10px;padding:14px 15px 10px;border-bottom:1px solid #f0efeb}.kicker{font-size:8px;letter-spacing:.08em;text-transform:uppercase;color:#9a9da5;font-weight:800}.surface-title{font-size:13px;font-weight:780;margin-top:3px}.surface-desc{font-size:9px;color:var(--muted);margin-top:4px}.surface-body{padding:13px 15px 16px}.edit-controls{display:none;gap:4px}.edit-mode .edit-controls{display:flex}.edit-controls button{border:1px solid var(--line);background:#fafafa;border-radius:7px;padding:4px 6px;font-size:9px;cursor:pointer}.empty{font-size:10px;color:var(--muted);padding:10px 0}.stamp{font-size:8px;color:#a1a5ad;margin-top:12px}.list{display:grid;gap:8px}.list-row{padding:9px 10px;background:#f7f7f4;border-radius:10px}.list-row strong{font-size:10.5px;display:block}.list-row span{display:block;color:var(--muted);font-size:9px;margin-top:3px;line-height:1.4}.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metric{background:#f7f7f4;border-radius:11px;padding:11px}.metric-label{font-size:8px;color:var(--muted);text-transform:uppercase}.metric-value{font-size:18px;font-weight:800;letter-spacing:-.03em;margin-top:4px}.metric-delta{font-size:9px;margin-top:3px;color:var(--muted)}.text-block{font-size:10.5px;line-height:1.6;white-space:pre-wrap}.table{width:100%;border-collapse:collapse;font-size:9px}.table td,.table th{padding:7px 6px;border-bottom:1px solid #eee;text-align:left}.table th{color:var(--muted)}.custom-surface{padding:16px;border:1px dashed #c9cad0;border-radius:12px;background:#fafafa;font-size:10px;color:var(--muted);line-height:1.55}.footer{margin-top:18px;text-align:center;color:#a2a5ab;font-size:8.5px}
.review-section{margin-top:38px}.review-header{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-bottom:14px}.review-header h2{font-size:24px;letter-spacing:-.035em;margin:5px 0}.review-header p{font-size:13px;color:var(--muted);margin:0;line-height:1.5}.review-count{font-size:12px;font-weight:750;color:var(--accent);background:var(--soft);padding:9px 12px;border-radius:999px;white-space:nowrap}.review-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,390px),1fr));gap:14px}.review-card{background:#fff;border:1px solid var(--line);border-radius:17px;padding:18px;min-width:0;box-shadow:0 10px 30px rgba(25,27,32,.035)}.review-card h3{font-size:17px;margin:5px 0 10px;overflow-wrap:anywhere}.review-meta{display:grid;gap:5px;color:#535965;font-size:12px;line-height:1.5;overflow-wrap:anywhere}.review-meta strong{color:var(--ink)}.review-payload{margin:13px 0;padding:13px;border-radius:11px;background:#f6f6f3;border:1px solid #eee;font:11px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;max-height:280px;overflow:auto}.review-actions{display:flex;gap:8px;flex-wrap:wrap}.review-actions button{font-size:12px;font-weight:700;border-radius:9px;padding:9px 12px;border:1px solid var(--line);background:#fff;cursor:pointer}.review-actions button.primary{background:var(--ink);border-color:var(--ink);color:#fff}.review-actions button:disabled{opacity:.5;cursor:wait}.review-note{font-size:12px;line-height:1.5;color:var(--muted)}.review-message{font-size:13px;margin:8px 0;color:#9a342e;min-height:18px}.review-status{display:inline-block;font-size:10px;font-weight:750;text-transform:uppercase;letter-spacing:.06em;color:var(--accent)}.actions a{font-size:12px;color:var(--ink);text-decoration:none;padding:8px}
@media(max-width:900px){.shell{padding:18px 12px 40px}.board{grid-template-columns:repeat(6,minmax(0,1fr))}.hero h1{font-size:42px}}@media(max-width:560px){.board{display:block}.surface{margin-bottom:10px}.topbar{align-items:flex-start}.topmeta{display:none}}
"""


JS = r"""
const token=document.documentElement.dataset.token;const board=document.querySelector('.board');const editButton=document.querySelector('#edit-toggle');
function surfaces(){return [...board.querySelectorAll('.surface')];}
function applyGrid(){for(const el of surfaces()){if(window.innerWidth<=560){el.style.gridColumn='';el.style.gridRow='';continue;}const cols=window.innerWidth<=900?6:12;const w=Math.min(Number(el.dataset.w||4),cols);const x=Math.min(Number(el.dataset.x||0),Math.max(0,cols-w));el.style.gridColumn=`${x+1} / span ${w}`;el.style.gridRow=`${Number(el.dataset.y||0)+1} / span ${Number(el.dataset.h||3)}`;}}
function payload(){return surfaces().map(el=>({extension_ref:el.dataset.ref,x:Number(el.dataset.x||0),y:Number(el.dataset.y||0),width:Number(el.dataset.w||4),height:Number(el.dataset.h||3),visible:true,config:{}}));}
async function save(){await fetch('/api/layout',{method:'POST',headers:{'Content-Type':'application/json','X-LifeHub-Token':token},body:JSON.stringify(payload())});}
let editing=false;editButton.addEventListener('click',()=>{editing=!editing;document.body.classList.toggle('edit-mode',editing);editButton.classList.toggle('active',editing);editButton.textContent=editing?'Done':'Edit';surfaces().forEach(el=>el.classList.toggle('editing',editing));});
for(const el of surfaces()){el.querySelectorAll('[data-size]').forEach(btn=>btn.addEventListener('click',async()=>{if(!editing)return;const axis=btn.dataset.size;if(axis==='w')el.dataset.w=String(Math.min(12,Number(el.dataset.w||4)+1));if(axis==='h')el.dataset.h=String(Math.min(12,Number(el.dataset.h||3)+1));if(axis==='w-')el.dataset.w=String(Math.max(1,Number(el.dataset.w||4)-1));if(axis==='h-')el.dataset.h=String(Math.max(1,Number(el.dataset.h||3)-1));applyGrid();await save();}));}
window.addEventListener('resize',applyGrid);applyGrid();
for(const button of document.querySelectorAll('[data-decision]')){button.addEventListener('click',async()=>{const message=document.querySelector('#decision-message');button.disabled=true;message.textContent='';try{const response=await fetch('/api/decision',{method:'POST',headers:{'Content-Type':'application/json','X-LifeHub-Token':token},body:JSON.stringify({type:button.dataset.type,action:button.dataset.decision,id:Number(button.dataset.id)})});if(!response.ok){throw new Error((await response.text()).trim()||'Decision failed');}window.location.replace('/?reviewed=1#reviews');}catch(error){message.textContent=error.message;button.disabled=false;}});}
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _primitive_payload(extension: RegisteredExtension, records: list[dict[str, Any]]) -> str:
    config = extension.contribution.config
    if not records:
        return '<div class="empty">No local data yet.</div>'
    latest = records[0]
    payload = latest["payload"]
    renderer = str(config.get("renderer", "list"))
    limit = max(1, min(50, int(config.get("limit", 8))))
    if renderer == "text":
        value = payload.get("text") if isinstance(payload, dict) else payload
        body = f'<div class="text-block">{_esc(value or "")}</div>'
    elif renderer == "metric":
        metrics = payload.get("metrics", []) if isinstance(payload, dict) else []
        cells = []
        for metric in metrics[:limit]:
            if not isinstance(metric, dict):
                continue
            cells.append(
                '<div class="metric">'
                f'<div class="metric-label">{_esc(metric.get("label", "Metric"))}</div>'
                f'<div class="metric-value">{_esc(metric.get("value", "—"))}</div>'
                f'<div class="metric-delta">{_esc(metric.get("delta", ""))}</div>'
                "</div>"
            )
        body = '<div class="metric-grid">' + "".join(cells) + "</div>"
    elif renderer == "table":
        columns = payload.get("columns", []) if isinstance(payload, dict) else []
        rows = payload.get("rows", []) if isinstance(payload, dict) else []
        head = "".join(f"<th>{_esc(col)}</th>" for col in columns)
        row_html = [
            "<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in row) + "</tr>"
            for row in rows[:limit]
            if isinstance(row, list)
        ]
        body = f'<table class="table"><thead><tr>{head}</tr></thead><tbody>{"".join(row_html)}</tbody></table>'
    else:
        items = payload.get("items", []) if isinstance(payload, dict) else []
        rows = []
        for item in items[:limit]:
            if isinstance(item, dict):
                rows.append(
                    '<div class="list-row">'
                    f"<strong>{_esc(item.get('title', item.get('label', 'Item')))}</strong>"
                    f"<span>{_esc(item.get('detail', item.get('value', '')))}</span>"
                    "</div>"
                )
            else:
                rows.append(f'<div class="list-row"><strong>{_esc(item)}</strong></div>')
        body = '<div class="list">' + "".join(rows) + "</div>"
    return body + f'<div class="stamp">local · observed {_esc(latest["observed_at"])}</div>'


def _extension_body(hub: LifeHub, extension: RegisteredExtension) -> str:
    contribution = extension.contribution
    if contribution.entrypoint != "lifehub.primitive":
        return (
            '<div class="custom-surface">Custom extension surface registered.<br>'
            f"entrypoint: <strong>{_esc(contribution.entrypoint or 'declarative')}</strong><br>"
            "The v0.2 kernel preserves this contribution without forcing it into a built-in renderer."
            "</div>"
        )
    if contribution.contract not in (None, "lifehub.primitive@1"):
        return '<div class="empty">Unsupported surface contract.</div>'
    namespace = str(contribution.config.get("namespace", ""))
    records = hub.store.latest_records(namespace, limit=int(contribution.config.get("limit", 8)))
    return _primitive_payload(extension, records)


def _decision_button(
    kind: str, action: str, item_id: int, label: str, primary: bool = False
) -> str:
    style = ' class="primary"' if primary else ""
    return (
        f'<button{style} data-type="{_esc(kind)}" data-decision="{_esc(action)}" '
        f'data-id="{item_id}">{_esc(label)}</button>'
    )


def render_review_inbox(hub: LifeHub) -> str:
    cards: list[str] = []
    for item in hub.proposals.list():
        payload = json.dumps(item["payload"], indent=2, ensure_ascii=False, sort_keys=True)
        buttons = _decision_button("proposal", "approve", item["id"], "Commit change", True)
        buttons += _decision_button("proposal", "reject", item["id"], "Reject")
        cards.append(
            '<article class="review-card"><span class="review-status">Local change · pending</span>'
            f"<h3>{_esc(item['namespace'])} / {_esc(item['record_key'])}</h3>"
            '<div class="review-meta">'
            f"<div><strong>From:</strong> {_esc(item['extension_ref'])}</div>"
            f"<div><strong>Base record:</strong> {_esc(item['base_record_id'] or 'new')}</div>"
            f"<div><strong>Package digest:</strong> {_esc(item['package_hash'])}</div></div>"
            f'<pre class="review-payload">{_esc(payload)}</pre>'
            f'<div class="review-actions">{buttons}</div></article>'
        )
    for status in ("pending", "approved", "in_flight", "unknown"):
        for item in hub.effects.list(status):
            payload = json.dumps(item["payload"], indent=2, ensure_ascii=False, sort_keys=True)
            buttons = ""
            if status == "pending":
                buttons = _decision_button("effect", "approve", item["id"], "Approve request", True)
                buttons += _decision_button("effect", "reject", item["id"], "Reject")
            elif status == "approved":
                if item["kind"] == "test.record":
                    buttons = _decision_button(
                        "effect", "dispatch_fake", item["id"], "Run local test", True
                    )
                buttons += _decision_button("effect", "reject", item["id"], "Cancel")
            note = ""
            if status in {"in_flight", "unknown"}:
                note = '<p class="review-note">Outcome needs manual investigation. This request cannot be run again.</p>'
            cards.append(
                f'<article class="review-card"><span class="review-status">External request · {_esc(status)}</span>'
                f"<h3>{_esc(item['kind'])} → {_esc(item['destination'])}</h3>"
                '<div class="review-meta">'
                f"<div><strong>Purpose:</strong> {_esc(item['purpose'])}</div>"
                f"<div><strong>From:</strong> {_esc(item['extension_ref'])}</div>"
                f"<div><strong>Package digest:</strong> {_esc(item['package_hash'])}</div></div>"
                f'<pre class="review-payload">{_esc(payload)}</pre>'
                f'<div class="review-actions">{buttons}</div>{note}</article>'
            )
    content = (
        "".join(cards)
        if cards
        else '<div class="review-card review-note">Nothing needs review.</div>'
    )
    return (
        '<section class="review-section" id="reviews">'
        '<div class="review-header"><div><div class="eyebrow">Your decision</div>'
        "<h2>Review inbox</h2><p>Inspect each change or disclosure before approving it.</p>"
        f'</div><span class="review-count">{len(cards)} items</span></div>'
        '<div id="decision-message" class="review-message" role="alert"></div>'
        f'<div class="review-grid">{content}</div></section>'
    )


def render_workspace(hub: LifeHub, *, token: str, workspace_id: str = "home") -> str:
    catalog = hub.catalog()
    refs = {entry["ref"] for entry in catalog["extensions"]}
    cards: list[str] = []
    for item in hub.store.workspace_layout(workspace_id):
        if not item["visible"]:
            continue
        if str(item["extension_ref"]) not in refs:
            continue
        try:
            extension = hub.extension(str(item["extension_ref"]))
        except KeyError:
            continue
        contribution = extension.contribution
        description = contribution.config.get("description") or contribution.point
        cards.append(
            f"""
            <section class="surface" data-ref="{_esc(extension.ref)}" data-x="{item["x"]}" data-y="{item["y"]}" data-w="{item["width"]}" data-h="{item["height"]}">
              <div class="surface-head"><div><div class="kicker">{_esc(extension.plugin_name)} · {_esc(contribution.point)}</div><div class="surface-title">{_esc(contribution.title or contribution.id)}</div><div class="surface-desc">{_esc(description)}</div></div>
              <div class="edit-controls"><button data-size="w-">−W</button><button data-size="w">+W</button><button data-size="h-">−H</button><button data-size="h">+H</button></div></div>
              <div class="surface-body">{_extension_body(hub, extension)}</div>
            </section>"""
        )
    points = len({entry["point"] for entry in catalog["extensions"]})
    return f"""<!doctype html><html lang="en" data-token="{_esc(token)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LifeHub</title><link rel="stylesheet" href="/assets/app.css"></head><body>
<div class="shell"><header class="topbar"><div class="brand"><div class="mark">LH</div>LifeHub <span class="topmeta">extension host · local kernel</span></div><div class="actions"><a href="#reviews">Review inbox</a><button id="edit-toggle">Edit</button></div></header>
<section class="hero"><div class="eyebrow">Workspace / Home</div><h1>A local host for whatever comes next.</h1><p>The board below is only one consumer of the extension registry. LifeHub Core does not define your life domains or a closed list of plugin types.</p><div class="status"><span class="pill">Local persistence</span><span class="pill neutral">{len(catalog["packages"])} packages</span><span class="pill neutral">{len(catalog["extensions"])} extensions</span><span class="pill neutral">{points} extension points</span></div></section>
<div class="boardbar"><h2>Home</h2><div class="hint">temporary workspace consumer · Edit changes local layout only</div></div><main class="board">{"".join(cards)}</main>{render_review_inbox(hub)}<div class="footer">LifeHub Kernel v0.2 · personal and derived data remains local</div></div><script src="/assets/app.js"></script></body></html>"""


def _decide(hub: LifeHub, payload: object) -> str:
    if not isinstance(payload, dict) or set(payload) != {"type", "action", "id"}:
        raise ValueError("invalid decision")
    item_id = payload["id"]
    if type(item_id) is not int or item_id < 1:
        raise ValueError("invalid item ID")
    kind, action = payload["type"], payload["action"]
    if kind == "proposal" and action == "approve":
        return hub.approve_proposal(item_id)
    if kind == "proposal" and action == "reject":
        hub.proposals.reject(item_id)
        return "rejected"
    if kind == "effect" and action == "approve":
        hub.approve_effect(item_id)
        return "approved"
    if kind == "effect" and action == "reject":
        hub.effects.reject(item_id)
        return "rejected"
    if kind == "effect" and action == "dispatch_fake":
        if hub.effects.get(item_id)["kind"] != "test.record":
            raise PermissionError("only local test effects can run here")
        return hub.dispatch_effect(item_id)
    raise ValueError("invalid decision")


def make_handler(*, db_path: str | Path, plugins_path: str | Path, token: str):
    class Handler(BaseHTTPRequestHandler):
        def _valid_host(self) -> bool:
            host = self.headers.get("Host", "")
            try:
                parsed = urlsplit(f"http://{host}")
                return (
                    parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                    and parsed.port == self.server.server_port
                    and parsed.path == ""
                    and parsed.query == ""
                    and parsed.fragment == ""
                    and "@" not in host
                )
            except ValueError:
                return False

        def _send(self, data: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if not self._valid_host():
                self._send(b"forbidden\n", "text/plain; charset=utf-8", 403)
                return
            path = urlparse(self.path).path
            if path == "/assets/app.css":
                self._send(CSS.encode(), "text/css; charset=utf-8")
                return
            if path == "/assets/app.js":
                self._send(JS.encode(), "application/javascript; charset=utf-8")
                return
            if path == "/healthz":
                self._send(b"ok\n", "text/plain; charset=utf-8")
                return
            if path != "/":
                self._send(b"not found\n", "text/plain; charset=utf-8", 404)
                return
            hub = LifeHub(db_path=db_path, plugins_path=plugins_path)
            try:
                page = render_workspace(hub, token=token)
            finally:
                hub.close()
            self._send(page.encode(), "text/html; charset=utf-8")

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path not in {"/api/layout", "/api/decision"}:
                self._send(b"not found\n", "text/plain; charset=utf-8", 404)
                return
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if (
                not self._valid_host()
                or (origin is not None and origin != f"http://{host}")
                or self.headers.get("X-LifeHub-Token") != token
            ):
                self._send(b"forbidden\n", "text/plain; charset=utf-8", 403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if (
                    length < 1
                    or length > 100_000
                    or self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    != "application/json"
                ):
                    raise ValueError("invalid request body")
                payload = json.loads(self.rfile.read(length))
                hub = LifeHub(db_path=db_path, plugins_path=plugins_path)
                try:
                    if path == "/api/layout":
                        if not isinstance(payload, list):
                            raise ValueError("layout must be a list")
                        hub.store.save_workspace_layout(payload)
                        result = "ok"
                    else:
                        result = _decide(hub, payload)
                finally:
                    hub.close()
            except (ValueError, TypeError, KeyError):
                self._send(b"bad request\n", "text/plain; charset=utf-8", 400)
                return
            except PermissionError:
                self._send(b"forbidden\n", "text/plain; charset=utf-8", 403)
                return
            self._send(f"{result}\n".encode(), "text/plain; charset=utf-8")

        def log_message(self, format: str, *args) -> None:  # noqa: A002, ANN002
            return

    return Handler


def serve(
    *, db_path: str | Path, plugins_path: str | Path, host: str = "127.0.0.1", port: int = 8844
) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("LifeHub v0.2 shell is loopback-only")
    token = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(
        (host, port),
        make_handler(db_path=db_path, plugins_path=plugins_path, token=token),
    )
    print(f"LifeHub: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
