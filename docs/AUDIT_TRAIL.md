# Development Audit Trail

AcademicOS records major implementation slices with a short audit summary so future maintainers can distinguish verified behavior from design intent.

## Calendar v0.1 — timetable + Truth Calendar slice

Status: implemented and locally tested before repository update.

Verified locally:
- fresh SQLite initialization;
- v1 -> v2 schema migration;
- course section persistence;
- idempotent timetable import;
- stale recurring-session reconciliation;
- base daily Truth Calendar materialization;
- cancellation overrides;
- location overrides;
- moved-session rendering on destination date;
- CLI timetable import and daily rendering;
- JSON daily output.

Local test result before push: **13 passed**.

## Calendar v0.1 — candidate acceptance + week slice

Status: implemented and locally tested before repository update.

Verified locally:
- candidate persistence;
- manual acceptance;
- confidence-gated automatic acceptance;
- rejection state transition;
- rejected candidates cannot later be accepted accidentally;
- class cancellation candidate -> event override;
- class location-change candidate -> event override;
- same-kind conflicting overrides are blocked instead of last-write-wins;
- Monday-Sunday Truth Calendar materialization;
- weekly CLI rendering.

Local cumulative test result before push: **19 passed**.

## Calendar v0.1 — Brightspace announcement ingestion

Status: implemented and CI verified.

Reference implementation reviewed:
- `Aaryan-Kapoor/d2l-cli` read-only Valence client and News command;
- verified LE `/{org_id}/news/` path, `since`, D2L RichText shape, and 429 retry behavior.

Implemented and verified:
- GET-only Brightspace client with Bearer authentication;
- HTTP 429 retry honoring `Retry-After`;
- News endpoint and `since` forwarding;
- announcement RichText normalization (`Text`, local HTML fallback);
- stable SourceItem IDs and canonical content hashes;
- unchanged-source short circuit;
- edited-source re-extraction of pending candidates only;
- Evidence links from candidates back to professor source text;
- Activity Feed insertion;
- deterministic extraction for explicit cancellation, online mode, room change, deadline change, exam/quiz announcement, and newly posted material;
- conservative confidence reduction when date/session target cannot be resolved;
- optional confidence-gated auto acceptance;
- environment-variable token input rather than command-line token input;
- Changes Inbox query and status filtering.

Security/privacy observations:
- no cloud LLM is called by ingestion;
- raw academic content remains in local SQLite;
- no token is stored in the repository;
- automatic fact materialization still passes through CandidateEvent acceptance/conflict checks.

## Calendar v0.1 — CI introduction

Status: active on pushes and pull requests.

Matrix:
- Python 3.11;
- Python 3.12.

Checks:
- Ruff correctness rules (`E4`, `E7`, `E9`, `F`);
- full pytest suite.

Audit note: the first workflow run intentionally exposed that an unrestricted modern Ruff default produced substantial style/tooling noise, including Typer's valid `Option(...)` signature pattern and several pre-existing modernization preferences. CI was narrowed to correctness rules rather than rewriting working CLI APIs merely to satisfy style rules.

A cross-file `class_location_changed` enum/reference inconsistency was also inspected during this audit and the current mainline imports successfully under CI.

## Calendar v0.1 — adaptive planner

Status: implemented and CI verified.

Open-source concepts reimplemented:
- Fluxure: free/busy, chunking, greedy placement, movable-plan replacement;
- Taskwarrior: computed live urgency instead of one permanent priority;
- Super Productivity: estimate and actual time as separate signals.

Verified behavior:
- hierarchical personal velocity model (course + task type -> course -> global -> neutral);
- robust median estimate with shrinkage toward 1.0 for sparse history;
- dynamic urgency from workload pressure, deadline pressure, and importance;
- Truth Calendar events removed from available study time;
- buffers around fixed academic events;
- pinned, started, and completed plan blocks protected from replanning;
- long tasks split into bounded chunks without tiny tails;
- near-deadline work wins placement over less urgent future work in covered scenarios;
- persisted replan removes only movable future plan blocks in its planning window;
- unscheduled minutes explicitly reported rather than silently dropped.

## Calendar v0.1 — Morning Brief + local dashboard

Status: implemented and CI verified.

Morning Brief combines locally and deterministically:
- today's effective Truth Calendar;
- recent Activity Feed items;
- pending CandidateEvents;
- upcoming tasks/deadlines;
- today's Plan Calendar blocks;
- immediate deadline/workload alerts.

Dashboard verified properties:
- server-rendered local page;
- no external fonts, CDN scripts, icon services, or analytics;
- default loopback binding (`127.0.0.1`);
- non-loopback binding refused unless code explicitly opts in;
- HTML-escaping of private/source-derived task data;
- `Cache-Control: no-store` and no-referrer policy;
- separate visual semantics for Confirmed facts, movable Plan blocks, and Candidate changes;
- responsive Today page with week strip, timeline, Attention, Changes Inbox, Upcoming Work, and Recent Activity.

CLI now exposes:
- timetable import;
- Brightspace announcement import/live News sync;
- day/week Truth Calendar;
- Changes Inbox + accept/reject;
- adaptive planning;
- deterministic brief;
- local dashboard server.

CI snapshot for the integrated Brightspace + planner + brief + dashboard code: **37 passed** on Python 3.11, with Ruff correctness checks passing; the corresponding Python 3.12 matrix job also completed successfully.

## Current limitations / next audit targets

- Brightspace browser SSO / automatic token capture is not implemented yet; live sync currently expects an existing Bearer token via environment variable.
- Email ingestion is not implemented yet.
- Free-text `class_moved` extraction is deliberately not automated yet because time/date movement language needs safer disambiguation; the Candidate acceptance engine itself supports moved events.
- Deadline-change CandidateEvents do not yet deterministically identify/materialize the correct Task.
- Accepted CandidateEvent rollback/supersession is not implemented yet.
- Adaptive planner does not yet learn time-of-day energy preference, switching cost, or schedule-churn penalties.
- Planner v0.1 is urgency-sorted first-fit greedy placement, not a global constraint optimum.
- Dashboard v0.1 is primarily read-only; Candidate accept/reject is currently exposed through CLI, not web controls.
- Full orchestrated recurring `sync` and Windows Task Scheduler installation are not implemented yet.
- Email + Brightspace combined Morning Brief has not yet been validated against the user's real Fall 2026 data.
