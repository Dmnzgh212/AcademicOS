# Audit — Brightspace Task Identity and Deadline Materialization

Date: 2026-09-25

Status: implemented and CI verified. Real uOttawa account validation remains required for institution-specific Brightspace response shapes.

## Scope

This slice closes the deterministic path from structured Brightspace assignment/quiz objects into AcademicOS Tasks and adds a conservative path for professor announcement deadline changes.

## Schema v7

Schema v7 adds:

- `task_source_links` — durable mapping from a Brightspace source identity to one local Task;
- `task_deadline_changes` — append-only audit rows recording accepted old/new due dates.

Both fresh databases and migrations from earlier schemas are covered by tests.

## Structured Brightspace -> Task

Assignments and quizzes already persisted in `source_items` are reconciled after normal full sync.

Stable identity:

```text
Brightspace org unit + dataset + external object ID
        -> task_source_links
        -> stable UUID5 AcademicOS Task ID
```

Structured source updates may change only source-authoritative Task fields:

- course association;
- title;
- task type;
- due date.

They deliberately do not reset user-owned execution state:

- progress;
- actual spent minutes;
- remaining minutes;
- task status.

Default initial estimates are conservative placeholders until the adaptive velocity model has history:

- assignment: 90 minutes, importance 0.60;
- quiz: 45 minutes, importance 0.70.

Hidden Brightspace objects and objects without a stable external ID are skipped rather than guessed.

Task reconciliation is replayable from local `source_items`, keeping the large Brightspace collector decoupled from task semantics. A reconciliation failure is attached to the sync report as `task_reconcile`, making the run partial instead of destroying otherwise collected source data.

## Free-text deadline announcements

Professor announcement text is intentionally treated differently from structured API data.

A `deadline_changed` CandidateEvent receives a Task target only when exactly one pending/in-progress Task in the same course has an explicit normalized title contained in the announcement title/body. No fuzzy nearest-match is used.

Outcomes:

- unique explicit match -> `target_ref=task_id`, confidence 0.94;
- zero or ambiguous matches -> no target, confidence capped at 0.82.

The default announcement auto-accept threshold remains 0.98, so even a unique free-text deadline match still requires review rather than silently changing the Task.

## Accepted deadline materialization

When a targeted `deadline_changed` candidate is accepted, AcademicOS validates:

- a target Task exists;
- candidate and Task course associations agree;
- the new due date is valid ISO-8601.

It then atomically:

1. writes `task_deadline_changes(old_due_at, new_due_at, candidate_event_id)`;
2. updates `tasks.due_at`;
3. returns `action_type=task_deadline_update`.

The Planner already reads Task due dates dynamically, so the next planning pass sees the accepted deadline automatically.

## State-machine repair

This slice also fixed an existing terminal-state gap: `AUTO_ACCEPTED` is now treated as terminal alongside `ACCEPTED` and `REJECTED`, preventing accidental second acceptance of an already auto-applied candidate.

## Verification

New regression tests cover:

- Assignment and Quiz -> stable Tasks and source links;
- structured due-date updates preserve Task identity/progress/spent/remaining state;
- unique Assignment deadline announcement -> targeted Candidate -> accepted Task due-date update;
- old/new due dates are preserved in the deadline-change audit table;
- ambiguous duplicate titles do not guess a target;
- schema v7 fresh initialization and migrations.

CI findings during the slice were real but non-functional maintenance issues:

- three older tests still expected schema v6 after the v7 migration;
- a new test file contained two unused imports, correctly rejected by Ruff.

Both were corrected before completion.

Final feature commit verification (`ea7c1edf2c3703bf1421d81960a301bedcec0eb0`):

- GitHub Actions: success;
- Python 3.11: Ruff passed, pytest passed;
- Python 3.12: Ruff passed, pytest passed;
- Python 3.12 snapshot: **91 passed**.

## Remaining limitations

- Real uOttawa Brightspace assignment/quiz payload shapes still need first-account validation on the user's Windows machine.
- No fuzzy/LLM task-target guessing is intentionally implemented for free-text deadline changes.
- Accepted deadline-change rollback/supersession is not yet implemented; the audit trail now provides the data needed to implement it safely.
- Structured Brightspace task deletion/closure semantics need real tenant evidence before automatically cancelling local Tasks.
