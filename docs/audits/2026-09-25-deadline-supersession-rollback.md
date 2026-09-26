# Audit — Deadline Supersession and Rollback

Date: 2026-09-25 (America/Toronto)

## Scope

This slice closes the lifecycle around reviewed deadline changes after Brightspace Assignment/Quiz objects have already been mapped to stable AcademicOS Tasks.

Implemented behavior:

- persist supersession relationships between CandidateEvents;
- persist a chain of Task deadline changes;
- supersede an older pending deadline Candidate when a newer unambiguous Candidate targets the same Task;
- supersede an already-applied deadline change when a newer reviewed change is accepted;
- rollback only the currently applied deadline change;
- restore the immediately preceding deadline change when rollback is chain-safe;
- reject a newer pending Candidate and restore the older pending Candidate it had superseded;
- let authoritative structured Brightspace Assignment/Quiz due dates supersede an announcement-derived applied change;
- repair supersession links when an edited announcement causes its stale pending Candidate to be deleted and re-extracted;
- expose review operations through `academicos-changes`.

## Schema

Schema version: **v8**.

`candidate_events` adds:

- `superseded_by_candidate_id`
- `superseded_at`
- `rolled_back_at`

Candidate lifecycle now includes:

- `pending`
- `accepted`
- `auto_accepted`
- `rejected`
- `superseded`
- `rolled_back`

`task_deadline_changes` adds:

- `status` (`applied`, `superseded`, or `rolled_back` in current code paths)
- `supersedes_change_id`
- `superseded_at`
- `rolled_back_at`

The v8 migration normalizes older deadline history so only the most recent historical deadline change remains `applied` per Task.

## Deadline chain semantics

Example:

```text
Task due Oct 1
  ↓ accept Candidate A
Oct 5  [A applied]
  ↓ accept Candidate B
Oct 7  [B applied, A superseded]
  ↓ rollback B
Oct 5  [B rolled_back, A reactivated]
```

A rollback is refused when the Task's current `due_at` no longer equals the change being rolled back. This prevents an old Candidate from overwriting newer truth.

An older superseded change cannot be rolled back while a newer change is active. The caller must rollback from the current head of the change chain.

## Source precedence

Structured Brightspace Assignment/Quiz objects are treated as authoritative for their own Task fields.

If an announcement-derived deadline change is currently applied and a later structured Brightspace sync reports a different due date:

1. the announcement-derived deadline change is marked `superseded`;
2. its Candidate is marked `superseded`;
3. the structured Brightspace due date becomes the Task due date;
4. the obsolete announcement change can no longer be rolled back over that newer structured value.

This preserves the rule that free-text interpretation cannot override a newer structured LMS fact.

## Edited announcement repair

Announcement edits replace stale, unaccepted extracted Candidates. Before a stale pending Candidate is deleted, AcademicOS now restores any directly superseded predecessor that was never materialized as a Task deadline change.

The edited announcement is then re-extracted and can supersede that predecessor again. This prevents dangling `superseded` Candidates whose `superseded_by_candidate_id` points at a deleted Candidate.

## CLI

New command group:

```text
academicos-changes list
academicos-changes accept <candidate-id>
academicos-changes reject <candidate-id>
academicos-changes rollback <candidate-id>
```

The older main CLI review commands remain available for compatibility.

## CI findings during implementation

CI was intentionally treated as an acceptance gate and caught real issues.

### Failure 1 — v8 migration assumed a complete legacy schema

A migration run against the project's intentionally minimal v1/v4 migration fixtures failed with:

```text
sqlite3.OperationalError: no such table: candidate_events
```

Fix: migration 008 now recreates the v7-compatible `candidate_events` shape only when it is absent before applying v8 columns. This keeps old/minimal migration paths testable without changing normal databases where the table already exists.

### Failure 2 — nondeterministic Candidate selection in the new test

The first supersession test selected the newest Candidate using `created_at`. SQLite's default timestamp resolution is seconds, so two Candidates inserted in the same second could be ordered by ID rather than insertion intent.

Fix: tests now locate the Candidate through its exact Evidence → SourceItem relationship and Brightspace announcement source ID. This also better reflects the actual provenance model.

### Review finding — edited source could leave a dangling supersession

`delete_pending_candidates_for_source()` previously deleted a stale pending Candidate without restoring an older pending Candidate that it had superseded.

Fix: eligible unmaterialized predecessors are restored before the stale Candidate is removed and the edited source is re-extracted.

## Final automated validation

Final verified feature HEAD before this audit document:

```text
22eac33a0dde98babfaa467c931dcd9d60487222
```

GitHub Actions run 198 (`36213108193`):

- Python 3.11: success
- Python 3.12: success
- Ruff correctness checks: success
- pytest: success
- Python 3.11 log: **95 passed in 1.66s**

Covered scenarios include:

- pending Candidate supersession;
- rejection restoring the predecessor;
- applied deadline supersession;
- rollback restoring the previous due date;
- rollback reactivating the previous applied Candidate/change;
- refusal to rollback a superseded older change;
- structured Brightspace due dates superseding announcement-derived changes;
- edited announcement supersession repair;
- schema migration to v8.

## Known limitations

- Rollback is currently implemented for `deadline_changed` only. Class cancellation/move/location/mode override rollback is not implemented in this slice.
- When a superseded parent deadline Candidate is reactivated after rollback, it is restored as `accepted`; historical `auto_accepted` provenance is not separately restored. Current deadline Candidates are intentionally below the default automatic acceptance threshold, so this does not affect the normal deadline path.
- CI validates deterministic state transitions and migrations, not uOttawa's live Brightspace response shapes or the user's Windows runtime. Live account validation remains a separate deployment gate.
