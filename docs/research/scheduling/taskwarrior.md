# Taskwarrior — dynamic urgency reference

Upstream: `GothenburgBitFactory/taskwarrior`

Role in AcademicOS: reference for **computing urgency from several live factors instead of storing one permanent priority number**.

## Key idea

Taskwarrior exposes configurable urgency coefficients for factors including due date, task age, blocking/blocked relationships, scheduled status, tags/projects, and other task metadata.

The architectural lesson is more important than the exact formula:

```text
priority = f(current state)
```

not:

```text
priority = fixed number entered once
```

## AcademicOS translation

A university task's live score should be built from academic state such as:

- deadline pressure;
- remaining-work pressure;
- grade/assessment impact;
- blocking/prerequisite importance;
- course risk;
- backlog age;
- user-stated priority;
- uncertainty in the remaining-work estimate;
- exam/quiz proximity;
- current progress.

Possible negative terms:

- bad time-of-day fit;
- excessive context switching;
- insufficient break;
- late-night/fatigue cost;
- fragmentation;
- schedule disruption cost.

## Workload pressure is different from due-date pressure

AcademicOS should explicitly model:

```text
remaining_work / usable_capacity_before_deadline
```

A large assignment due in a week can be more urgent than a one-hour task due tomorrow if future free capacity is already constrained.

## Dependency lesson

Taskwarrior's blocking relationships map naturally to student work:

```text
read lab manual -> do prelab -> perform lab -> submit report
```

The planner should use dependencies as both hard ordering constraints and an urgency signal when one task blocks several later tasks.

## Reuse strategy

Reimplement the urgency concept with AcademicOS-specific features rather than copying Taskwarrior's exact coefficients. Verify upstream license before adapting source.
