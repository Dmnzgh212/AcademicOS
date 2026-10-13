# LifeHub PPT implementation contract

The approved source is `LifeHub_platform_design_v2.pptx` (8 slides). Its page structure is the implementation target. Later informal suggestions are evaluated without replacing that target. This is a private workstation with course/project navigation, material/work continuity, source polling, versioned lib and browser feedback. It is not three product planes named after the discussion labels.

## Per-slide audit

| Slide | Required structure / behavior | Current implementation | Unverified or outstanding |
| --- | --- | --- | --- |
| 1 — Schedule | Time grid, Week / Agenda, context filter, work table and upcoming/source rail | `schedule.js`; real duration positioning and overlap lanes; filter applies to all panels; weekends and early/late events visible | Actual desktop/narrow-screen visual comparison |
| 2 — Workbench | Original beside result, current-run timeline and saved files | `workbench.js`; source/output panes; safe text/native PDF; pinned input; request form is a dialog | Real PDF sizing and browser screenshots; no fabricated analysis or ChatGPT reply |
| 3 — Poll / crawl / lib | Checks → changes → valid original/text → versions/references; no-change skip; errors preserve old data | Existing browser/station/lib adapters; `sources.js` and `updates.js` expose actual records and a scoped check action | Only selected loaded page range; course traversal, attachments and actual source end-to-end validation outstanding |
| 4 — Library | Course/term/category folders, table, text preview, provenance/work links, versions and recent check | `library.js`; material-version and project-reference scope; real IndexedDB original availability checked by host | Native Windows folder opening is not available in this hosted shell; the existing user-picked export/sync action is exposed instead |
| 5 — Browser monitor | One browser canvas, address/live/history bar, one run/resource inspector, recent actions | `monitor.js`; the old nested workbench + monitor double inspector removed; actual frame/event data; original-tab focus action | Requires user's local extension and monitor permission; Windows/browser visual acceptance outstanding |
| 6 — Take over / return | User-control banner, pause/stop, return with page check; preserve archived data | Worker control acknowledgments drive the host; user mode replaces controls; frozen frames labeled; existing resume validates page | Real Windows takeover/resume not verified here; no claim of live connection from a fixture |
| 7 — Project resources | Scoped source checks, Skill/method/script versions, newer versions and next-run policy | Shared `resources.js` in workbench and monitor; catalog preview/history; next selection and current-run frozen version shown separately | Arbitrary script execution and automatic habit distillation are not introduced |
| 8 — Windows local execution | UI + executor + source adapter + lib + frozen resource chain in one real work | Existing extension/data path preserved; no Core/Engine/M1 change | PowerShell/background executor and whole-course adapter are not wired by this UI module; a real source→lib→work→saved result run is not claimed |

## Concrete corrections in this revision

- Library no longer leaves an out-of-scope selected document visible after a course/filter switch. Historical versions remain accessible only within the selected material family. Work links include pinned historical inputs.
- Original-file presence is checked from the actual IndexedDB file record rather than inferred from metadata alone.
- Browser is its own full workspace route. Its canvas and inspector no longer sit inside another workspace's canvas and inspector.
- A frame from another target is discarded; saved items and associated work are scoped to the selected bound page. Failed/frozen frames do not imply live progress.
- Opening the original browser is a validated, target-bound focus operation, separate from takeover and resume. It uses existing extension permissions.
- Shared typography uses readable contrast and a consistent hierarchy. These CSS changes still require browser visual comparison.

## Isolated reference

`reference.html` uses the same components with clearly labeled fixture data. It has links for schedule, workbench, library, sources, browser, takeover and project resources; catalog is reached from resources. `#takeover` and `#resources` demonstrate slide-6/7 states. The sample portal is HTML labeled “示例页面 · 非真实浏览器画面”; it is not a screenshot, an external connection, or proof of executed collection. The fixture does not write personal records or invoke services. Its curves are analytical layout examples, not user measurements.

## Verification boundary

Node checks cover host handlers/persistence, domain rules, module scope/version behavior, frame/control models, fixture navigation and the extension's target-bound actions. They do not check pixels. The supported `$control-browser` capability is unavailable in the managed environment; no substitute browser or preview server was used. Browser screenshots, native PDF sizing, visual collision/scroll review and Windows acceptance remain unverified.

This revision completes additional presentation components and host wiring; it is not full PPT visual acceptance, a finished Windows workstation or M1 acceptance. Keep the GitHub change Draft and independent of the active runtime stack.
