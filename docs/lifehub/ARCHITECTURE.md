# LifeHub Core v0.1 — historical architecture

This page records the initial implementation. For current platform contracts,
ownership boundaries and runnable examples, read [PLATFORM_STATUS.md](PLATFORM_STATUS.md).
The loopback web shell and widget model below are reference application choices,
not mandatory interfaces for every LifeHub shell.

LifeHub is an incubating local-first personal information platform. AcademicOS remains intact and can later become one LifeHub integration.

## Product rule

**Functionality is open; personal data is closed.**

The platform should make it cheap to add new capabilities without teaching the core what a cafeteria menu, workout, stock, course, server, trip or future domain means. Personal and derived data stays on the user's machine by default.

## v0.1 architecture

LifeHub Core currently owns only:

- plugin manifest discovery;
- local SQLite record retention;
- plugin-owned storage namespaces;
- workspace/widget registration and layout persistence;
- a loopback-only web shell;
- a retrieval-only, allowlisted outbound gateway with an audit ledger.

Declarative plugins live under `lifehub_plugins/<plugin>/plugin.toml`. Adding a new widget does not require modifying the LifeHub web shell.

A manifest declares:

```toml
id = "example.plugin"
name = "Example"
version = "0.1.0"
kind = ["connector", "widget"]

[permissions]
storage_write = ["example"]
network_hosts = ["data.example.org"]
localhost_ports = []

[[widgets]]
id = "today"
title = "Example today"
namespace = "example.today"
renderer = "list"
width = 1
height = 1
```

The core validates that a widget can only read a namespace owned by its plugin. The scoped store rejects writes outside that namespace.

## Data retention

Records are appended to local SQLite with content hashes. Repeated identical snapshots are deduplicated, while changed snapshots remain locally available as history.

Runtime databases are already excluded by repository `.gitignore` patterns (`data/`, `*.db`, `*.sqlite*`).

## Network / egress model

The host-owned `EgressGateway` is intentionally retrieval-oriented:

- only `GET` and `HEAD`;
- no request body API;
- no credentials embedded in URLs;
- no arbitrary query strings in v0.1;
- external traffic requires HTTPS;
- destination hosts must be declared in the plugin manifest;
- local services require an explicitly declared loopback port;
- every authorization attempt is written to the local network audit table.

This is a **host API boundary, not an operating-system sandbox**. v0.1 therefore does not execute arbitrary third-party Python plugin code. A malicious native Python extension could bypass an in-process gateway, so executable third-party plugins remain out of scope until a real sandbox boundary is selected (for example a capability-limited subprocess/WASM design).

For the same reason, v0.1 demo plugins are declaration + local seed data only.

A future connector contract may re-introduce query parameters only as reviewed public/static parameters constructed by Core (for example a date or ticker), rather than giving plugins arbitrary query-string construction. This is required before real connectors can preserve the closed-data rule without crippling normal retrieval APIs.

## Workspace

The default Workspace is intentionally generic. It renders WidgetSpecs discovered from plugins and knows no business-domain concepts. Widgets can be dragged to reorder and cycled through width/height settings; layout changes are stored locally.

No external JavaScript, fonts, telemetry or cloud account are required. The web shell binds only to loopback and uses a per-process token for layout mutation.

## Demo plugins

The repository includes three independent synthetic plugins solely to exercise the platform contract:

- `demo.food`
- `demo.fitness`
- `demo.markets`

They prove that unrelated features can enter the same Workspace without changing Core. Their data is synthetic and is not a claim about any current dining menu, workout prescription or market price.

## Commands

After updating the editable install:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[brightspace,mail]"
```

Inspect the platform:

```powershell
.\.venv\Scripts\lifehub.exe doctor
.\.venv\Scripts\lifehub.exe plugins
```

Run the isolated demo:

```powershell
.\.venv\Scripts\lifehub.exe demo --reset --serve
```

Then open `http://127.0.0.1:8844`.

## Next architecture slices

The next useful work should not add domain features to Core. It should add platform capability in this order:

1. declarative Connector contract with safe public request parameters and scheduling;
2. first real connector: uOttawa dining menu -> local records -> Food widget;
3. localhost Service Adapter contract for projects such as wger/OpenBB/FreshRSS;
4. AcademicOS adapter as a complex local service/plugin;
5. executable third-party plugin sandbox only after the capability/egress boundary can be enforced outside ordinary in-process Python.

### Egress transport boundary

The retrieval gateway disables automatic HTTP redirects (301/302/303/307/308).
A plugin must request a redirect destination separately through the gateway,
which rechecks package validity and destination policy before opening it.
This avoids applying initial-URL authorization to an unreviewed redirect target.
It does not provide DNS pinning or a complete SSRF/network isolation sandbox.
