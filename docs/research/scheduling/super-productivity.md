# Super Productivity — time-tracking and planner UX reference

Upstream: `super-productivity/super-productivity`

Role in AcademicOS: reference for **timeboxing, actual-vs-estimated work, remaining-time display, and local-first planner UX**.

## Important behavior found during research

Super Productivity stores both estimated work and tracked work. Core task logic repeatedly distinguishes:

```text
timeEstimate
timeSpent
remaining = max(timeEstimate - timeSpent, 0)
```

It also rolls child/subtask estimates and spent time into higher-level task views.

This is more useful to AcademicOS than a traditional calendar that only stores a planned start/end time.

## What AcademicOS should borrow

- explicit Start / Pause / Done study sessions;
- planned duration vs actual tracked duration;
- remaining-work calculations;
- timeboxing in the planner UI;
- daily review of planned vs completed work;
- task/subtask rollups;
- schedule conflict detection around remaining task duration.

## What AcademicOS should add

Super Productivity tracks the discrepancy but AcademicOS should **learn from it**.

For completed tasks, store:

```text
estimate_at_start
actual_focused_time
completion_ratio / completion state
course
task_type
context
```

Then update a hierarchical personal velocity model:

```text
global estimate factor
    -> course factor
        -> course + task-type factor
```

Example:

```text
user estimate: CEG2136 lab = 120 min
historical CEG2136 lab factor = 1.25
planner budget = 150 min
```

The early implementation should use robust statistics and shrink small-sample estimates toward 1.0 rather than overfitting one bad session.

## UI lesson

Expose both values to the user:

```text
planned: 90 min
tracked: 65 min
estimated remaining: 42 min
```

This makes replanning understandable instead of feeling like an opaque AI changed the schedule.

## Integration stance

Do not embed or depend on the whole Super Productivity application. Borrow the task/time model and interaction patterns selectively after verifying current license compatibility for any copied source.
