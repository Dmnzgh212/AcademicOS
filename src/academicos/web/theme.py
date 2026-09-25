WEB_CSS = r"""
:root {
  color-scheme: light;
  --bg: #f4f6fb;
  --surface: rgba(255,255,255,.86);
  --surface-solid: #ffffff;
  --ink: #172033;
  --muted: #6f7890;
  --faint: #9aa3b7;
  --line: rgba(48,58,79,.10);
  --accent: #4f5fe7;
  --accent-soft: #eef0ff;
  --mint: #0f8f73;
  --mint-soft: #e8f8f3;
  --amber: #ad6d14;
  --amber-soft: #fff4df;
  --rose: #b4455e;
  --rose-soft: #fff0f3;
  --shadow: 0 18px 55px rgba(45,54,88,.08);
  --radius-xl: 28px;
  --radius-lg: 20px;
  --radius-md: 14px;
}

* { box-sizing: border-box; }
html { background: var(--bg); }
body {
  margin: 0;
  min-height: 100vh;
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at 8% 5%, rgba(116,126,244,.12), transparent 28rem),
    radial-gradient(circle at 95% 8%, rgba(27,181,143,.09), transparent 25rem),
    var(--bg);
}
a { color: inherit; text-decoration: none; }

.shell { min-height: 100vh; display: grid; grid-template-columns: 220px 1fr; }
.sidebar {
  position: sticky; top: 0; height: 100vh; padding: 28px 18px;
  border-right: 1px solid var(--line); background: rgba(248,249,253,.72);
  backdrop-filter: blur(18px);
}
.brand { display: flex; align-items: center; gap: 11px; padding: 4px 10px 28px; font-weight: 760; letter-spacing: -.02em; }
.brand-mark {
  width: 34px; height: 34px; border-radius: 11px; display: grid; place-items: center;
  color: white; font-size: 14px; background: linear-gradient(145deg, #6573f1, #4150ca);
  box-shadow: 0 10px 24px rgba(79,95,231,.25);
}
.nav { display: grid; gap: 6px; }
.nav a { padding: 11px 12px; border-radius: 12px; color: var(--muted); font-size: 14px; font-weight: 580; }
.nav a:hover { background: rgba(255,255,255,.7); color: var(--ink); }
.nav a.active { color: var(--accent); background: var(--accent-soft); }
.nav-dot { width: 7px; height: 7px; display: inline-block; border-radius: 50%; margin-right: 10px; background: currentColor; opacity: .75; }
.sidebar-foot { position: absolute; left: 28px; right: 28px; bottom: 28px; color: var(--faint); font-size: 11px; line-height: 1.55; }

.main { padding: 34px 38px 56px; max-width: 1480px; width: 100%; margin: 0 auto; }
.topbar { display:flex; justify-content:space-between; align-items:center; gap:18px; margin-bottom: 22px; }
.eyebrow { color: var(--accent); font-size: 12px; font-weight: 760; letter-spacing: .08em; text-transform: uppercase; }
h1 { margin: 6px 0 3px; font-size: clamp(31px, 4vw, 46px); letter-spacing: -.045em; line-height: 1; }
.subtitle { color: var(--muted); font-size: 14px; }
.date-nav { display:flex; align-items:center; gap:8px; }
.date-nav a, .date-chip { border:1px solid var(--line); background: rgba(255,255,255,.75); border-radius: 12px; padding: 9px 12px; font-size: 13px; box-shadow: 0 3px 12px rgba(45,54,88,.03); }
.date-nav a:hover { border-color: rgba(79,95,231,.25); }

.metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:16px; }
.metric { padding:17px 18px; border:1px solid var(--line); border-radius:var(--radius-lg); background:var(--surface); box-shadow:0 8px 30px rgba(45,54,88,.04); }
.metric-label { font-size:11px; text-transform:uppercase; letter-spacing:.075em; color:var(--faint); font-weight:700; }
.metric-value { margin-top:6px; font-size:23px; font-weight:760; letter-spacing:-.03em; }
.metric-note { margin-top:4px; color:var(--muted); font-size:11px; }

.grid { display:grid; grid-template-columns:minmax(0,1.65fr) minmax(300px,.8fr); gap:16px; align-items:start; }
.stack { display:grid; gap:16px; }
.card { border:1px solid var(--line); background:var(--surface); border-radius:var(--radius-xl); box-shadow:var(--shadow); overflow:hidden; }
.card-head { display:flex; justify-content:space-between; align-items:flex-start; padding:21px 22px 13px; }
.card-title { font-size:16px; font-weight:720; letter-spacing:-.02em; }
.card-subtitle { margin-top:4px; color:var(--muted); font-size:12px; }
.badge { display:inline-flex; align-items:center; padding:5px 8px; border-radius:999px; font-size:10px; font-weight:750; letter-spacing:.04em; text-transform:uppercase; }
.badge.fact { background:var(--mint-soft); color:var(--mint); }
.badge.plan { background:var(--accent-soft); color:var(--accent); }
.badge.review { background:var(--amber-soft); color:var(--amber); }
.badge.risk { background:var(--rose-soft); color:var(--rose); }

.timeline { padding: 4px 22px 22px; }
.timeline-item { position:relative; display:grid; grid-template-columns:76px 16px 1fr; gap:10px; min-height:74px; }
.timeline-time { padding-top:13px; color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }
.timeline-rail { position:relative; }
.timeline-rail::before { content:""; position:absolute; left:7px; top:0; bottom:0; width:1px; background:var(--line); }
.timeline-dot { position:absolute; z-index:1; left:3px; top:17px; width:9px; height:9px; border:2px solid white; border-radius:50%; background:var(--accent); box-shadow:0 0 0 1px rgba(79,95,231,.18); }
.timeline-dot.fact { background:var(--mint); }
.timeline-content { margin:5px 0 9px; padding:12px 14px; border-radius:15px; background:rgba(248,249,253,.85); border:1px solid rgba(48,58,79,.07); }
.timeline-main { display:flex; justify-content:space-between; gap:12px; }
.timeline-name { font-size:14px; font-weight:680; }
.timeline-meta { margin-top:5px; font-size:11px; color:var(--muted); }
.empty { color:var(--muted); font-size:13px; padding:12px 22px 24px; }

.list { padding:4px 16px 18px; display:grid; gap:8px; }
.list-item { padding:12px 13px; border-radius:14px; border:1px solid rgba(48,58,79,.07); background:rgba(250,251,254,.83); }
.list-top { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }
.list-title { font-size:13px; font-weight:660; line-height:1.35; }
.list-meta { margin-top:5px; color:var(--muted); font-size:11px; line-height:1.4; }
.confidence { font-size:10px; color:var(--amber); white-space:nowrap; font-weight:700; }

.alerts { padding:4px 18px 18px; display:grid; gap:8px; }
.alert { display:flex; gap:10px; align-items:flex-start; padding:11px 12px; border-radius:14px; background:var(--amber-soft); color:#74470b; font-size:12px; line-height:1.45; }
.alert::before { content:"!"; flex:0 0 20px; width:20px; height:20px; border-radius:50%; display:grid; place-items:center; background:rgba(173,109,20,.13); font-weight:800; }
.alert.ok { background:var(--mint-soft); color:#0d6f5b; }
.alert.ok::before { content:"✓"; background:rgba(15,143,115,.13); }

.week-strip { display:grid; grid-template-columns:repeat(7,1fr); gap:8px; padding:4px 18px 20px; }
.day-pill { padding:10px 7px; border-radius:14px; text-align:center; border:1px solid transparent; color:var(--muted); }
.day-pill:hover { background:rgba(255,255,255,.7); }
.day-pill.active { background:var(--accent-soft); border-color:rgba(79,95,231,.10); color:var(--accent); }
.day-name { font-size:10px; text-transform:uppercase; font-weight:700; letter-spacing:.05em; }
.day-num { margin-top:5px; font-size:17px; font-weight:750; }
.day-count { margin-top:4px; font-size:9px; opacity:.75; }

.footer-note { margin-top:18px; text-align:center; color:var(--faint); font-size:10px; }

@media (max-width: 980px) {
  .shell { grid-template-columns:1fr; }
  .sidebar { display:none; }
  .main { padding:24px 16px 42px; }
  .metrics { grid-template-columns:repeat(2,1fr); }
  .grid { grid-template-columns:1fr; }
}
@media (max-width: 560px) {
  .topbar { align-items:flex-start; flex-direction:column; }
  .metrics { grid-template-columns:1fr 1fr; }
  .timeline-item { grid-template-columns:60px 12px 1fr; gap:6px; }
  .week-strip { gap:2px; padding-left:8px; padding-right:8px; }
  .day-pill { padding:8px 2px; }
}
"""
