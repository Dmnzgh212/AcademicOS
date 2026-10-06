# LifeHub / AcademicOS

LifeHub is an open personal computing platform incubated in this repository.
Current engineering focuses on plugin packages, capability mediation, bounded
Wasm execution, internal contracts and replaceable shells. AcademicOS is the
existing academic application and a potential integration of that platform.

LifeHub Platform v0.1 bounded developer prototype is **accepted**.
[PR #32](https://github.com/Dmnzgh212/AcademicOS/pull/32) merged into main at
`690c0b9f0624617adcd3ed7e95341f8b9bb85f44`. Post-merge CI run 328 passed Python 3.11/3.12,
Ruff, 228 tests, wheel build/install and all installed/platform/examples smoke checks.
Read [the integration record](docs/lifehub/INTEGRATION_CANDIDATE.md),
[platform status](docs/lifehub/PLATFORM_STATUS.md) and
[acceptance record](docs/lifehub/PROTOTYPE_ACCEPTANCE.md).

Core is frozen for the real-plugin validation phase. Domain behavior belongs in
plugins; Core changes need reproducible safety, lifecycle or cross-domain evidence.
LifeHub does not define your digital life. It provides the mechanisms by which
you assemble it.

Runnable examples:

- [Generic Wasm reader](examples/lifehub/reader/README.md): package review,
  installation, discovery, explicit read grants and revocation.
- [JSON service and Wasm caller](examples/lifehub/json_echo/README.md): exact
  package-bound service authorization and bounded request/response computation.
- [Independent catalog shell](examples/lifehub/catalog_shell/README.md): consume
  catalog JSON with Python's standard library, without importing the kernel.

PersonIR, a new source language and a compiler remain frozen research hypotheses.
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
