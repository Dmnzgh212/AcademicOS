# Brightspace Announcement Ingestion

## Purpose

Calendar v0.1 needs to learn about class cancellations, room/mode changes, deadline changes, exams/quizzes, and newly posted material without allowing raw professor text to mutate the calendar directly.

The ingestion path is therefore:

```text
Brightspace News API
  -> normalized announcement
  -> SourceItem + content hash
  -> Evidence
  -> deterministic extraction
  -> CandidateEvent
  -> review / confidence-gated auto acceptance
  -> Truth Calendar override when supported
```

## Upstream reference

The read path was verified against `Aaryan-Kapoor/d2l-cli` (MIT), including:

- read-only GET design;
- LE Valence path construction;
- `/{org_id}/news/` announcement endpoint;
- optional `since` query parameter;
- retry on HTTP 429 using `Retry-After`;
- D2L RichText convention (`Text`, fallback `Html`);
- announcement dates from `StartDate`, `CreatedDate`, or `PublicationDate`.

AcademicOS reimplements this narrowly instead of importing the entire CLI.

## Local data behavior

Each announcement gets a stable source ID:

```text
news:{org_unit_id}:{announcement_id}
```

and a canonical SHA-256 content hash over normalized title/body/publication time.

Unchanged announcements stop before extraction. Edited announcements update the same SourceItem. Only stale **pending** candidates are removed and re-extracted; accepted facts are never silently rolled back.

## Evidence

Normalized title + body are stored as Evidence and linked to every CandidateEvent extracted from that source. This is intended to let the dashboard answer “why is this change here?” without relying on model memory.

## Deterministic extractor

The first extractor intentionally recognizes a conservative subset:

- explicit class cancellation;
- explicit online / Zoom / remote mode change;
- explicit room/location change;
- deadline extension/change;
- exam/midterm/final announcement with a resolvable date;
- quiz announcement with a resolvable date;
- newly uploaded/posted course material.

Dates support simple academic phrasing such as `today`, `tomorrow`, weekdays, `next Friday`, ISO dates, and English month/day expressions.

Class changes also try to resolve the exact recurring session using course, occurrence date, and a session-type clue such as `lecture` or `lab`. Failure to resolve lowers confidence and prevents automatic calendar mutation.

## Auto acceptance

Default behavior is review-first. `--auto-accept` is opt-in.

Even then, only high-confidence candidates can reach the acceptance engine, which independently checks its own threshold and conflict rules. Unsupported candidates such as deadline changes remain pending until deterministic task materialization is implemented.

## Authentication boundary

The current sync command accepts a bearer token only through an environment variable (default `BRIGHTSPACE_TOKEN`), never a command-line argument, to reduce shell-history leakage.

Persistent Playwright SSO/token capture is a later slice, informed by d2l-cli but not yet implemented.
