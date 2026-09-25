# Calendar and Adaptive Planner Design

## Three concepts

### Truth Calendar
Factual commitments and overrides.

### Plan Calendar
Movable study/work blocks.

### Activity Feed
Changes worth knowing about but not necessarily calendar events.

## Candidate-event pipeline

```text
source item
 -> extraction
 -> candidate event
 -> evidence + confidence
 -> conflict resolution
 -> accepted fact / activity / suggested task
```

Examples:
- “There will be no lecture tomorrow.” -> high-confidence cancellation
- “We may move Friday online.” -> candidate only
- “Review Chapter 4 before Friday.” -> suggested task

## Base timetable + overrides

The semester timetable is the base schedule. One-off changes are overlays rather than destructive edits.

## Adaptive duration model

Store:
- initial estimate
- current remaining estimate
- actual tracked time
- progress
- course
- task type
- deadline

Learn personal estimation bias with hierarchical fallback:

1. global multiplier
2. course multiplier
3. course + task-type multiplier

Start with robust median ratios with shrinkage toward 1.0; later add EMA for recency.

## Workload pressure

Use more than deadline distance.

A useful feature is:

```text
remaining_estimated_work / usable_free_time_before_deadline
```

## Dynamic urgency

Candidate factors:
- deadline pressure
- remaining workload pressure
- grade impact
- course risk
- prerequisite/blocking importance
- backlog age
- user priority
- uncertainty
- newly announced exam/quiz
- current progress

Possible penalties:
- bad time-of-day fit
- excessive same-course concentration
- insufficient breaks
- switching cost
- fatigue/late-night penalty
- fragmentation

## Slot scoring

First implementation: deterministic greedy scoring.

1. split tasks into chunks;
2. generate feasible slots;
3. score slots;
4. place high-priority items first;
5. minimize unnecessary changes to existing plans.

Possible score components:
- deadline safety
- urgency
- preferred time
- continuity
- buffer compliance
- focus-length fit
- course balance
- disruption penalty

## Chunking

Initial defaults:
- minimum block: 30 min
- preferred: 60–90 min
- maximum: 120 min

Avoid tiny leftovers by merging or redistributing chunks.

## Hard vs soft constraints

### Hard
- no overlap with classes/exams
- no plan after deadline
- started/completed blocks stay fixed
- prerequisite ordering when required
- unavailable/sleep periods blocked

### Soft
- preferred time of day
- breaks
- course variety
- continuity
- focus length
- safety margin before deadline

v0.1 uses greedy scoring. OR-Tools CP-SAT is the future upgrade path.

## Event-driven replanning

Replan on meaningful state changes:
- deadline changed
- new exam/quiz
- class cancelled/moved
- task progress materially changed
- tracked session overruns
- availability changes
- new important task

Rules:
- never move completed blocks
- normally do not move started blocks
- penalize schedule churn
- preserve near-term plans unless a strong reason exists

## Daily outputs

### Morning Brief
- today’s fixed events
- changes since yesterday
- new academic material
- upcoming deadlines
- planned study blocks
- overload/risk warnings

### Evening Summary
- completed vs planned
- actual vs estimated time
- unfinished work
- changes since morning
- tomorrow preview
- rollover decisions

### Weekly Plan
- fixed commitment hours
- workload estimate
- free capacity
- deadline clusters
- overload days
- early-start recommendations

## Schedule quality

Expose a transparent quality score using:
- deadline safety
- workload coverage
- high-priority placement
- buffer quality
- focus-time fit
- sleep protection
- course balance
- overload risk
- schedule stability
