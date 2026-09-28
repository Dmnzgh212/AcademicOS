from __future__ import annotations

import html
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from academicos.lifehub.core import LifeHub, WidgetSpec


CSS = r"""
:root{color-scheme:light;--bg:#f3f4f6;--panel:#fff;--ink:#17181c;--muted:#70747d;--line:#e3e5e8;--accent:#5b5ce2;--soft:#eeefff;--good:#0b775d;--warn:#a46315}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
.shell{min-height:100vh;display:grid;grid-template-columns:220px 1fr}.sidebar{background:#181a20;color:#fff;padding:22px 16px;position:sticky;top:0;height:100vh}.brand{font-weight:800;font-size:17px;letter-spacing:-.03em;padding:4px 8px 24px}.brand small{display:block;color:#818691;font-size:9px;text-transform:uppercase;letter-spacing:.12em;margin-top:4px}.side-section{margin:18px 8px 0;padding-top:16px;border-top:1px solid rgba(255,255,255,.08)}.side-label{font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:#777c86;margin-bottom:9px}.side-item{font-size:11px;color:#a7abb4;padding:8px 0}.side-item strong{color:#fff;font-weight:650}.privacy{position:absolute;bottom:22px;left:24px;right:24px;color:#737984;font-size:9px;line-height:1.5}
.main{padding:28px 30px 50px;max-width:1600px;width:100%;margin:0 auto}.topbar{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;margin-bottom:22px}.eyebrow{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.12em;font-weight:750}h1{font-size:34px;letter-spacing:-.045em;margin:6px 0 3px}.subtitle{font-size:11px;color:var(--muted)}.pill{padding:7px 10px;border-radius:999px;background:#e8f6f1;color:var(--good);font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.05em}
.workspace-toolbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.workspace-title{font-size:12px;font-weight:750}.hint{font-size:9px;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-auto-flow:row dense;gap:12px;align-items:stretch}.widget{background:var(--panel);border:1px solid var(--line);border-radius:17px;min-height:190px;box-shadow:0 12px 30px rgba(24,26,32,.04);overflow:hidden;transition:transform .12s,border-color .12s;position:relative}.widget.dragging{opacity:.45;transform:scale(.99)}.widget.drag-over{border-color:var(--accent);box-shadow:0 0 0 2px var(--soft)}.widget[data-w="2"]{grid-column:span 2}.widget[data-w="3"]{grid-column:span 3}.widget[data-h="2"]{min-height:390px}.widget[data-h="3"]{min-height:590px}.widget-head{display:flex;justify-content:space-between;gap:10px;padding:14px 15px 10px;border-bottom:1px solid #f0f1f2}.widget-kicker{font-size:8px;color:#9a9ea7;text-transform:uppercase;letter-spacing:.08em;font-weight:750}.widget-title{font-size:13px;font-weight:760;margin-top:3px}.widget-desc{font-size:9px;color:var(--muted);margin-top:4px}.widget-controls{display:flex;gap:4px}.widget-controls button{border:1px solid var(--line);background:#fafafa;color:#747983;border-radius:7px;font-size:9px;padding:4px 6px;cursor:pointer}.widget-controls button:hover{border-color:#cfd2d7;color:#30333a}.widget-body{padding:13px 15px 16px}.empty{font-size:10px;color:var(--muted);padding:15px 0}.stamp{font-size:8px;color:#a1a5ad;margin-top:12px}.list{display:grid;gap:8px}.list-row{padding:9px 10px;background:#f8f8f6;border-radius:10px}.list-row strong{font-size:10.5px;display:block}.list-row span{display:block;color:var(--muted);font-size:9px;margin-top:3px;line-height:1.4}.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metric{background:#f8f8f6;border-radius:11px;padding:11px}.metric-label{font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.metric-value{font-size:18px;font-weight:780;letter-spacing:-.03em;margin-top:4px}.metric-delta{font-size:9px;margin-top:3px;color:var(--muted)}.text-block{font-size:10.5px;line-height:1.6;white-space:pre-wrap}.table{width:100%;border-collapse:collapse;font-size:9px}.table td,.table th{padding:7px 6px;border-bottom:1px solid #eee;text-align:left}.table th{color:var(--muted);font-weight:700}.statusbar{margin-top:14px;font-size:8.5px;color:#9da1a9;text-align:center}
@media(max-width:1050px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.widget[data-w="3"]{grid-column:span 2}}@media(max-width:760px){.shell{grid-template-columns:1fr}.sidebar{display:none}.main{padding:20px 12px 35px}.grid{grid-template-columns:1fr}.widget[data-w="2"],.widget[data-w="3"]{grid-column:span 1}.topbar{align-items:flex-start;flex-direction:column}}
"""


JS = r"""
const token = document.documentElement.dataset.token;
const grid = document.querySelector('.grid');
let dragged = null;

function cards(){ return [...grid.querySelectorAll('.widget')]; }
function payload(){
  return cards().map((card) => ({
    plugin_id: card.dataset.plugin,
    widget_id: card.dataset.widget,
    width: Number(card.dataset.w || 1),
    height: Number(card.dataset.h || 1),
    visible: true
  }));
}
async function save(){
  await fetch('/api/layout', {method:'POST', headers:{'Content-Type':'application/json','X-LifeHub-Token':token}, body:JSON.stringify(payload())});
}
for(const card of cards()){
  card.addEventListener('dragstart', () => { dragged = card; card.classList.add('dragging'); });
  card.addEventListener('dragend', () => { card.classList.remove('dragging'); dragged = null; cards().forEach(c=>c.classList.remove('drag-over')); save(); });
  card.addEventListener('dragover', (e) => { e.preventDefault(); if(card !== dragged) card.classList.add('drag-over'); });
  card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
  card.addEventListener('drop', (e) => { e.preventDefault(); card.classList.remove('drag-over'); if(dragged && card !== dragged) grid.insertBefore(dragged, card); });
}
document.querySelectorAll('[data-resize]').forEach((button) => button.addEventListener('click', async () => {
  const card = button.closest('.widget');
  const axis = button.dataset.resize;
  const key = axis === 'w' ? 'w' : 'h';
  const next = Number(card.dataset[key] || 1) % 3 + 1;
  card.dataset[key] = String(next);
  await save();
}));
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _format_payload(widget: WidgetSpec, records: list[dict[str, Any]]) -> str:
    if not records:
        return '<div class="empty">No local data yet.</div>'
    latest = records[0]
    payload = latest["payload"]
    if widget.renderer == "text":
        value = payload.get("text") if isinstance(payload, dict) else payload
        body = f'<div class="text-block">{_esc(value or "")}</div>'
    elif widget.renderer == "metric":
        metrics = payload.get("metrics", []) if isinstance(payload, dict) else []
        cells = []
        for metric in metrics[:8]:
            if not isinstance(metric, dict):
                continue
            cells.append(
                '<div class="metric">'
                f'<div class="metric-label">{_esc(metric.get("label", "Metric"))}</div>'
                f'<div class="metric-value">{_esc(metric.get("value", "—"))}</div>'
                f'<div class="metric-delta">{_esc(metric.get("delta", ""))}</div>'
                '</div>'
            )
        body = '<div class="metric-grid">' + "".join(cells) + "</div>"
    elif widget.renderer == "table":
        columns = payload.get("columns", []) if isinstance(payload, dict) else []
        rows = payload.get("rows", []) if isinstance(payload, dict) else []
        head = "".join(f"<th>{_esc(col)}</th>" for col in columns)
        row_html = []
        for row in rows[: widget.limit]:
            if isinstance(row, list):
                row_html.append("<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in row) + "</tr>")
        body = f'<table class="table"><thead><tr>{head}</tr></thead><tbody>{"".join(row_html)}</tbody></table>'
    else:
        items = payload.get("items", []) if isinstance(payload, dict) else []
        rows = []
        for item in items[: widget.limit]:
            if isinstance(item, dict):
                rows.append(
                    '<div class="list-row">'
                    f'<strong>{_esc(item.get("title", item.get("label", "Item")))}</strong>'
                    f'<span>{_esc(item.get("detail", item.get("value", "")))}</span>'
                    '</div>'
                )
            else:
                rows.append(f'<div class="list-row"><strong>{_esc(item)}</strong></div>')
        body = '<div class="list">' + "".join(rows) + "</div>"
    return body + f'<div class="stamp">local · observed {_esc(latest["observed_at"])}</div>'


def render_workspace(hub: LifeHub, *, token: str, workspace_id: str = "home") -> str:
    bundles = {bundle.manifest.id: bundle for bundle in hub.bundles}
    layout = hub.store.workspace_layout(workspace_id)
    cards: list[str] = []
    for item in layout:
        if not item["visible"]:
            continue
        bundle = bundles.get(item["plugin_id"])
        if bundle is None:
            continue
        widget = next((w for w in bundle.manifest.widgets if w.id == item["widget_id"]), None)
        if widget is None:
            continue
        records = hub.store.latest_records(widget.namespace, limit=widget.limit)
        cards.append(
            f"""
            <section class="widget" draggable="true" data-plugin="{_esc(bundle.manifest.id)}"
              data-widget="{_esc(widget.id)}" data-w="{int(item['width'])}" data-h="{int(item['height'])}">
              <div class="widget-head">
                <div>
                  <div class="widget-kicker">{_esc(bundle.manifest.name)}</div>
                  <div class="widget-title">{_esc(widget.title)}</div>
                  <div class="widget-desc">{_esc(widget.description or widget.namespace)}</div>
                </div>
                <div class="widget-controls">
                  <button type="button" title="Cycle width" data-resize="w">W</button>
                  <button type="button" title="Cycle height" data-resize="h">H</button>
                </div>
              </div>
              <div class="widget-body">{_format_payload(widget, records)}</div>
            </section>
            """
        )
    plugin_summary = "".join(
        f'<div class="side-item"><strong>{_esc(b.manifest.name)}</strong><br>{_esc(b.manifest.id)}</div>'
        for b in hub.bundles
    ) or '<div class="side-item">No plugins discovered</div>'
    return f"""<!doctype html>
<html lang="en" data-token="{_esc(token)}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LifeHub</title><link rel="stylesheet" href="/assets/app.css"></head>
<body><div class="shell">
<aside class="sidebar"><div class="brand">LifeHub<small>local personal platform</small></div><div class="side-section"><div class="side-label">Installed</div>{plugin_summary}</div><div class="privacy">Personal and derived data stays local.<br>Outbound retrieval goes through declared permissions.</div></aside>
<main class="main"><header class="topbar"><div><div class="eyebrow">Workspace / home</div><h1>Your life, assembled locally.</h1><div class="subtitle">Drag widgets. Resize them. Add functionality by dropping in plugins, not by rewriting the shell.</div></div><div class="pill">Local data</div></header>
<div class="workspace-toolbar"><div class="workspace-title">Home</div><div class="hint">drag to reorder · W/H changes widget size</div></div><div class="grid">{''.join(cards)}</div><div class="statusbar">LifeHub Core v0.1 · {len(hub.bundles)} plugin(s) · no cloud account required</div>
</main></div><script src="/assets/app.js"></script></body></html>"""


def make_handler(
    *,
    db_path: str | Path,
    plugins_path: str | Path,
    token: str,
):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, data: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
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
            if urlparse(self.path).path != "/api/layout":
                self._send(b"not found\n", "text/plain; charset=utf-8", 404)
                return
            if self.headers.get("X-LifeHub-Token") != token:
                self._send(b"forbidden\n", "text/plain; charset=utf-8", 403)
                return
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 100_000)
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, list):
                    raise ValueError("layout must be a list")
                hub = LifeHub(db_path=db_path, plugins_path=plugins_path)
                try:
                    hub.store.save_workspace_layout(payload)
                finally:
                    hub.close()
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                self._send(b"bad request\n", "text/plain; charset=utf-8", 400)
                return
            self._send(b"ok\n", "text/plain; charset=utf-8")

        def log_message(self, format: str, *args) -> None:  # noqa: A002, ANN002
            return

    return Handler


def serve(
    *,
    db_path: str | Path = "data/lifehub.db",
    plugins_path: str | Path = "lifehub_plugins",
    host: str = "127.0.0.1",
    port: int = 8844,
) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("LifeHub v0.1 only binds to loopback")
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
