# Fluxure — scheduling-engine reference

Upstream: `FluxureCalendar/Fluxure`

Role in AcademicOS: strongest current reference for **Calendar v0.1 scheduling mechanics**.

## Verified upstream design

Fluxure separates scheduling into a pure engine with no DB/auth/I/O side effects. Its engine takes domain objects, existing calendar events, and user settings, then returns calendar operations.

Core algorithm documented upstream:

1. convert habits/tasks/meetings into schedulable items;
2. sort by priority and item type;
3. generate candidate slots;
4. score candidates and place the best slot;
5. place focus time after higher-priority items;
6. diff against existing managed events to emit minimal create/update/delete operations.

Important modules observed:

- `scheduler.ts` — main scheduling loop;
- `scoring.ts` — slot scoring;
- `slots.ts` — candidate-slot generation;
- `free-busy.ts` — busy-time computation;
- `timeline.ts` — scheduling windows;
- `quality.ts` — schedule health score.

## Scoring ideas worth reimplementing

Fluxure uses several independent slot signals rather than one fixed priority:

- ideal-time proximity;
- buffer compliance;
- continuity/dependency proximity;
- generic time-of-day preference.

The ideal-time component uses Gaussian decay: a slot loses value smoothly as it moves away from the preferred time instead of using crude binary windows.

AcademicOS should preserve this shape, but replace the objective terms with student-specific ones such as deadline safety, workload pressure, course balance, focus length, and schedule churn.

## Chunking

Fluxure splits long tasks into bounded chunks and avoids tiny final fragments by merging or redistributing them. Chunks can depend on the previous chunk so ordering is preserved.

AcademicOS should adopt the behavior, with student defaults such as 30-minute minimum, 60–90-minute preferred blocks, and 120-minute maximum unless the user/task type says otherwise.

## Schedule quality

Fluxure exposes a 0–100 schedule quality score built from multiple components rather than claiming a plan is simply "optimal".

AcademicOS should use the same transparency principle with different metrics:

- deadline safety;
- workload coverage;
- high-priority placement;
- break/buffer quality;
- sleep protection;
- course balance;
- overload risk;
- plan stability.

## Architecture lesson

The most important lesson is to keep the scheduling engine a pure deterministic module:

```text
facts + tasks + availability + settings
            -> planner engine
            -> proposed plan operations
```

Database writes and UI updates should happen outside the scoring engine.

## License caution

Fluxure declares AGPL-3.0. AcademicOS should **reimplement the ideas independently** rather than copy engine source into a differently licensed core unless a deliberate licensing decision is made.

Reviewed source during research: `packages/engine/README.md`, `scoring.ts`, `scheduler-items.ts`.
