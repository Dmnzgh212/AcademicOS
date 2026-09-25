# Constraint-solvers — Timefold and OR-Tools

Upstreams:
- `TimefoldAI/timefold-solver`
- `google/or-tools`

Role in AcademicOS: future references for **hard/soft constraints and globally optimized scheduling** when the initial greedy planner becomes insufficient.

## Timefold: conceptual model

Timefold's planning model is useful for thinking clearly about what the planner may and may not change.

### Hard constraints

Violations are unacceptable:

- two events overlap;
- study block occurs during a class/exam;
- a task is scheduled after its deadline;
- a required prerequisite is scheduled after its dependent task;
- a pinned/started/completed block is moved;
- an explicitly unavailable period is used.

### Soft constraints

Violations are allowed but reduce schedule quality:

- user prefers a different time of day;
- break is shorter than ideal;
- too much of one course is clustered together;
- a difficult subject is scheduled during low-energy hours;
- a task is fragmented into too many pieces;
- a plan changes unnecessarily after the user has already seen it.

### Pinned entities

Timefold's notion of pinned planning entities maps well to AcademicOS:

```text
completed block -> pinned
started block -> pinned
fixed class/exam -> not a planning entity at all
near-term user-locked block -> pinned
```

## OR-Tools: likely future implementation path

OR-Tools is a better technical fit than Timefold for AcademicOS because it has a mature Python API.

Potential CP-SAT representation:

- each study chunk -> optional/fixed-duration interval variable;
- class/exam/unavailable time -> blocked intervals;
- `NoOverlap` for a user's timeline;
- precedence constraints for dependent tasks;
- deadline constraints;
- objective terms for slot quality and disruption.

## Why not start with CP-SAT

Calendar v0.1 should use a deterministic greedy scorer because:

- easier to inspect and debug;
- easier to explain to the user;
- easier to make stable under frequent small updates;
- sufficient for a single student's early workload;
- lower implementation/maintenance complexity.

Upgrade only when real cases show that greedy placement is producing avoidable conflicts or poor global allocation.

## Migration design rule

Keep the planner interface solver-agnostic:

```text
PlannerInput
  facts
  tasks
  availability
  preferences
  existing plan

PlannerEngine.plan(input) -> proposed operations + quality metrics
```

Then a future `CpSatPlannerEngine` can replace `GreedyPlannerEngine` without changing storage or UI semantics.

## Licensing

Timefold was observed under Apache-2.0 during research. OR-Tools is an established open-source Google optimization project; verify the exact current license/version immediately before adding it as a dependency.
