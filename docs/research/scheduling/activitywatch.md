# ActivityWatch — optional local activity-feedback reference

Upstream: `ActivityWatch/activitywatch`

Role in AcademicOS: optional future source of **passive local activity evidence**, not a required part of Calendar v0.1.

## Why it is interesting

ActivityWatch records local timestamped activity such as:

- active application/window;
- browser activity through optional watchers;
- AFK/idle periods;
- event buckets and durations.

This could later help AcademicOS compare a planned study block with what actually happened on the computer.

Example:

```text
planned 19:00–20:30 MAT2322
actual desktop evidence:
19:02–19:43 PDF/notes
19:43–20:02 unrelated browser activity
20:02–20:31 PDF/notes
```

## Why it should remain optional

Desktop activity is not the same as studying:

- paper problem solving may look idle;
- lectures/labs happen away from the computer;
- a browser tab does not prove attention;
- passive monitoring can feel intrusive.

Therefore v0.1 should use explicit session controls:

```text
Start
Pause
Done
```

ActivityWatch may later serve as a secondary signal, never the sole source of truth for effort or productivity.

## Possible future integration

A local adapter could import coarse session evidence and offer suggestions such as:

> Planned 90 min, timer recorded 70 focused min, passive desktop data suggests about 15 min of interruption. Keep the tracked timer result unless the user corrects it.

The adapter should read local ActivityWatch data and preserve its local-first privacy model.

## Design rule

AcademicOS must not become a surveillance product. Passive telemetry is opt-in, inspectable, and subordinate to explicit user input.
