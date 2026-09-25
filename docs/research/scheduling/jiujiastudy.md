# jiujiastudy / 救驾 — deterministic study-planner reference

Role in AcademicOS: reference for **simple deterministic planning before AI presentation**.

## Why it matters

The strongest idea is architectural rather than model-specific:

> collect fresh facts -> deterministic planner/state machine -> optional AI wording

This matches AcademicOS's `Script first, AI last` rule.

## Ideas worth retaining

- refresh source data before generating deadline/week reports;
- use a structured source of truth instead of trusting conversational memory;
- keep planning logic deterministic and inspectable;
- separate must-do work from useful-but-deferrable work;
- use explicit user states such as normal / behind / stuck / overload;
- provide conservative default duration estimates when no better evidence exists;
- treat AI as an overlay, not the scheduler itself.

A useful AcademicOS translation is:

```text
MUST      -> deadline/safety-critical blocks
SHOULD    -> important but movable study work
PARKING   -> optional review/enrichment
```

## Where AcademicOS goes further

AcademicOS should not keep fixed duration assumptions forever. It adds:

- actual session timing;
- personal estimation-bias factors;
- workload pressure from remaining work / usable capacity;
- event-driven rescheduling;
- evidence-backed calendar changes;
- schedule stability penalties so plans do not constantly jump around.

## Reuse strategy

Treat this primarily as planner/state-machine inspiration until the exact current upstream repository and license are re-verified. Do not copy code solely from remembered snippets or old snapshots.
