from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from academicos.briefing import MorningBrief, build_morning_brief
from academicos.calendar.truth import effective_sessions_for_range
from academicos.storage.db import connect_db, initialize_db
from academicos.web.theme import WEB_CSS

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _minutes_label(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def _date_link(day: date) -> str:
    return f"/?date={day.isoformat()}"


def _timeline_html(brief: MorningBrief) -> str:
    items: list[tuple[datetime, str]] = []
    for session in brief.sessions:
        section = f" {session.course_section}" if session.course_section else ""
        location = f" · {_esc(session.location)}" if session.location else ""
        mode = f" · {_esc(session.delivery_mode)}" if session.delivery_mode else ""
        items.append(
            (
                session.start_at,
                f"""
                <div class="timeline-item">
                  <div class="timeline-time">{session.start_at:%H:%M}</div>
                  <div class="timeline-rail"><span class="timeline-dot fact"></span></div>
                  <div class="timeline-content">
                    <div class="timeline-main">
                      <div class="timeline-name">{_esc(session.course_code)}{_esc(section)} · {_esc(session.session_type.value.title())}</div>
                      <span class="badge fact">Confirmed</span>
                    </div>
                    <div class="timeline-meta">{session.start_at:%H:%M}–{session.end_at:%H:%M}{location}{mode}</div>
                  </div>
                </div>
                """,
            )
        )

    for block in brief.plan_blocks:
        course = f"{_esc(block.course_code)} · " if block.course_code else ""
        pinned = " · pinned" if block.pinned else ""
        items.append(
            (
                block.start_at,
                f"""
                <div class="timeline-item">
                  <div class="timeline-time">{block.start_at:%H:%M}</div>
                  <div class="timeline-rail"><span class="timeline-dot"></span></div>
                  <div class="timeline-content">
                    <div class="timeline-main">
                      <div class="timeline-name">{course}{_esc(block.task_title)}</div>
                      <span class="badge plan">Plan</span>
                    </div>
                    <div class="timeline-meta">{block.start_at:%H:%M}–{block.end_at:%H:%M} · {_minutes_label(block.minutes)}{pinned}</div>
                  </div>
                </div>
                """,
            )
        )

    items.sort(key=lambda item: item[0])
    if not items:
        return '<div class="empty">Nothing fixed or planned yet. Your day is open.</div>'
    return '<div class="timeline">' + "".join(markup for _, markup in items) + "</div>"


def _changes_html(brief: MorningBrief) -> str:
    if not brief.pending_changes:
        return '<div class="empty">No changes waiting for review.</div>'
    rows: list[str] = []
    for item in brief.pending_changes[:6]:
        course = item.course_code or "Academic"
        if item.course_section:
            course += f" {item.course_section}"
        rows.append(
            f"""
            <div class="list-item">
              <div class="list-top">
                <div class="list-title">{_esc(item.title)}</div>
                <div class="confidence">{item.confidence:.0%}</div>
              </div>
              <div class="list-meta">{_esc(course)} · {_esc(item.kind.value.replace('_', ' '))}</div>
            </div>
            """
        )
    return '<div class="list">' + "".join(rows) + "</div>"


def _tasks_html(brief: MorningBrief) -> str:
    if not brief.upcoming_tasks:
        return '<div class="empty">No upcoming tracked deadlines.</div>'
    rows: list[str] = []
    for task in brief.upcoming_tasks[:6]:
        course = task.course_code or "General"
        due = task.due_at.strftime("%a %b %d · %H:%M") if task.due_at else "No deadline"
        rows.append(
            f"""
            <div class="list-item">
              <div class="list-top">
                <div class="list-title">{_esc(task.title)}</div>
                <span class="badge plan">{_minutes_label(task.remaining_minutes)}</span>
              </div>
              <div class="list-meta">{_esc(course)} · {_esc(due)}</div>
            </div>
            """
        )
    return '<div class="list">' + "".join(rows) + "</div>"


def _activity_html(brief: MorningBrief) -> str:
    if not brief.activities:
        return '<div class="empty">No new academic activity in the current lookback window.</div>'
    rows: list[str] = []
    for activity in brief.activities[:5]:
        course = activity.course_code or "Academic"
        when = activity.occurred_at.strftime("%b %d · %H:%M") if activity.occurred_at else ""
        rows.append(
            f"""
            <div class="list-item">
              <div class="list-title">{_esc(activity.title)}</div>
              <div class="list-meta">{_esc(course)} · {_esc(activity.kind)} · {_esc(when)}</div>
            </div>
            """
        )
    return '<div class="list">' + "".join(rows) + "</div>"


def _alerts_html(brief: MorningBrief) -> str:
    rows: list[str] = []
    for alert in brief.alerts:
        ok = alert.startswith("No immediate")
        rows.append(f'<div class="alert{" ok" if ok else ""}">{_esc(alert)}</div>')
    return '<div class="alerts">' + "".join(rows) + "</div>"


def _week_html(conn, target_date: date, timezone_name: str) -> str:  # noqa: ANN001
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    week = effective_sessions_for_range(
        conn,
        monday,
        sunday,
        timezone_name=timezone_name,
    )
    pills: list[str] = []
    current = monday
    while current <= sunday:
        active = " active" if current == target_date else ""
        count = len(week[current])
        pills.append(
            f"""
            <a class="day-pill{active}" href="{_date_link(current)}">
              <div class="day-name">{current:%a}</div>
              <div class="day-num">{current.day}</div>
              <div class="day-count">{count} class{'es' if count != 1 else ''}</div>
            </a>
            """
        )
        current += timedelta(days=1)
    return '<div class="week-strip">' + "".join(pills) + "</div>"


def render_dashboard(
    conn,
    target_date: date,
    *,
    timezone_name: str = "America/Toronto",
    now: datetime | None = None,
) -> str:  # noqa: ANN001
    tz = ZoneInfo(timezone_name)
    local_now = now or datetime.now(tz)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=tz)
    else:
        local_now = local_now.astimezone(tz)

    brief = build_morning_brief(
        conn,
        target_date,
        now=local_now,
        timezone_name=timezone_name,
    )
    planned_minutes = sum(block.minutes for block in brief.plan_blocks)
    deadline_count = sum(task.due_at is not None for task in brief.upcoming_tasks)
    yesterday = target_date - timedelta(days=1)
    tomorrow = target_date + timedelta(days=1)
    today_link = _date_link(local_now.date())

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>AcademicOS · Today</title>
  <link rel="stylesheet" href="/assets/app.css">
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand"><div class="brand-mark">AO</div><span>AcademicOS</span></div>
    <nav class="nav">
      <a class="active" href="{_date_link(target_date)}"><span class="nav-dot"></span>Today</a>
      <a href="#week"><span class="nav-dot"></span>Week</a>
      <a href="#changes"><span class="nav-dot"></span>Changes</a>
      <a href="#tasks"><span class="nav-dot"></span>Tasks</a>
      <a href="#activity"><span class="nav-dot"></span>Activity</a>
    </nav>
    <div class="sidebar-foot">Local dashboard<br>Data stays on this machine by default.</div>
  </aside>

  <main class="main">
    <header class="topbar">
      <div>
        <div class="eyebrow">Academic command center</div>
        <h1>{target_date:%A}</h1>
        <div class="subtitle">{target_date:%B %d, %Y} · {timezone_name}</div>
      </div>
      <div class="date-nav">
        <a aria-label="Previous day" href="{_date_link(yesterday)}">←</a>
        <a href="{today_link}">Today</a>
        <span class="date-chip">{target_date:%b %d}</span>
        <a aria-label="Next day" href="{_date_link(tomorrow)}">→</a>
      </div>
    </header>

    <section class="metrics">
      <div class="metric"><div class="metric-label">Confirmed classes</div><div class="metric-value">{len(brief.sessions)}</div><div class="metric-note">Truth Calendar</div></div>
      <div class="metric"><div class="metric-label">Study plan</div><div class="metric-value">{_minutes_label(planned_minutes)}</div><div class="metric-note">Movable blocks today</div></div>
      <div class="metric"><div class="metric-label">Needs review</div><div class="metric-value">{len(brief.pending_changes)}</div><div class="metric-note">Evidence-backed changes</div></div>
      <div class="metric"><div class="metric-label">Upcoming deadlines</div><div class="metric-value">{deadline_count}</div><div class="metric-note">Within planner horizon</div></div>
    </section>

    <section id="week" class="card" style="margin-bottom:16px">
      <div class="card-head"><div><div class="card-title">This week</div><div class="card-subtitle">Confirmed academic rhythm</div></div><span class="badge fact">Truth</span></div>
      {_week_html(conn, target_date, timezone_name)}
    </section>

    <div class="grid">
      <div class="stack">
        <section class="card">
          <div class="card-head"><div><div class="card-title">Today timeline</div><div class="card-subtitle">Confirmed commitments and movable study plan</div></div></div>
          {_timeline_html(brief)}
        </section>
        <section id="activity" class="card">
          <div class="card-head"><div><div class="card-title">New since last check</div><div class="card-subtitle">Recent source activity, not silently promoted to facts</div></div><span class="badge fact">Feed</span></div>
          {_activity_html(brief)}
        </section>
      </div>

      <div class="stack">
        <section class="card">
          <div class="card-head"><div><div class="card-title">Attention</div><div class="card-subtitle">Risk signals from current local state</div></div></div>
          {_alerts_html(brief)}
        </section>
        <section id="changes" class="card">
          <div class="card-head"><div><div class="card-title">Changes inbox</div><div class="card-subtitle">Review before Truth Calendar changes</div></div><span class="badge review">Candidate</span></div>
          {_changes_html(brief)}
        </section>
        <section id="tasks" class="card">
          <div class="card-head"><div><div class="card-title">Upcoming work</div><div class="card-subtitle">Deadlines and remaining workload</div></div><span class="badge plan">Plan</span></div>
          {_tasks_html(brief)}
        </section>
      </div>
    </div>
    <div class="footer-note">AcademicOS · local-first · generated from local SQLite state at {_esc(local_now.strftime('%H:%M'))}</div>
  </main>
</div>
</body>
</html>"""


def make_handler(
    db_path: str | Path,
    *,
    timezone_name: str = "America/Toronto",
):
    database = Path(db_path)

    class DashboardHandler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/assets/app.css":
                self._send(WEB_CSS.encode("utf-8"), "text/css; charset=utf-8")
                return
            if parsed.path == "/healthz":
                self._send(b"ok\n", "text/plain; charset=utf-8")
                return
            if parsed.path != "/":
                self._send(b"Not found\n", "text/plain; charset=utf-8", status=404)
                return

            query = parse_qs(parsed.query)
            tz = ZoneInfo(timezone_name)
            raw_date = query.get("date", [datetime.now(tz).date().isoformat()])[0]
            try:
                target_date = date.fromisoformat(raw_date)
            except ValueError:
                self._send(b"Invalid date\n", "text/plain; charset=utf-8", status=400)
                return

            conn = connect_db(database)
            try:
                initialize_db(conn)
                page = render_dashboard(
                    conn,
                    target_date,
                    timezone_name=timezone_name,
                )
            finally:
                conn.close()
            self._send(page.encode("utf-8"), "text/html; charset=utf-8")

        def log_message(self, format: str, *args) -> None:  # noqa: A002, ANN002
            return

    return DashboardHandler


def serve_dashboard(
    db_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    timezone_name: str = "America/Toronto",
    allow_remote: bool = False,
) -> None:
    """Run the local dashboard. Non-loopback binding requires explicit opt-in."""
    if host not in _LOOPBACK_HOSTS and not allow_remote:
        raise ValueError(
            "refusing non-loopback dashboard bind without allow_remote=True"
        )
    server = ThreadingHTTPServer(
        (host, port),
        make_handler(db_path, timezone_name=timezone_name),
    )
    print(f"AcademicOS dashboard: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
