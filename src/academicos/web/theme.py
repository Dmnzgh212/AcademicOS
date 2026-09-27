WEB_CSS = r"""
:root {
  color-scheme: light;
  --bg: #f5f5f2;
  --surface: #ffffff;
  --surface-2: #fafaf8;
  --ink: #171a1f;
  --muted: #6f737c;
  --faint: #a0a4ad;
  --line: #e7e7e2;
  --line-strong: #d9d9d2;
  --accent: #5a5ce2;
  --accent-soft: #eeefff;
  --mint: #18785f;
  --mint-soft: #eaf6f1;
  --amber: #9a6518;
  --amber-soft: #fff5e2;
  --rose: #a63d55;
  --rose-soft: #fff0f3;
  --sidebar: #17191f;
  --sidebar-muted: #989ca7;
  --shadow: 0 16px 40px rgba(31, 34, 43, .06);
  --radius-xl: 22px;
  --radius-lg: 16px;
  --radius-md: 12px;
}

* { box-sizing: border-box; }
html { background: var(--bg); scroll-behavior: smooth; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--ink);
  background: var(--bg);
}
a { color: inherit; text-decoration: none; }

.shell { min-height: 100vh; display: grid; grid-template-columns: 226px 1fr; }
.sidebar {
  position: sticky; top: 0; height: 100vh; padding: 24px 16px;
  background: var(--sidebar); color: #fff; border-right: 1px solid rgba(255,255,255,.04);
}
.brand { display: flex; align-items: center; gap: 11px; padding: 4px 8px 26px; font-weight: 760; letter-spacing: -.02em; }
.brand > div:last-child { display:grid; gap:2px; }
.brand small { font-size: 10px; color: var(--sidebar-muted); font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }
.brand-mark {
  width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center;
  color: white; font-size: 13px; background: #5a5ce2;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.08);
}
.nav { display: grid; gap: 5px; }
.nav a { padding: 11px 12px; border-radius: 10px; color: var(--sidebar-muted); font-size: 13px; font-weight: 620; }
.nav a:hover { background: rgba(255,255,255,.05); color: #fff; }
.nav a.active { color: #fff; background: rgba(255,255,255,.08); }
.nav-dot { width: 6px; height: 6px; display: inline-block; border-radius: 50%; margin-right: 10px; background: currentColor; opacity: .8; }
.legend { margin: 28px 9px 0; padding-top: 18px; border-top: 1px solid rgba(255,255,255,.08); display:grid; gap:9px; color:var(--sidebar-muted); font-size:10px; }
.legend > div { display:flex; align-items:center; gap:8px; }
.legend-dot { width:8px; height:8px; border-radius:3px; background:var(--accent); }
.legend-dot.fact { background:#58a68e; }
.legend-dot.review { background:#d39b45; }
.sidebar-foot { position: absolute; left: 24px; right: 24px; bottom: 24px; color: #777c87; font-size: 10px; line-height: 1.55; }

.main { padding: 30px 34px 52px; max-width: 1580px; width: 100%; margin: 0 auto; }
.topbar { display:flex; justify-content:space-between; align-items:center; gap:18px; margin-bottom: 18px; }
.eyebrow { color: var(--muted); font-size: 10px; font-weight: 760; letter-spacing: .1em; text-transform: uppercase; }
h1 { margin: 6px 0 3px; font-size: clamp(30px, 3.6vw, 44px); letter-spacing: -.045em; line-height: 1; }
h1 span { color:var(--faint); font-weight:620; }
.subtitle { color: var(--muted); font-size: 12px; }
.top-actions { display:flex; align-items:center; gap:10px; }
.date-nav { display:flex; align-items:center; gap:6px; }
.date-nav a { border:1px solid var(--line); background:var(--surface); border-radius:10px; padding:8px 11px; font-size:12px; box-shadow:0 2px 8px rgba(31,34,43,.02); }
.date-nav a:hover { border-color: var(--line-strong); background:var(--surface-2); }

.brief-hero {
  display:grid; grid-template-columns:minmax(0,1.15fr) minmax(360px,.85fr); gap:18px;
  padding:22px; margin-bottom:16px; border:1px solid var(--line); border-radius:var(--radius-xl);
  background:var(--surface); box-shadow:var(--shadow);
}
.brief-copy { padding:6px 4px; }
.micro-label { color:var(--faint); text-transform:uppercase; letter-spacing:.08em; font-size:9px; font-weight:760; }
.brief-copy h2 { margin:8px 0 7px; font-size:22px; letter-spacing:-.035em; }
.brief-copy p { margin:0; color:var(--muted); font-size:12px; line-height:1.55; }
.brief-signals { display:flex; gap:8px; flex-wrap:wrap; margin-top:18px; }
.brief-signals span { border:1px solid var(--line); background:var(--surface-2); padding:7px 9px; border-radius:10px; color:var(--muted); font-size:10px; }
.brief-signals strong { color:var(--ink); font-size:11px; }
.now-next { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.now-card { border:1px solid var(--line); background:#fbfbf9; border-radius:15px; padding:15px; min-height:132px; }
.now-card.next { background:#f5f5ff; border-color:#e1e2fb; }
.now-state { display:inline-flex; margin-top:9px; padding:4px 7px; border-radius:999px; background:var(--mint-soft); color:var(--mint); font-size:9px; font-weight:760; text-transform:uppercase; letter-spacing:.05em; }
.now-title { margin-top:10px; font-size:13px; font-weight:720; line-height:1.35; }
.now-meta { margin-top:5px; color:var(--muted); font-size:10px; line-height:1.45; }

.card { border:1px solid var(--line); background:var(--surface); border-radius:var(--radius-xl); box-shadow:var(--shadow); overflow:hidden; }
.card-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; padding:19px 20px 12px; }
.card-title { font-size:15px; font-weight:740; letter-spacing:-.02em; }
.card-subtitle { margin-top:4px; color:var(--muted); font-size:10.5px; line-height:1.45; }
.card-actions { display:flex; gap:6px; }
.badge { display:inline-flex; align-items:center; padding:5px 8px; border-radius:999px; font-size:9px; font-weight:760; letter-spacing:.04em; text-transform:uppercase; white-space:nowrap; }
.badge.fact { background:var(--mint-soft); color:var(--mint); }
.badge.plan { background:var(--accent-soft); color:var(--accent); }
.badge.review { background:var(--amber-soft); color:var(--amber); }
.badge.risk { background:var(--rose-soft); color:var(--rose); }
.badge.normal { background:#f0f1f3; color:#6b7078; }

.week-card { margin-bottom:16px; }
.calendar-scroll { overflow-x:auto; padding:0 14px 18px; }
.week-calendar { min-width:980px; display:grid; grid-template-columns:54px repeat(7,minmax(120px,1fr)); border:1px solid var(--line); border-radius:14px; overflow:hidden; background:#fff; }
.week-axis { display:grid; grid-template-rows:46px repeat(15, 38px); background:#fafaf8; border-right:1px solid var(--line); }
.axis-head { border-bottom:1px solid var(--line); }
.hour-label { padding:5px 7px 0 0; text-align:right; color:var(--faint); font-size:8px; border-bottom:1px solid #f0f0ec; }
.week-day { min-width:0; border-right:1px solid var(--line); }
.week-day:last-child { border-right:0; }
.week-day-head { height:46px; display:flex; justify-content:center; align-items:center; gap:6px; border-bottom:1px solid var(--line); color:var(--muted); font-size:10px; }
.week-day-head strong { font-size:13px; color:var(--ink); }
.week-day.active .week-day-head { background:var(--accent-soft); color:var(--accent); }
.week-day.active .week-day-head strong { color:var(--accent); }
.week-day-body { position:relative; height:570px; background:repeating-linear-gradient(to bottom,#fff 0,#fff 37px,#f0f0ec 38px); }
.week-day.active .week-day-body { background:repeating-linear-gradient(to bottom,#fdfdff 0,#fdfdff 37px,#ececfa 38px); }
.week-event { position:absolute; left:5px; right:5px; z-index:2; min-height:22px; border-radius:8px; padding:5px 6px; overflow:hidden; border:1px solid transparent; font-size:9px; line-height:1.25; }
.week-event strong { display:block; font-size:9px; font-weight:760; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.week-event span { display:block; margin-top:2px; opacity:.76; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.week-event.fact { background:#e9f5f1; color:#176b57; border-color:#d5ece4; }
.week-event.plan { background:#eff0ff; color:#5052c8; border-color:#dfe0fb; }
.week-event:hover { filter:brightness(.985); }

.ops-grid { display:grid; grid-template-columns:minmax(0,1.6fr) minmax(330px,.8fr); gap:16px; align-items:start; }
.stack { display:grid; gap:16px; }
.side-stack { position:sticky; top:16px; }

.timeline { padding:2px 20px 20px; }
.timeline-item { position:relative; display:grid; grid-template-columns:62px 14px 1fr; gap:9px; min-height:66px; }
.timeline-time { padding-top:12px; color:var(--muted); font-size:10px; font-variant-numeric:tabular-nums; }
.timeline-rail { position:relative; }
.timeline-rail::before { content:""; position:absolute; left:6px; top:0; bottom:0; width:1px; background:var(--line); }
.timeline-dot { position:absolute; z-index:1; left:2px; top:15px; width:9px; height:9px; border:2px solid white; border-radius:50%; background:var(--accent); box-shadow:0 0 0 1px rgba(90,92,226,.16); }
.timeline-dot.fact { background:var(--mint); box-shadow:0 0 0 1px rgba(24,120,95,.16); }
.timeline-content { margin:4px 0 8px; padding:11px 12px; border-radius:13px; background:#fafaf8; border:1px solid #eeeeea; }
.timeline-main { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
.timeline-name { font-size:12px; font-weight:690; line-height:1.35; }
.timeline-meta { margin-top:4px; font-size:9.5px; color:var(--muted); }
.empty { color:var(--muted); font-size:11px; padding:10px 20px 20px; }

.task-list { padding:2px 14px 16px; display:grid; gap:7px; }
.task-row { display:flex; justify-content:space-between; gap:14px; align-items:flex-start; padding:13px; border:1px solid var(--line); border-radius:13px; background:#fbfbf9; }
.task-main { min-width:0; flex:1; }
.task-title { margin-top:3px; font-size:12px; font-weight:700; }
.task-meta { margin-top:5px; color:var(--muted); font-size:9.5px; }
.coverage { height:4px; margin-top:9px; border-radius:999px; overflow:hidden; background:#ecece8; }
.coverage span { display:block; height:100%; border-radius:999px; background:var(--accent); }

.list { padding:2px 14px 16px; display:grid; gap:7px; }
.list-item { padding:12px; border-radius:13px; border:1px solid var(--line); background:#fbfbf9; }
.list-top { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }
.list-kicker { color:var(--faint); font-size:8.5px; font-weight:740; letter-spacing:.05em; text-transform:uppercase; }
.list-title { margin-top:2px; font-size:11.5px; font-weight:690; line-height:1.35; }
.list-meta { margin-top:4px; color:var(--muted); font-size:9.5px; line-height:1.4; }
.confidence { font-size:9px; color:var(--amber); white-space:nowrap; font-weight:760; }
.evidence { margin-top:8px; padding:8px 9px; border-radius:9px; background:#fff8ea; color:#765122; font-size:9.5px; line-height:1.45; }

.activity-list { padding:2px 16px 16px; display:grid; gap:2px; }
.activity-row { display:grid; grid-template-columns:10px 1fr; gap:9px; padding:9px 2px; border-bottom:1px solid #f0f0ec; }
.activity-row:last-child { border-bottom:0; }
.activity-dot { width:7px; height:7px; margin-top:5px; border-radius:50%; background:var(--mint); }

.alerts { padding:2px 14px 16px; display:grid; gap:7px; }
.alert { display:flex; gap:9px; align-items:flex-start; padding:10px 11px; border-radius:12px; background:var(--amber-soft); color:#714a11; font-size:10px; line-height:1.45; }
.alert::before { content:"!"; flex:0 0 18px; width:18px; height:18px; border-radius:50%; display:grid; place-items:center; background:rgba(154,101,24,.12); font-weight:800; }
.alert.ok { background:var(--mint-soft); color:#12634f; }
.alert.ok::before { content:"✓"; background:rgba(24,120,95,.12); }
.alert.data { background:#f2f2ff; color:#5153b5; }
.alert.data::before { content:"↻"; background:rgba(90,92,226,.10); }

.footer-note { margin-top:16px; text-align:center; color:var(--faint); font-size:9px; }

@media (max-width: 1120px) {
  .brief-hero { grid-template-columns:1fr; }
  .ops-grid { grid-template-columns:1fr; }
  .side-stack { position:static; }
}
@media (max-width: 920px) {
  .shell { grid-template-columns:1fr; }
  .sidebar { display:none; }
  .main { padding:22px 14px 40px; }
}
@media (max-width: 620px) {
  .topbar { align-items:flex-start; flex-direction:column; }
  .top-actions { width:100%; justify-content:space-between; }
  .now-next { grid-template-columns:1fr; }
  .brief-signals { display:grid; grid-template-columns:1fr 1fr; }
  .timeline-item { grid-template-columns:52px 12px 1fr; gap:6px; }
}
"""
