# Calendar v0.1 — Base Timetable and Truth Calendar

This is the first executable Calendar slice.

## What works now

- create/migrate the SQLite database;
- import an authoritative semester timetable from JSON;
- keep imports idempotent;
- store recurring classes/labs/tutorials;
- preserve course sections such as A00/B00;
- apply cancellation/location/mode/move overrides;
- render the effective academic sessions for a date;
- show moved classes on the destination day rather than the original day.

## Timetable JSON

See `examples/timetable.example.json`.

Core structure:

```json
{
  "term": "2026F",
  "timezone": "America/Toronto",
  "courses": [
    {
      "code": "CEG2136",
      "name": "Computer Architecture I",
      "section": "A00",
      "sessions": [
        {
          "session_type": "lecture",
          "days": ["MO", "TH"],
          "start_time": "14:30",
          "end_time": "15:50",
          "start_date": "2026-09-09",
          "end_date": "2026-12-04",
          "location": "SITE",
          "delivery_mode": "in_person",
          "group": "A00"
        }
      ]
    }
  ]
}
```

Weekday aliases such as `MO`, `MON`, `MONDAY`, `TH`, and `FRI` are accepted.

## Commands

```bash
academicos init-db --db D:/AcademicOSData/academicos.db

academicos timetable-import examples/timetable.example.json \
  --db D:/AcademicOSData/academicos.db

academicos day 2026-09-28 \
  --db D:/AcademicOSData/academicos.db

academicos day 2026-09-28 \
  --db D:/AcademicOSData/academicos.db \
  --include-cancelled

academicos day 2026-09-28 \
  --db D:/AcademicOSData/academicos.db \
  --json
```

## Truth Calendar semantics

The base timetable is authoritative recurring truth.

Announcement/email changes should later become `candidate_events`. Accepted candidates create `event_overrides`; the base recurrence is not destructively rewritten.

A moved class uses the original occurrence date as its identity but is rendered on its new effective date.

## Current limitations

- no Brightspace source connector yet;
- no automatic candidate-event extraction yet;
- no email ingestion yet;
- no planner/free-time allocation yet;
- no web dashboard yet;
- multiple conflicting overrides are currently applied in insertion order; conflict-resolution policy will be added with the event acceptance pipeline.
