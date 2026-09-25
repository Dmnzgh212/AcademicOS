# AcademicOS

Local-first academic event intelligence, adaptive planning, and study assistance for university students.

## Current focus: Calendar-first v0.1

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
