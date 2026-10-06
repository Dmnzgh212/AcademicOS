# LifeHub / AcademicOS

LifeHub is an open personal computing platform incubated in this repository.
Current engineering focuses on plugin packages, capability mediation, bounded
Wasm execution, internal contracts and replaceable shells. AcademicOS is the
existing academic application and a potential integration of that platform.

Start with [the current platform status](docs/lifehub/PLATFORM_STATUS.md) and
[the recovery record](docs/lifehub/PLATFORM_RECOVERY_2026-10-05.md).
The platform work is on a stack of draft PRs, currently through
[PR #31](https://github.com/Dmnzgh212/AcademicOS/pull/31); it has not been merged into main.

Runnable examples:

- [Generic Wasm reader](examples/lifehub/reader/README.md): package review,
  installation, discovery, explicit read grants and revocation.
- [JSON service and Wasm caller](examples/lifehub/json_echo/README.md): exact
  package-bound service authorization and bounded request/response computation.
- [Independent catalog shell](examples/lifehub/catalog_shell/README.md): consume
  catalog JSON with Python's standard library, without importing the kernel.

PersonIR, a new source language and a compiler remain research directions.
Their implementation and evidence are retained on the original research branches;
they are not prerequisites of this platform branch. The current evidence does not
justify expanding a language/compiler implementation.

## Existing AcademicOS application: calendar and planning

AcademicOS is being built in phases. The first usable system is a reliable academic calendar and planning core that can:

- import a fixed course timetable;
- monitor Brightspace announcements and academic changes;
- ingest relevant course email information;
- distinguish facts, tasks, and informational updates;
- maintain a **Truth Calendar** for real events and a separate **Plan Calendar** for movable study blocks;
- generate morning briefs, evening summaries, and important change alerts;
- adapt future study blocks using deadlines, remaining workload, historical task duration, and actual time spent.

Later phases add course-file ingestion, Zoom transcripts, note/OCR pipelines, retrieval, and an AI Tutor.

## Core principles

1. **Script first, AI last.**
2. **Local by default.**
3. **Explicit cloud egress.**
4. **Facts keep evidence.**
5. **Truth and plans are separate.**
6. **Adaptive planning.**
7. **One maintainable Python project.**

## High-level architecture

```text
Brightspace ─┐
             ├─> source sync -> raw local store -> event extraction
Email ───────┘                                  |
                                                v
                                    evidence + confidence
                                                |
                         ┌──────────────────────┼──────────────────────┐
                         v                      v                      v
                  Truth Calendar          Activity Feed          Task Store
                         |                                             |
                         └──────────────────────┬──────────────────────┘
                                                v
                                      Adaptive Planner
                                                |
                                                v
                                         Plan Calendar
                                                |
                              ┌─────────────────┼─────────────────┐
                              v                 v                 v
                         Morning Brief      Alerts        Evening Summary
```

## Open-source strategy

AcademicOS does not vendor whole projects by default. Mature implementations are studied and compatible code is reused selectively with attribution and license review.

See `docs/OPEN_SOURCE_REFERENCES.md` and `THIRD_PARTY_NOTICES.md`.
