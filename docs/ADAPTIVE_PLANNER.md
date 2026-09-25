# Adaptive Planner v0.1

## Goal

AcademicOS should not treat a user estimate such as “this lab will take two hours” as permanently correct. The planner should learn personal execution speed and continually rebuild only the movable part of the schedule.

## Open-source ideas used

### Fluxure
Reimplemented concepts:
- pure scheduling layer;
- task chunking;
- free/busy calculation;
- greedy placement;
- movable plan diff rather than rewriting fixed calendar facts.

Fluxure is AGPL-3.0, so AcademicOS uses independently written code and does not copy its engine.

### Taskwarrior
Reimplemented concept:
- urgency is computed from current factors rather than stored as one permanent priority number.

### Super Productivity
Reimplemented concept:
- estimated work and actual time spent are separate signals.

## Personal velocity model

Completed tasks provide ratios:

```text
actual_spent_minutes / initial_estimate_minutes
```

The lookup hierarchy is:

1. course + task type;
2. course;
3. global;
4. neutral 1.0 fallback.

Sparse history is intentionally shrunk toward 1.0 rather than trusting one unusual task. The current robust estimate uses a median ratio with sample-count shrinkage and clamps the multiplier to a conservative range.

Example:

```text
User estimate: 120 min
Learned CEG2136 lab multiplier: 1.25
Planner budget: 150 min
```

## Dynamic urgency

Planner v0.1 recomputes task urgency each run from:

- workload pressure: adjusted remaining work / free capacity before deadline;
- deadline pressure;
- user/task importance.

Current weighting:

```text
45% workload pressure
35% deadline pressure
20% importance
```

These are explicit configuration candidates, not claimed universal constants.

## Free time

Free intervals are constructed from the planning window, then subtract:

- Truth Calendar sessions plus buffers;
- pinned plan blocks;
- started blocks;
- completed blocks.

Only ordinary future `planned` blocks are replaceable.

## Chunking

Default chunk targets:

- minimum 30 min;
- preferred around 90 min;
- maximum 120 min.

Long tasks are balanced across chunks to avoid a tiny unusable remainder.

## Replanning

Each planner run gets an ID. Persisted replanning deletes only movable, unpinned `planned` blocks in the selected future window and inserts the new plan.

The following are protected:

- Truth Calendar facts;
- pinned blocks;
- started blocks;
- completed blocks.

## Current limitation

v0.1 uses a deterministic first-fit greedy placement after urgency sorting. It does not yet score time-of-day preference, fatigue, subject switching, or schedule churn as richly as the final design intends.

If the greedy approach becomes insufficient, OR-Tools CP-SAT remains the preferred Python-native upgrade path for hard/soft constraint optimization.
