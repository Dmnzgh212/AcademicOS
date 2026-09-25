# Web UI Principles

The AcademicOS dashboard should feel like a polished personal operating system, not an admin panel.

## Design goals

- local-first and fast;
- calm visual hierarchy;
- calendar is the primary surface;
- changes and risks are visible without notification spam;
- Truth Calendar and Plan Calendar are visually distinct but composable;
- evidence/source details are available on demand rather than always occupying space;
- desktop-first, responsive enough for tablet/mobile viewing;
- no CDN-dependent fonts, icons, analytics, or remote UI assets by default.

## Initial visual direction

- dense enough for a university timetable, but not spreadsheet-like;
- generous whitespace around the daily brief and risk summaries;
- soft cards only where grouping adds meaning;
- restrained status colors; do not turn every course into a rainbow;
- typography and spacing should carry most hierarchy;
- class blocks, study blocks, deadlines, and uncertainty states must be distinguishable without relying on color alone;
- subtle motion only for state changes; no decorative animation.

## Core views planned

1. **Today** — morning brief, next class, changes, deadlines, planned study blocks.
2. **Week** — fixed classes + movable study blocks + deadline pressure.
3. **Inbox / Changes** — announcements and email-derived candidate events with evidence and confidence.
4. **Tasks** — remaining workload, actual vs estimated time, risk.
5. **Course** — later, materials, lecture entities, notes, retrieval, and tutor.

## Interaction rule

The UI must never hide whether an item is:

- a confirmed fact;
- an inferred candidate;
- a movable plan;
- an informational activity item.

That distinction is more important than visual decoration.
