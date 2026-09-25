# Architecture

## Product boundary

AcademicOS is one local Python project with one primary SQLite database and a local data directory.

The system has four responsibilities:

1. **Acquisition** — Brightspace, selected academic email, timetable imports, later Zoom/material sources.
2. **Truth** — normalize source data into evidence-backed academic facts and changes.
3. **Planning** — convert deadlines and workload into movable study blocks.
4. **Assistance** — later, local retrieval and AI Tutor features.

## Calendar-first architecture

### Source layer
- Brightspace connector
- Mail connector
- Manual timetable import
- Later: Zoom, local files, note photos

### Raw source store
Every fetched item should retain source type, source ID, URL when available, timestamps, canonical hash, and raw text/metadata or local file path.

### Extraction layer
New information becomes a **candidate fact** first.

Examples:
- `class_cancelled`
- `class_moved`
- `class_mode_changed`
- `deadline_created`
- `deadline_changed`
- `exam_announced`
- `quiz_announced`
- `new_material`
- `suggested_task`

Each candidate stores evidence and confidence.

### Truth Calendar
Contains recurring classes/labs/tutorials, exams/quizzes, deadlines, and dated overrides such as cancellation, room change, online mode, or moved time.

### Activity Feed
Contains changes worth knowing about but not necessarily calendar events.

### Task Store
Contains work with remaining effort and deadline.

### Plan Calendar
Contains movable study/work blocks.

## AI boundary
AI may interpret ambiguous language but must not become the source of truth.

## Storage
Initial target: SQLite + local files. Later add FTS5 and sqlite-vec.

Avoid Redis, PostgreSQL, and microservice infrastructure in v0.1.
