from __future__ import annotations

import html
from datetime import date, datetime, time, timedelta
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


def _parse_local(value: str, tz: ZoneInfo) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _timeline_items(brief: MorningBrief) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for session in brief.sessions:
        section = f" {session.course_section}" if session.course_section else ""
        items.append(
            {
                "start": session.start_at,
                "end": session.end_at,
                "title": f"{session.course_code}{section} · {session.session_type.value.title()}",
                "meta": session.location or session.delivery_mode or "Confirmed class",
                "kind": "fact",
            }
        )
    for block in brief.plan_blocks:
        course = f"{block.course_code} · " if block.course_code else ""
        items.append(
            {
                "start": block.start_at,
                "end": block.end_at,
                "title": f"{course}{block.task_title}",
                "meta": f"{_minutes_label(block.minutes)}{' · pinned' if block.pinned else ''}",
                "kind": "plan",
            }
        )
    items.sort(key=lambda item: item["start"])
    return items


def _now_next_html(brief: MorningBrief, local_now: datetime) -> str:
    items = _timeline_items(brief)
    current = next(
        (
            item
            for item in items
            if item["start"] <= local_now < item["end"]
        ),
        None,
    )
    upcoming = next((item for item in items if item["start"] > local_now), None)

    if brief.target_date != local_now.date():
        upcoming = items[0] if items else None
        current = None

    if current:
        now_title = _esc(current["title"])
        now_meta = f"until {current['end']:%H:%M} · {_esc(current['meta'])}"
        now_state = "In progress"
    else:
        now_title = "Open time"
        now_meta = "No confirmed class or study block right now."
        now_state = "Available"

    if upcoming:
        next_title = _esc(upcoming["title"])
        next_meta = f"{upcoming['start']:%H:%M}–{upcoming['end']:%H:%M} · {_esc(upcoming['meta'])}"
    else:
        next_title = "Day clear"
        next_meta = "No later commitment or planned study block."

    return f"""
    <div class="now-next">
      <div class="now-card">
        <div class="micro-label">Now</div>
        <div class="now-state">{_esc(now_state)}</div>
        <div class="now-title">{now_title}</div>
        <div class="now-meta">{now_meta}</div>
      </div>
      <div class="now-card next">
        <div class="micro-label">Next</div>
        <div class="now-title">{next_title}</div>
        <div class="now-meta">{next_meta}</div>
      </div>
    </div>
    """


def _timeline_html(brief: MorningBrief) -> str:
    items = _timeline_items(brief)
    if not items:
        return '<div class="empty">Nothing fixed or planned yet. Your day is open.</div>'

    rows: list[str] = []
    for item in items:
        kind = str(item["kind"])
        rows.append(
            f"""
            <div class="timeline-item">
              <div class="timeline-time">{item['start']:%H:%M}</div>
              <div class="timeline-rail"><span class="timeline-dot {kind}"></span></div>
              <div class="timeline-content">
                <div class="timeline-main">
                  <div class="timeline-name">{_esc(item['title'])}</div>
                  <span class="badge {kind}">{'Confirmed' if kind == 'fact' else 'Movable'}</span>
                </div>
                <div class="timeline-meta">{item['start']:%H:%M}–{item['end']:%H:%M} · {_esc(item['meta'])}</div>
              </div>
            </div>
            """
        )
    return '<div class="timeline">' + "".join(rows) + "</div>"


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
            <div class="list-item change-item">
              <div class="list-top">
                <div>
                  <div class="list-kicker">{_esc(course)}</div>
                  <div class="list-title">{_esc(item.title)}</div>
                </div>
                <div class="confidence">{item.confidence:.0%}</div>
              </div>
              <div class="list-meta">{_esc(item.kind.value.replace('_', ' '))}</div>
              <div class="evidence">{_esc(item.excerpt[:180])}</div>
            </div>
            """
        )
    return '<div class="list">' + "".join(rows) + "</div>"


def _task_pressure(task, now: datetime) -> tuple[str, str]:  # noqa: ANN001
    if task.due_at is None:
        return "normal", "No deadline"
    delta = task.due_at - now
    hours = delta.total_seconds() / 3600
    if hours < 0:
        return "risk", "Overdue"
    if hours <= 24:
        return "risk", f"Due in {max(1, int(hours))}h"
    if hours <= 72:
        return "review", f"Due in {max(1, int(hours // 24))}d"
    return "normal", task.due_at.strftime("%a %b %d")


def _tasks_html(brief: MorningBrief, now: datetime) -> str:
    if not brief.upcoming_tasks:
        return '<div class="empty">No upcoming tracked deadlines.</div>'
    rows: list[str] = []
    planned_by_task: dict[str, int] = {}
    for block in brief.plan_blocks:
        planned_by_task[block.task_id] = planned_by_task.get(block.task_id, 0) + block.minutes

    for task in brief.upcoming_tasks[:8]:
        course = task.course_code or "General"
        pressure, due_label = _task_pressure(task, now)
        planned = planned_by_task.get(task.id, 0)
        coverage = 100 if task.remaining_minutes <= 0 else min(100, round(planned / task.remaining_minutes * 100))
        rows.append(
            f"""
            <div class="task-row">
              <div class="task-main">
                <div class="list-kicker">{_esc(course)} · {_esc(task.task_type.replace('_', ' '))}</div>
                <div class="task-title">{_esc(task.title)}</div>
                <div class="task-meta">{_minutes_label(task.remaining_minutes)} remaining · {_minutes_label(planned)} planned today</div>
                <div class="coverage"><span style="width:{coverage}%"></span></div>
              </div>
              <span class="badge {pressure}">{_esc(due_label)}</span>
            </div>
            """
        )
    return '<div class="task-list">' + "".join(rows) + "</div>"


def _activity_html(brief: MorningBrief) -> str:
    if not brief.activities:
        return '<div class="empty">No new academic activity in the current lookback window.</div>'
    rows: list[str] = []
    for activity in brief.activities[:6]:
        course = activity.course_code or "Academic"
        when = activity.occurred_at.strftime("%H:%M") if activity.occurred_at else ""
        rows.append(
            f"""
            <div class="activity-row">
              <div class="activity-dot"></div>
              <div>
                <div class="list-title">{_esc(activity.title)}</div>
                <div class="list-meta">{_esc(course)} · {_esc(activity.kind)} · {_esc(when)}</div>
              </div>
            </div>
            """
        )
    return '<div class="activity-list">' + "".join(rows) + "</div>"


def _alerts_html(brief: MorningBrief) -> str:
    rows: list[str] = []
    for alert in brief.alerts:
        ok = alert.startswith("No immediate")
        data = alert.startswith("DATA ")
        class_name = "alert ok" if ok else ("alert data" if data else "alert")
        rows.append(f'<div class="{class_name}">{_esc(alert)}</div>')
    return '<div class="alerts">' + "".join(rows) + "</div>"


def _week_plan_blocks(conn, monday: date, timezone_name: str) -> dict[date, list[dict[str, object]]]:  # noqa: ANN001
    tz = ZoneInfo(timezone_name)
    start_at = datetime.combine(monday, time.min, tzinfo=tz)
    end_at = start_at + timedelta(days=7)
    rows = conn.execute(
        """
        SELECT pb.start_at, pb.end_at, pb.pinned, t.title, c.code AS course_code
        FROM plan_blocks AS pb
        JOIN tasks AS t ON t.id = pb.task_id
        LEFT JOIN courses AS c ON c.id = t.course_id
        WHERE pb.start_at < ? AND pb.end_at > ? AND pb.state != 'skipped'
        ORDER BY pb.start_at
        """,
        (end_at.isoformat(), start_at.isoformat()),
    ).fetchall()
    result = {monday + timedelta(days=i): [] for i in range(7)}
    for row in rows:
        start = _parse_local(row["start_at"], tz)
        end = _parse_local(row["end_at"], tz)
        if start.date() not in result:
            continue
        result[start.date()].append(
            {
                "start": start,
                "end": end,
                "title": row["title"],
                "course_code": row["course_code"],
                "pinned": bool(row["pinned"]),
            }
        )
    return result


def _calendar_position(start: datetime, end: datetime) -> tuple[float, float]:
    day_start = 8 * 60
    day_end = 22 * 60
    start_minute = max(day_start, start.hour * 60 + start.minute)
    end_minute = min(day_end, end.hour * 60 + end.minute)
    span = day_end - day_start
    top = (start_minute - day_start) / span * 100
    height = max(2.8, (max(start_minute + 15, end_minute) - start_minute) / span * 100)
    return top, height


def _week_html(conn, target_date: date, timezone_name: str) -> str:  # noqa: ANN001
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    sessions = effective_sessions_for_range(conn, monday, sunday, timezone_name=timezone_name)
    plans = _week_plan_blocks(conn, monday, timezone_name)

    hour_labels = "".join(f'<div class="hour-label">{hour:02d}:00</div>' for hour in range(8, 23))
    columns: list[str] = []
    for offset in range(7):
        current = monday + timedelta(days=offset)
        active = " active" if current == target_date else ""
        blocks: list[str] = []
        for session in sessions[current]:
            top, height = _calendar_position(session.start_at, session.end_at)
            blocks.append(
                f"""
                <a class="week-event fact" href="{_date_link(current)}" style="top:{top:.2f}%;height:{height:.2f}%">
                  <strong>{_esc(session.course_code)}</strong>
                  <span>{session.start_at:%H:%M} · {_esc(session.session_type.value)}</span>
                </a>
                """
            )
        for block in plans[current]:
            top, height = _calendar_position(block["start"], block["end"])
            course = f"{block['course_code']} · " if block["course_code"] else ""
            blocks.append(
                f"""
                <a class="week-event plan" href="{_date_link(current)}" style="top:{top:.2f}%;height:{height:.2f}%">
                  <strong>{_esc(course + str(block['title']))}</strong>
                  <span>{block['start']:%H:%M} · movable</span>
                </a>
                """
            )
        columns.append(
            f"""
            <div class="week-day{active}">
              <a class="week-day-head" href="{_date_link(current)}">
                <span>{current:%a}</span><strong>{current.day}</strong>
              </a>
              <div class="week-day-body">{''.join(blocks)}</div>
            </div>
            """
        )

    return f"""
    <div class="calendar-scroll">
      <div class="week-calendar">
        <div class="week-axis"><div class="axis-head"></div>{hour_labels}</div>
        {''.join(columns)}
      </div>
    </div>
    """


def _data_chip(brief: MorningBrief) -> tuple[str, str]:
    for alert in brief.alerts:
        if alert.startswith("DATA FAILED"):
            return "risk", "Data failed"
        if alert.startswith("DATA PARTIAL"):
            return "review", "Data partial"
        if alert.startswith("DATA STALE"):
            return "review", "Data stale"
        if alert.startswith("DATA UNKNOWN"):
            return "review", "Data unknown"
        if alert.startswith("DATA EMPTY"):
            return "review", "Data empty"
    return "fact", "Data fresh"


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

    brief = build_morning_brief(conn, target_date, now=local_now, timezone_name=timezone_name)
    planned_minutes = sum(block.minutes for block in brief.plan_blocks)
    urgent_count = sum(
        task.due_at is not None and 0 <= (task.due_at - local_now).total_seconds() <= 48 * 3600
        for task in brief.upcoming_tasks
    )
    yesterday = target_date - timedelta(days=1)
    tomorrow = target_date + timedelta(days=1)
    today_link = _date_link(local_now.date())
    data_class, data_label = _data_chip(brief)

    if target_date == local_now.date():
        headline = "Today is an execution problem, not a to-do list."
    else:
        headline = f"Planning view for {target_date:%A}."
    summary = (
        f"{len(brief.sessions)} confirmed classes · {_minutes_label(planned_minutes)} movable study · "
        f"{len(brief.pending_changes)} change(s) waiting · {urgent_count} urgent deadline(s)"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>AcademicOS · Command Center</title>
  <link rel="stylesheet" href="/assets/app.css">
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand"><div class="brand-mark">AO</div><div><span>AcademicOS</span><small>StudyOps</small></div></div>
    <nav class="nav">
      <a class="active" href="{_date_link(target_date)}"><span class="nav-dot"></span>Today</a>
      <a href="#week"><span class="nav-dot"></span>Calendar</a>
      <a href="#execution"><span class="nav-dot"></span>Execution</a>
      <a href="#changes"><span class="nav-dot"></span>Inbox</a>
      <a href="#activity"><span class="nav-dot"></span>Sources</a>
    </nav>
    <div class="legend">
      <div><span class="legend-dot fact"></span>Truth / fixed</div>
      <div><span class="legend-dot plan"></span>Plan / movable</div>
      <div><span class="legend-dot review"></span>Needs review</div>
    </div>
    <div class="sidebar-foot">Local-first workspace<br>External AI only when explicitly requested.</div>
  </aside>

  <main class="main">
    <header class="topbar">
      <div>
        <div class="eyebrow">Academic command center</div>
        <h1>{target_date:%A} <span>{target_date:%b %d}</span></h1>
        <div class="subtitle">{timezone_name} · plan against reality, then keep moving</div>
      </div>
      <div class="top-actions">
        <span class="badge {data_class}">{_esc(data_label)}</span>
        <div class="date-nav">
          <a aria-label="Previous day" href="{_date_link(yesterday)}">←</a>
          <a href="{today_link}">Today</a>
          <a aria-label="Next day" href="{_date_link(tomorrow)}">→</a>
        </div>
      </div>
    </header>

    <section class="brief-hero">
      <div class="brief-copy">
        <div class="micro-label">Morning / live brief</div>
        <h2>{_esc(headline)}</h2>
        <p>{_esc(summary)}</p>
        <div class="brief-signals">
          <span><strong>{len(brief.sessions)}</strong> classes</span>
          <span><strong>{_minutes_label(planned_minutes)}</strong> planned</span>
          <span><strong>{len(brief.pending_changes)}</strong> review</span>
          <span><strong>{urgent_count}</strong> urgent</span>
        </div>
      </div>
      {_now_next_html(brief, local_now)}
    </section>

    <section id="week" class="card week-card">
      <div class="card-head">
        <div><div class="card-title">Week calendar</div><div class="card-subtitle">Fixed classes and movable study live in the same time surface.</div></div>
        <div class="card-actions"><span class="badge fact">Truth</span><span class="badge plan">Plan</span></div>
      </div>
      {_week_html(conn, target_date, timezone_name)}
    </section>

    <div class="ops-grid">
      <div class="stack">
        <section id="execution" class="card">
          <div class="card-head"><div><div class="card-title">Today execution</div><div class="card-subtitle">Today timeline · what is fixed, what can move, and what comes next.</div></div></div>
          {_timeline_html(brief)}
        </section>
        <section id="tasks" class="card">
          <div class="card-head"><div><div class="card-title">Work queue</div><div class="card-subtitle">Deadline pressure plus how much of the work is actually covered by today’s plan.</div></div><span class="badge plan">Adaptive</span></div>
          {_tasks_html(brief, local_now)}
        </section>
      </div>

      <div class="stack side-stack">
        <section class="card attention-card">
          <div class="card-head"><div><div class="card-title">Attention</div><div class="card-subtitle">Only things that can change what you should do.</div></div></div>
          {_alerts_html(brief)}
        </section>
        <section id="changes" class="card">
          <div class="card-head"><div><div class="card-title">Changes inbox</div><div class="card-subtitle">Professor announcements and mail stay candidates until reviewed.</div></div><span class="badge review">Review</span></div>
          {_changes_html(brief)}
        </section>
        <section id="activity" class="card">
          <div class="card-head"><div><div class="card-title">Source pulse</div><div class="card-subtitle">New since last check, without pretending every update is a task.</div></div><span class="badge fact">Feed</span></div>
          {_activity_html(brief)}
        </section>
      </div>
    </div>
    <div class="footer-note">AcademicOS · local-first · rendered from local SQLite at {_esc(local_now.strftime('%H:%M'))}</div>
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
                page = render_dashboard(conn, target_date, timezone_name=timezone_name)
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
        raise ValueError("refusing non-loopback dashboard bind without allow_remote=True")
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
