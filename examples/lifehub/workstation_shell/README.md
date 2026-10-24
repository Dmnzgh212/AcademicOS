# LifeHub workstation shell — PPT page components

This is a standalone UI component module proposed in a Draft PR. It repairs the mismatch between the approved workstation presentation and a large three-plane request-form implementation.

The host supplies state and actions. This module renders navigation, simultaneous original/result panes, current-run history, project resources, schedule, library, source updates and browser canvas. It does not import the Engine, start a process, fetch course data or execute scripts. The existing private Site wires this module to its existing data and browser adapters; backend behavior remains outside the presentation module.

## Staged reconstruction

Current UI checkpoint: [W0 browser check](docs/W0-browser-check.md) now records actual fixed-viewport layout measurements and scaled browser captures. It fixes navigation wrapping, sidebar spacing, pane proportions and placeholder contrast. This is structural QA, not final visual or product acceptance. Next is only W1’s minimal context/material entry and one real text reader. Earlier pending-W0 statements below describe prior checkpoints.


The [goal-alignment review](docs/GOAL_ALIGNMENT_REVIEW_2026-10-17.md) distinguishes the approved visual framework from incomplete product behavior and unverified implementation. The [single-course workflow](docs/SINGLE_COURSE_WORKFLOW.md) now defines context assignment, existing-method selection, actual results and evidence-based progress updates. It keeps the approved layout; W0 is still pending. W1's first slice includes a minimal context/material entry and one real text reader, with PDF verified separately. These are design requirements, not newly connected features.

Read the complete [8-slide implementation plan](docs/IMPLEMENTATION_PLAN.md) and [reuse research](docs/REUSE_RESEARCH.md) first. The plan maps every slide to modules, proposed application contracts, dependencies, small commits and separate acceptance gates. Its next UI task remains W0: compare and correct the existing slide-2 skeleton in a real browser. The planning baseline changed documents only; later implementations are recorded in their own checkpoints.

The [2026-10-15 audit](docs/DESIGN_PLAN_AUDIT_2026-10-15.md) corrects dependencies and explicit delivery gaps: monitoring before browser actions, persisted work/run records, PDF text, report assets, navigation and migration gates. Static skeleton regeneration is reproducible; W0 visual acceptance remains pending.

The independent [D0 material-reader checkpoint](docs/D0-material-reader.md) adds a bounded read-only adapter and metadata schema over existing host records. It reads an exact historical version, checks context/reference scope and actual original availability, and withholds results invalidated during async IO. It does not change the skeleton, access personal storage, connect a browser, integrate the local service or deploy the Site. Schema parsing and eight Node boundary checks are recorded separately from pending browser/Windows validation.

[C0's first small delivery](docs/C0-work-drafts.md) adds work-draft creation/update over existing host requests, revision conflicts, missing-input labels and a synchronous host-persistence controller. Eight new checks include temporary-file reopen, failed-save rollback and a fixed-version read through D0; the combined 16 checks pass. The module is not wired to the page and does not start runs. Command acceptance and run events belong to the next checkpoint below; browser/Windows validation remains pending.

[C0's second small delivery](docs/C0-run-admission.md) accepts only local organize requests, saves fixed work/input/resource snapshots and one accepted event, and replays matching command IDs after reopen without another run or event. Eight additional checks bring these three slices to 24 passing checks. Admission leaves every step pending and the run queued; there is no executor or fake completed report. Public run queries return summaries and bounded event pages without material/resource bodies. Real host wiring and execution remain pending.

The existing integrated UI is not accepted as a PPT reproduction. Begin with [the structural contract](docs/01-workspace-structure.md), then [the stage-02 static skeleton](stages/02-workspace-skeleton/README.md) and [its checkpoint](docs/02-workspace-skeleton.md). Stage 02 can be viewed by opening its self-contained `index.html`; it has no runtime services or personal state. Reading, report and execution panels are separate later steps. This stage does not update the live Site.

## Localized reuse

Selected Lucide SVG source is copied locally with ISC / Feather MIT notices and exact source blob identifiers in `vendor/lucide-source.json`. No remote icon loader is required. Native browser PDF viewing is reused. Basic safe text preview is small local code; advanced math/document rendering is a later module, not a fresh general renderer.

## Files

| Module | Responsibility |
| --- | --- |
| `ui/shell.js` | Course/term and project navigation, breadcrumbs |
| `ui/schedule.js`, `ui/schedule.css` | Duration-aware week grid, agenda, scoped work and source updates |
| `ui/workbench.js` | Selection, simultaneous source/output, current-run inspector |
| `ui/library.js` | Course/term/category folders, scoped current/history material selection and provenance/work links |
| `ui/sources.js` | Scoped source checks, change/failure records and pipeline presentation |
| `ui/resources.js` | Shared project resource inspector and versioned catalog |
| `ui/monitor.js` | One browser canvas/inspector, target-scoped frame/work/items and takeover states |
| `ui/records.js` | Shared read-only labels, safe URLs, reading/check helpers |
| `ui/collections.css`, `ui/readability.css` | PPT collection/browser layouts and text hierarchy |
| `ui/document-scope.js` | Read-only material references and latest versions |
| `ui/markdown.js` | Basic safe text preview |
| `ui/base.css`, `ui/workspace.css` | Shared primitives and reference proportions |
| `ui/reference-state.js`, `ui/reference.js`, `index.html` | Isolated visual fixture using the same components |

`createWorkbench(ctx)` receives `getState`, `fileOp`, `asset`, `runId`, `selectAsset`, `selectRun`, `draft`, `render`, `modal`, `change`, `go`, `toast`, escaping/button helpers and an existing station view adapter. It does not acquire authority from these record fields; the host owns actions and authorization. The host returns the complete `renderMonitor` workspace for the browser route; it is never nested in another workbench. Progress updates can refresh the inspector without remounting the source reader or losing PDF position.

`renderSchedule(state, options, {esc, btn})` is a pure renderer. `scheduleModel` accepts `offset`, `scope`, `weekend` and an optional explicit `{date,time}` clock for reproducibility. The host owns `station-week`, `station-schedule-mode`, `station-schedule-weekend`, `station-edit-event`, `station-add-event`, `station-open-request`, context and source-update actions. `schedule-scope` inputs select the course/project. It imports no Engine and mutates no records. Its clock follows the existing workspace's Toronto timezone. The fixture route is `#schedule`; default fixture remains the workbench.

`renderLibrary`, `renderSources`, `renderUpdates`, `renderCatalog`, `renderMonitor` and `renderProjectResources` are pure presentation functions. The host supplies escaped text/button helpers, transient frame/connection state, original-file availability and local folder paths. Components do not acquire authority from records, invoke services or persist changes. Existing host adapters own save/edit, source checking, folder sync, browser control and resource selection.

Library selection is scoped by material family; filtering cannot leave another course's selected document visible. `resourceModel` distinguishes next-run references from the provided run's immutable snapshot. `monitorModel` drops another target's frame and associates a run only with the selected target/source. A frozen image remains explicitly frozen. The host must validate frame encoding before passing it to the renderer and should never persist frames.

## Developer validation

Run `node --test tests/*.test.mjs` from this directory. No dependency installation is required. Serve this directory through an ordinary static host to open the isolated fixture. The normal user opens the private deployed Site and does not need to build or run a local developer server.

The fixture is explicitly labeled sample data. It does not write personal records, run analysis, connect a browser or create genuine execution evidence. The analytical curves only inspect the report layout. The sample portal is visibly labeled HTML, never a fake screenshot or an assertion of live browser control.

## Acceptance scope

See `DESIGN_CONTRACT.md` for the approved PPT mapping and staged work. Data/handler/preview, schedule, collection/version scope and fixture navigation checks pass in Node. Actual browser screenshot comparison, real PDF viewer sizing and Windows UI verification are **unverified**, because the current development environment lacks the supported browser-control capability. This Draft is not full PPT visual acceptance, an Engine integration, M1 acceptance or a product release. Keep it independent of the active M1 runtime stack and do not merge automatically.

## Host and browser adapter

`adapters/browser-bridge/` retains the existing standalone Chrome/Edge extension, including the target-bound `focus` operation. It uses the same private Site origin and existing optional host/debugger permissions; no new permission is requested. The UI does not call that extension directly. Its host supplies the bridge callbacks. `adapters/HOST_INTEGRATION.patch` records the exact host changes against Site source commit `b700879114c5958e318df551898f00e2c35be948` for engineering review; apply it only to that matching host after copying the UI components. It is not a Core/Engine or M1 runtime patch. The user opens the private Site and the supplied extension bundle; engineering owns integration.





