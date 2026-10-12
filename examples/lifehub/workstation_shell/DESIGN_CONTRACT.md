# Workstation Shell — phase 1

The approved visual source is `LifeHub_platform_design_v2.pptx`, especially slide 2 (course/project workbench). Later suggestions are ideas for evaluation, not automatic scope changes. The previous implementation failed by exposing the discussion labels “需求面 / 工作面 / 执行面” as three product planes and making a large request editor the workspace.

This correction changes presentation components and routes, not the LifeHub Engine or the local browser protocol.

| PPT element | Phase 1 implementation | Remaining verification |
| --- | --- | --- |
| Quiet off-white shell, pine-green active project | `ui/shell.js`, `ui/workspace.css`, selected Lucide SVGs | Actual browser visual comparison |
| Left course/term and project folders | Shared navigation with contextual folder links | Long real course/project names |
| Source / report / browser / run-history bar | Workspace tabs; request form moves into an explicit dialog | Desktop keyboard and pointer QA |
| Original beside a report | Two independent panes, native PDF or safe text, report preview/raw switch | Real PDF viewer sizing |
| Right current-run timeline | Actual steps, waiting, pause/resume and saved-result count | Real Windows/browser transitions |
| Current run / project resources | Contextual inspector tabs; centralized resource versions and source checks | Panel visual QA |
| Old input survives source updates | Current run opens its pinned source version | Covered by model tests |
| Work can be reopened | Existing request/run IDs open the workbench | Covered by handler tests |

`reference.html` uses the same components with explicitly labeled isolated fixture data. It never saves fixture records to the user's workspace. Its curves are analytical layout examples, not user measurements or evidence of completed scripts.

## Modules

- `ui/base.css`: shared primitives and native dialogs.
- `ui/shell.js`: navigation and breadcrumbs.
- `ui/workbench.js`: document selection, simultaneous panes, right inspector.
- `ui/markdown.js`: minimal safe reader. Advanced math/tables defer to a mature renderer module.
- `ui/icons.js` and `vendor/lucide-LICENSE.txt`: selected localized Lucide SVGs with required licenses.
- Existing workflow, station and browser components remain data/execution adapters. Runtime tests do not prove visual fidelity.

## Next stages

1. Visually verify the workbench against slide 2, including text, PDF, waiting reply and saved report.
2. Refine schedule and lib against slides 1 and 4 as separate changes.
3. Refine browser canvas and takeover against slides 5 and 6. Existing protocol tests do not imply visual acceptance.
4. Check the resources panel against slide 7 with real resources. No automatic habit distillation.

Node tests verify handlers, data scope, pinned versions and safe preview. They do **not** verify pixels. The supported `$control-browser` capability is unavailable in this environment; no substitute browser was installed or used. Browser screenshots, overlap checks and Windows acceptance remain unverified. This is a reviewable phase-1 UI implementation, not full PPT acceptance, M1 acceptance or a finished platform.
