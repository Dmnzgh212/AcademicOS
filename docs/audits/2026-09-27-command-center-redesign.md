# AcademicOS command-center redesign audit — 2026-09-27

## Why the previous dashboard felt wrong

The previous page was a status report: four metrics, a count-only weekly strip, a daily timeline, and several passive lists. It exposed database state but did not answer the operating questions AcademicOS is supposed to answer: what is happening now, what comes next, where the week is overloaded, which work is covered by the current plan, and which source changes can alter the plan.

## Changes in this slice

- Replaced the count-only week strip with a real 08:00–22:00 weekly time surface.
- Rendered Truth Calendar sessions and movable Plan Calendar blocks on the same calendar while keeping them visually distinct.
- Added Now / Next state at the top of Today.
- Reframed the top area as a live brief instead of four database metrics.
- Added an execution queue that shows remaining work, planned coverage for today, and deadline pressure.
- Promoted Changes Inbox evidence so a candidate can be understood without opening raw source content.
- Renamed recent activity to Source pulse to keep source changes separate from tasks and facts.
- Surfaced collection freshness as a top-level data-status chip.
- Added a privacy-safe synthetic demo dataset with six fictional courses, tasks, plan blocks, source activity, reviewed-state candidates, and a recent successful sync.
- Added `academicos-demo`, which refuses database filenames that do not contain `demo`.

## What this deliberately does not solve yet

This slice changes information architecture and evaluation quality. It does not yet make the web UI a full mutation surface. Accept/reject candidate actions, drag/re-pin plan blocks, manual task progress updates, and one-click replanning remain command-line or future interaction work.

## Product direction to preserve

AcademicOS should remain an execution layer rather than a passive dashboard. The intended hierarchy is:

1. What is true now (fixed classes, accepted changes, source freshness).
2. What should I do next (Now / Next and current execution queue).
3. What is the shape of the week (fixed + movable time blocks in one surface).
4. What changed externally (Changes Inbox and Source pulse).
5. Replan only future movable work; never silently mutate Truth Calendar from ambiguous source text.

## Validation

The redesign and demo seed are covered by automated tests. Latest feature head passed Ruff and pytest on Python 3.11 and 3.12 with 98 tests passing.
