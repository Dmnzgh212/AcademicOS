# LifeHub open-platform research — 2026-09-27

## Why v0.1 still feels closed

The current LifeHub prototype proves local plugin discovery and local data retention, but it is still a pluginized dashboard rather than an open platform.

Current constraints in Core/UI include:

- `WidgetSpec.renderer` is hard-coded to `list`, `metric`, `text`, or `table`.
- widget width/height are hard-coded to integer values 1–3.
- the shell owns a fixed three-column grid and permanent sidebar.
- `web.py` owns the visual implementation of all widget renderers through `_format_payload()`.
- plugin `kind` is constrained to four fixed values.
- a widget can only read a namespace that its own plugin owns; there is no user-authorized cross-plugin composition model.
- there are no extension points for pages, commands, navigation, search, settings, themes, actions, background jobs, contextual menus, or custom renderers.

That is not analogous to Linux. It is closer to a configurable dashboard with plugin-supplied data.

## Systems studied

### Home Assistant frontend / Lovelace

Relevant source:

- `home-assistant/frontend/src/panels/lovelace/create-element/create-element-base.ts`
- `home-assistant/frontend/src/panels/lovelace/create-element/create-card-element.ts`

What matters:

- built-in cards can be lazy-loaded, but custom cards are not limited to the built-in renderer list.
- a custom card uses the `custom:` type prefix and resolves to a browser Custom Element.
- the core waits for `customElements.whenDefined(tag)` and then rebuilds/upgrades the element.
- custom cards can provide their own configuration editor.
- Home Assistant also supports custom views, panels, card features, and dashboard strategies.

Lesson for LifeHub:

**The shell should host arbitrary extension surfaces, not decide how every extension renders.**

A LifeHub plugin should be able to contribute a fully custom visual element through a host API, not be translated into one of four renderer types by Core.

### Backstage

Relevant source:

- `backstage/backstage/packages/frontend-plugin-api/src/wiring/createFrontendPlugin.ts`
- Backstage frontend/backend extension architecture docs.

What matters:

- the application itself is primarily wiring.
- plugins provide a collection of extensions.
- extensions form an application extension tree.
- plugins can expose pages, navigation, APIs and extension points.
- integrations can override existing extensions or attach new extensions at defined points.
- backend plugins are isolated units and communicate through explicit interfaces rather than importing each other's implementation.

Lesson for LifeHub:

**Plugin is not a domain type; plugin is a package of contributions.**

The manifest should not say `kind = ["widget", "connector"]` as the primary architecture. It should declare what the package *contributes* to extension points.

### Grafana

Relevant source:

- `grafana/grafana/pkg/plugins/storage/fs.go`
- Grafana plugin anatomy / plugin.json documentation.

What matters:

- plugins are discovered as packages rather than compiled into one central widget registry.
- `plugin.json` describes the plugin package and capabilities.
- plugin types include panels, data sources and full applications.
- app plugins can expose UI extensions into other parts of Grafana.
- plugin archives are treated as untrusted filesystem input: Grafana includes path traversal and symlink escape protections during extraction.

Lesson for LifeHub:

**Installable packages and a versioned manifest need to be first-class.**

Core should scan/install packages and load their declared entry points. Adding a plugin must not require editing a Core registry.

### VS Code / Code OSS

Relevant concepts/source:

- extension `package.json` contribution points.
- activation events.
- Extension Host process.
- Webview / Custom Editor APIs.

What matters:

- extensions statically contribute commands, views, menus, configuration, custom editors, themes, languages and more.
- activation is lazy: an extension can remain unloaded until a command/view/resource actually needs it.
- arbitrary custom UI can run inside a webview and communicate with the extension via message passing.
- extension code runs in an Extension Host rather than directly inside the UI process.

Lesson for LifeHub:

**Use contribution points + lazy activation + a separate extension runtime.**

This is much closer to the “Linux-like” feeling than loading Python modules into the same process.

### Homarr

Relevant source:

- `homarr-labs/homarr/apps/nextjs/src/components/board/sections/gridstack/*`
- `homarr-labs/homarr/packages/widgets/src/manifest.ts`

What it does very well:

- real drag/resize via GridStack rather than fake reorder + width buttons.
- explicit edit mode vs view mode.
- exact x/y/w/h placement.
- responsive layouts with independent breakpoint positions.
- nested sections / containers.
- board-level appearance, background and custom CSS.
- good direct manipulation UX.

What **not** to copy:

Homarr's built-in widget code still has a central typed widget registry in `packages/widgets/src/manifest.ts` with explicit imports/loaders for every widget kind. That is excellent for product maintainability but not open enough for the LifeHub goal.

Lesson for LifeHub:

**Borrow Homarr's board UX, not its central widget registry.**

## Target architecture: LifeHub as an extension host

LifeHub should be reduced to four durable responsibilities:

1. **Extension host** — discover/install/activate packages.
2. **Capability broker** — mediate storage, data reads, scheduling, network retrieval, secrets and local-service access.
3. **Workspace shell** — provide canvases and extension attachment points without owning domain UI.
4. **Privacy boundary** — personal/derived data cannot leave except through narrowly reviewed retrieval contracts.

Everything else should be contributed.

## New manifest direction

Instead of:

```toml
kind = ["connector", "widget"]
renderer = "list"
```

move toward a VS Code / Backstage style contribution model:

```toml
manifest_version = 1
id = "uottawa.dining"
name = "uOttawa Dining"
version = "0.1.0"
api = "lifehub@1"

[permissions]
storage_write = ["dining"]
storage_read = ["dining"]
network_retrieval = ["foodservices.uottawa.ca"]

[contributes]
commands = ["dining.refresh"]
views = ["dining.full"]
widgets = ["dining.today", "dining.compact"]
search_providers = ["dining.search"]
background_jobs = ["dining.refreshDaily"]
```

The identifiers above should map to extension definitions supplied by the plugin package, not to renderer names hard-coded in Core.

## UI contribution model

Support two tiers.

### Tier A — declarative primitives

For simple and safe plugins:

- text
- list
- metric
- table
- chart
- image
- markdown
- action button
- composition/container

These are convenience components, not the limit of the platform.

### Tier B — custom extension surface

For arbitrary UI:

- plugin ships a local frontend bundle.
- Core loads it into a sandboxed webview/iframe/custom-element host.
- communication occurs through a versioned message API.
- plugin UI never receives direct SQLite/filesystem access.
- plugin UI requests capabilities from the broker.

This follows the strongest parts of Home Assistant custom elements and VS Code webviews while keeping LifeHub's privacy model.

## Workspace redesign

The current permanent sidebar + three equal cards should be replaced by a real board system.

Borrow from Homarr:

- explicit Edit mode.
- 12-column (or configurable) grid.
- drag handles and native resize handles.
- stored x/y/w/h rather than ordered list + width/height cycle buttons.
- independent mobile/tablet/desktop layouts.
- containers/sections that can nest widgets.
- multiple workspaces/boards.
- direct Add content menu.
- widget context menu instead of controls permanently visible.

LifeHub-specific additions:

- an empty workspace can truly be empty.
- navigation itself can be contributed or user-created.
- a command palette can launch plugin commands without a permanent sidebar.
- themes and shell appearance should be extension/configuration points.
- workspaces can mix contributions from many plugins.

## Data / cross-plugin model

The current rule “a widget may only read the namespace it owns” is safe but prevents useful composition.

Replace it with separate permissions:

```text
storage.write: dining.*
storage.read: dining.*
```

and allow a plugin to request another namespace:

```text
storage.read: academic.deadlines
```

The request must be approved by the user and recorded locally.

This enables legitimate cross-domain plugins such as:

- weather + calendar commute suggestions.
- sleep + fitness recommendation.
- academic workload + schedule planning.

without making all data globally visible.

## Runtime / sandbox direction

Do not load arbitrary third-party Python into the Core process.

Preferred direction:

```text
LifeHub UI
   │
   ├── Extension Frontend Host (sandboxed webview)
   │
   └── Capability Broker
          │
          ├── Local Store
          ├── Retrieval Gateway
          ├── Scheduler
          ├── Secrets
          └── Extension Runtime
                 │
                 └── isolated process / WASM
```

The final executable extension runtime should be selected only after confirming that it can enforce the no-egress rule. Ordinary subprocess separation alone is not enough if the child process still has unrestricted network/filesystem access.

## Design direction

The current screenshot feels like an admin dashboard because:

- all modules share one identical card chrome.
- the sidebar consumes permanent space even though most content does not need navigation.
- resize controls are always visible.
- whitespace is large but hierarchy is weak.
- every card uses the same density and structure.
- the workspace does not visually communicate that it is editable.

The redesign should use:

- content-first canvas.
- compact top command/search bar rather than a permanent large sidebar.
- neutral background and stronger type hierarchy.
- card chrome that appears mainly in Edit mode.
- direct resize handles.
- varied extension surfaces: cards, full-bleed charts, lists, timelines, images, mini-panels, full pages.
- optional board background/theme tokens rather than one fixed product style.

The goal is not to imitate one product's appearance. The goal is to make LifeHub look like a **host for applications**, not a dashboard template.

## What to borrow / avoid

| Project | Borrow | Avoid |
|---|---|---|
| Home Assistant | custom elements, cards/views/panels, config editors | exposing plugin UI directly to all global state |
| Backstage | extension tree, extension points, overrides, plugin package separation | enterprise-specific concepts |
| Grafana | installable packages, manifest scanning, app/panel/data-source split, archive hardening | unrestricted datasource assumptions |
| VS Code | contribution points, lazy activation, extension host, webview message boundary | broad filesystem/network trust model |
| Homarr | GridStack UX, edit mode, responsive board layouts, nested sections | central hard-coded widget registry |

## Decision for LifeHub v0.2

Do **not** add dining, fitness, news or finance features to the current renderer architecture yet.

First replace the platform boundary:

1. contribution-based manifest v1;
2. extension registry + extension points;
3. real board model with x/y/w/h and responsive layouts;
4. Edit mode + Add-content palette + command palette;
5. custom extension surface contract;
6. separate read/write permissions and user-granted cross-plugin reads;
7. later: isolated executable extension runtime.

Only after those foundations exist should the first real feature, uOttawa Dining, be implemented. The dining plugin should be able to arrive without modifying Core or the shell.