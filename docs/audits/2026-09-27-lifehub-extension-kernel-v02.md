# LifeHub v0.2 Extension Kernel audit — 2026-09-27

## Scope

This slice deliberately builds platform infrastructure rather than adding life-domain features.
The food, fitness and markets packages remain synthetic probes.

## Architectural change

LifeHub v0.1 was a pluginized dashboard: Core still owned a closed set of plugin kinds,
renderers and widget dimensions. v0.2 moves the durable boundary toward an extension host.

The kernel is now split into focused layers:

- `manifest.py` — versioned package contract and v0.1 compatibility adapter.
- `registry.py` — package discovery and arbitrary extension-point index.
- `store.py` — local persistence, workspace model and permission grants.
- `network.py` — retrieval-only egress broker.
- `kernel.py` — composition/root API.
- `core.py` — compatibility facade only.

## Open extension model

Manifest v1 uses contributions rather than a closed plugin-kind enum.

```toml
manifest_version = 1
api = "lifehub@1"

[[contributes]]
id = "today"
point = "workspace.widget"
entrypoint = "lifehub.primitive"
```

`point` is intentionally not validated against a Core-owned allowlist.
A test registers `future.capability.that-core-does-not-know` and queries it successfully.
This means adding a new extension point does not intrinsically require a LifeHub Core release.

Plugins are packages of contributions; they are not classified as one fixed domain/type.

## Capability broker

Storage permissions are now split into:

- `storage_write`
- `storage_read` (requested cross-plugin reads)

A plugin always retains access to namespaces it owns through `storage_write`.
A cross-plugin read requires both:

1. the plugin manifest requested a matching `storage_read` namespace; and
2. a local grant exists in `lifehub_permission_grants`.

The kernel exposes local grant/revoke operations and the CLI exposes:

```text
lifehub grants
lifehub grant-read <plugin> <namespace>
lifehub revoke-read <plugin> <namespace>
```

Tests verify deny-before-grant, allow-after-grant and deny-after-revoke behavior.
The kernel also refuses to grant a namespace the plugin did not request.

## Data egress policy

The network gateway remains retrieval-only:

- GET/HEAD only.
- request-body/upload methods denied.
- embedded URL credentials denied.
- arbitrary query strings denied in this early contract.
- external destinations require HTTPS and manifest allowlisting.
- localhost access requires an explicitly declared port.
- every authorization attempt is recorded locally.

This is a broker boundary for declarative/trusted integrations, not yet an OS sandbox for arbitrary executable code.

## Workspace model

Workspace persistence no longer stores `plugin_id + widget_id + position` as the primary abstraction.
It stores generic extension references:

```text
workspace_id
extension_ref
breakpoint
x / y / width / height
visible
config
```

The current web board consumes only the `workspace.widget` extension point.
That board is explicitly a temporary consumer, not the definition of the platform.
Other extension consumers can be built independently.

The workspace uses a 12-column coordinate model rather than the old 1–3 width/height cycle as a storage constraint.

## Compatibility

v0.1 manifests are upgraded at the package boundary to manifest v1.
Legacy `kind` and `widgets` are not retained as kernel concepts.
The three synthetic demo packages have been migrated to native manifest v1.

## Validation

Functional head: `cf12e7f3ecd74b3c22226fbc1db4b29687079386`

GitHub Actions:

- Python 3.11: PASS
- Python 3.12: PASS
- Ruff: PASS
- pytest: 105 passed

## What is still intentionally missing

LifeHub is not yet a Linux-like finished platform. The following are the next kernel problems, in priority order:

1. **Package installation/uninstallation** — secure local package format, archive hardening, versioning and dependency metadata.
2. **Extension runtime** — executable third-party code must not run inside the Core process; choose and enforce a real sandbox boundary.
3. **Activation/lifecycle** — lazy activation events, start/stop/crash semantics and health supervision.
4. **Extension-point contracts** — versioned host APIs and consumer/provider negotiation without a central type whitelist.
5. **Custom UI host** — sandboxed local frontend surface with message-based capabilities, rather than Core rendering every plugin.
6. **Command/search/settings buses** — Shell features should consume extension points instead of being hard-coded.
7. **Real board editor** — direct drag/resize, responsive breakpoints, nested sections and multiple workspaces.
8. **Package trust** — signing/hash provenance and local review before capability grants.

Only after the runtime/package boundary is trustworthy should real personal-data plugins be installed broadly.

## Platform invariants

These are intended to survive future UI and implementation rewrites:

1. Personal and derived data is local by default.
2. No plugin receives global data access by virtue of being installed.
3. Cross-plugin reads are requested and locally granted.
4. Outbound retrieval is mediated by the host.
5. Core does not own a closed list of life domains or extension points.
6. A new domain feature should arrive as a package without editing Core.
7. The Shell is replaceable; LifeHub is not synonymous with one dashboard.
8. Arbitrary third-party executable code stays disabled until isolation can enforce the privacy model.
