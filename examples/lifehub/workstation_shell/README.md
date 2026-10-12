# LifeHub workstation shell — phase 1

This is a standalone UI component module proposed in a Draft PR. It repairs the mismatch between the approved workstation presentation and a large three-plane request-form implementation.

The host supplies state and actions. This module renders navigation, simultaneous original/result panes, current-run history and project resources. It does not import the Engine, start a process, fetch course data or execute scripts. The existing private Site wires this module to its existing data and browser adapters; backend behavior remains outside the presentation module.

## Localized reuse

Selected Lucide SVG source is copied locally with ISC / Feather MIT notices and exact source blob identifiers in `vendor/lucide-source.json`. No remote icon loader is required. Native browser PDF viewing is reused. Basic safe text preview is small local code; advanced math/document rendering is a later module, not a fresh general renderer.

## Files

| Module | Responsibility |
| --- | --- |
| `ui/shell.js` | Course/term and project navigation, breadcrumbs |
| `ui/workbench.js` | Selection, simultaneous source/output, current-run inspector |
| `ui/document-scope.js` | Read-only material references and latest versions |
| `ui/markdown.js` | Basic safe text preview |
| `ui/base.css`, `ui/workspace.css` | Shared primitives and reference proportions |
| `ui/reference-state.js`, `ui/reference.js`, `index.html` | Isolated visual fixture using the same components |

`createWorkbench(ctx)` receives `getState`, `fileOp`, `asset`, `runId`, `selectAsset`, `selectRun`, `draft`, `render`, `modal`, `change`, `go`, `toast`, escaping/button helpers and an optional existing station view adapter. It does not acquire authority from these record fields; the host owns actions and authorization. Progress updates can refresh the inspector without remounting the source reader or losing PDF position.

## Developer validation

Run `node --test tests/workbench.test.mjs` from this directory. No dependency installation is required. Serve this directory through an ordinary static host to open the isolated fixture. The normal user opens the private deployed Site and does not need to build or run a local developer server.

The fixture is explicitly labeled sample data. It does not write personal records, run analysis, connect a browser or create genuine execution evidence. The analytical curves only inspect the report layout.

## Acceptance scope

See `DESIGN_CONTRACT.md` for the approved PPT mapping and staged work. Data/handler/preview checks passed in Node. Actual browser screenshot comparison, real PDF viewer sizing and Windows UI verification are **unverified**, because the current development environment lacks the supported browser-control capability. This Draft is not full PPT visual acceptance, an Engine integration, M1 acceptance or a product release. Keep it independent of the active M1 runtime stack and do not merge automatically.
