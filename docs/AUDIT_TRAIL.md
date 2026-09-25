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

## Source collection — Brightspace + Microsoft 365

Status: implemented and CI verified; real-account validation is still required on the user's machine.

Brightspace acquisition now includes:
- persistent-browser SSO/MFA bootstrap and local bearer-token capture/refresh;
- account identity, active enrollments, and activity feed;
- announcements;
- assignments and the student's submissions;
- quizzes and attempts;
- content TOC/root/module structures;
- grades, grade objects, and final grade;
- calendar, due, overdue, and update feeds;
- discussions, checklists, and overview;
- downloadable course-content files and assignment attachments.

Microsoft 365 acquisition now includes:
- delegated read-only Graph authentication with local token cache;
- Inbox metadata/body collection;
- bounded pagination;
- attachment metadata/content collection and local attachment download support.

Incremental sync:
- schema v3 adds `sync_state`;
- Brightspace activity feed, per-course announcement collection, and Microsoft 365 Inbox use persisted cursors/last-success timestamps;
- successful runs advance cursors; failed course/source runs do not;
- unchanged source objects are hash-deduplicated.

Course discovery:
- local timetable courses are conservatively matched against active Brightspace Course Offering enrollments;
- `org_id` is auto-filled when there is exactly one match;
- a missing `[[brightspace.courses]]` list means auto-discover all unambiguous local courses;
- ambiguous mappings are reported instead of guessed;
- explicit per-course config remains available as an override.

Collector audit finding:
- CI exposed a real bug where requesting `content_structure` did not collect `content_root` because the nested helper incorrectly rechecked the alias name against the include set;
- the collector now fetches and persists `content_root` directly under the `content_structure` request, and nested module discovery again has the full root + TOC input.

Final CI snapshot for this source-collection slice: **48 passed** on Python 3.12 with Ruff correctness checks passing; the corresponding Python 3.11 matrix job also completed successfully.

See `SOURCE_COLLECTION.md` for the acquisition architecture and privacy boundary.

## Current limitations / next audit targets

- Source collectors are implemented, but Brightspace and Microsoft 365 still need end-to-end validation against the user's real uOttawa accounts on Windows.
- The Windows Task Scheduler installer/registration flow is not yet implemented; the sync command itself is suitable for scheduled execution.
- Some Brightspace endpoints can vary by institution/course permissions; per-endpoint isolation is implemented, but real uOttawa response shapes should be captured and hardened.
- File mirroring currently compares local bytes to downloaded bytes; a persistent remote metadata/hash manifest could reduce unnecessary binary transfers further.
- Microsoft Graph Inbox collection uses a timestamp filter rather than Graph delta queries; delta-link support would be a stronger long-term incremental mechanism.
- Free-text `class_moved` extraction is deliberately not automated yet because time/date movement language needs safer disambiguation; the Candidate acceptance engine itself supports moved events.
- Deadline-change CandidateEvents do not yet deterministically identify/materialize the correct Task.
- Accepted CandidateEvent rollback/supersession is not implemented yet.
- Adaptive planner does not yet learn time-of-day energy preference, switching cost, or schedule-churn penalties.
- Dashboard v0.1 remains primarily read-only; Candidate accept/reject is currently exposed through CLI, not web controls.
