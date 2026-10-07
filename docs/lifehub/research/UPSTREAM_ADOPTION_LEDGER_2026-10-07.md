# LifeHub Upstream Adoption Ledger — 2026-10-07

This file turns the platform-engine reference study into an engineering adoption map.

It deliberately distinguishes:

- **REUSE** — an upstream dependency/standard we can plausibly use directly;
- **SPIKE** — prototype before committing the architecture;
- **PATTERN** — learn the semantics/architecture, do not add the project as a dependency;
- **ADAPTER-LATER** — integrate only behind a LifeHub interface when the host OS requires it;
- **DO-NOT-ADOPT** — a tempting part that would add the wrong complexity.

Nothing in this ledger authorizes copying third-party source into the LifeHub repository.
Prefer upstream packages, generated bindings, standards, and thin adapters. Pin versions,
review licenses, and preserve attribution when an implementation dependency is actually added.

---

## Current upstream already used by LifeHub

### Wasmtime Python binding

Status: **REUSE — already present**

Repository: https://github.com/bytecodealliance/wasmtime-py  
Runtime project: https://github.com/bytecodealliance/wasmtime  
Documentation: https://docs.wasmtime.dev/

Current LifeHub packaging already declares:

```toml
wasm = ["wasmtime>=36,<37"]
```

Current purpose:

- bounded Wasm execution;
- host-controlled runtime;
- no implicit filesystem/network/WASI authority.

Next action:

- keep the existing bounded core-module path working;
- separately spike Component Model/WIT support;
- do not silently replace the proven v0.1 Wasm security boundary.

---

# Candidate reusable standards/tools

## WebAssembly Component Model + WIT

Status: **SPIKE, then likely REUSE**

References:

- https://component-model.bytecodealliance.org/
- https://component-model.bytecodealliance.org/design/wit.html
- https://github.com/WebAssembly/component-model
- https://github.com/bytecodealliance/wasm-tools
- https://github.com/bytecodealliance/wit-bindgen

Candidate LifeHub use:

- typed component interfaces;
- imports/exports;
- generated guest/host bindings;
- resources;
- future async/stream interfaces;
- language-neutral component contracts.

Boundary:

WIT defines interface shape. LifeHub still owns:

- caller identity;
- capability/authority checks;
- provider selection;
- package digest binding;
- revocation;
- policy;
- provenance;
- effect/declassification rules.

Experiment gate:

Implement the same tiny interface twice:

1. current bounded JSON service ABI;
2. WIT/Component Model.

Compare ergonomics, type safety, generated bindings, error quality, resource limits,
authorization integration, startup cost, and Python-host feasibility before choosing a
long-term ABI.

Do not add new production dependencies merely to make the spike possible on main.

---

## WASI

Status: **SPIKE / selectively REUSE**

References:

- https://wasi.dev/
- https://github.com/WebAssembly/WASI

Candidate LifeHub use:

Standard interfaces may be preferable to inventing LifeHub-specific low-level interfaces
for clocks, random values, streams, sockets, files or CLI-like resources.

Security rule:

Never enable broad WASI merely because a runner supports it. A LifeHub component receives
only the resources/capabilities that the Engine intentionally binds.

LifeHub authority remains above WASI.

---

# Architecture references — learn, do not vendor

## Fuchsia Component Framework

Status: **PATTERN**

References:

- https://fuchsia.dev/fuchsia-src/concepts/components/v2/introduction
- https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities
- https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities/runner
- https://fuchsia.dev/fuchsia-src/concepts/components/v2/environments
- https://fuchsia.googlesource.com/fuchsia/

Adopt concepts:

- first-class Component;
- Runner;
- Resolver;
- capability routing;
- provider/consumer declarations;
- environment-controlled runtime availability.

Do not adopt:

- Fuchsia kernel assumptions;
- full realm hierarchy now;
- FIDL as a second competing interface language;
- OS-specific handle model.

LifeHub target module inspired by this work:

```text
lifehub/component.py
lifehub/binding.py
lifehub/runners/
lifehub/resolution.py
```

These are LifeHub modules, not copied Fuchsia code.

---

## systemd

Status: **PATTERN**

References:

- https://systemd.io/
- https://systemd.io/ARCHITECTURE/
- https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
- https://www.freedesktop.org/software/systemd/man/latest/systemd.socket.html

Adopt semantics:

- desired vs observed state;
- activation;
- readiness distinct from process existence;
- restart policy;
- restart backoff;
- watchdog/health;
- dependency readiness;
- manager-owned lifecycle.

Do not adopt:

- Linux-only unit implementation;
- cgroups as a cross-platform assumption;
- systemd configuration language;
- socket activation as the only activation model.

LifeHub target:

```text
lifehub/supervisor.py
```

must remain cross-platform and runner-neutral.

---

## VS Code Extension Host / Agent Host

Status: **PATTERN**

References:

- https://code.visualstudio.com/api/advanced-topics/extension-host
- https://code.visualstudio.com/api/references/activation-events
- https://code.visualstudio.com/docs/agents/concepts/agent-host
- https://github.com/microsoft/vscode

Adopt concepts:

- UI client lifetime is separate from host/session lifetime;
- lazy/event activation;
- protocol boundary between UI and host;
- extension/runtime location is selected by the platform.

Do not adopt:

- classic VS Code extensions' broad ambient OS authority;
- editor-centric contribution points as the LifeHub component model;
- Node.js as a mandatory LifeHub runtime.

---

## Deno

Status: **PATTERN**

References:

- https://github.com/denoland/deno
- https://docs.deno.com/runtime/fundamentals/security/
- https://docs.deno.com/runtime/reference/permissions/

Adopt concepts:

- strict dependency layering;
- permission enforcement at privileged native/host boundaries;
- host-managed resource handles/table;
- no trust in authority claims inside guest payloads.

Do not adopt:

- JavaScript/TypeScript as the mandatory component language;
- Deno's exact process permission model as the complete LifeHub authority model.

Potential LifeHub target abstraction:

```text
ResourceHandle<T>
ResourceTable
HostOperationContext {
    component_identity
    package_digest
    active_binding
    grants
}
```

This is a design candidate, not yet an approved API.

---

# Host-resource brokers

## XDG Desktop Portal / Flatpak

Status: **PATTERN on all OSes; ADAPTER-LATER on Linux**

References:

- https://flatpak.github.io/xdg-desktop-portal/docs/
- https://github.com/flatpak/xdg-desktop-portal
- https://docs.flatpak.org/en/latest/sandbox-permissions.html

Adopt concepts:

- broker privileged host access;
- user-mediated narrow grants;
- return a selected resource/handle rather than broad ambient authority;
- host-owned permission store.

Possible future LifeHub interfaces:

```text
person.file.choose
person.directory.choose
person.contact.choose
person.location.share
external.open-uri
external.send
```

Do not expose XDG Portal directly as the cross-platform LifeHub API.

Instead:

```text
LifeHub Resource Broker interface
       |
       +-- Linux portal adapter
       +-- Windows adapter
       +-- macOS adapter
```

No portal dependency should enter the Engine core.

---

# Linking/provider references

## wasmCloud

Status: **PATTERN; possible WIT interoperability later**

References:

- https://github.com/wasmCloud/wasmCloud
- https://wasmcloud.com/docs/
- https://wasmcloud.com/docs/concepts/linking-components/

Adopt concepts:

- component imports/exports;
- provider abstraction;
- runtime-selected links;
- consumer depends on an interface, not a concrete provider.

Do not adopt:

- NATS lattice;
- distributed placement/scaling machinery;
- cloud orchestration as a local Engine prerequisite.

LifeHub remains local-first.

---

## Extism

Status: **SDK PATTERN; optional SPIKE**

References:

- https://github.com/extism/extism
- https://extism.org/docs/concepts/host-functions/

Adopt concepts:

- ergonomic host functions;
- simple guest SDK;
- hide raw Wasm memory plumbing from normal developers;
- multiple guest-language SDK experience.

Do not adopt:

- "one host application + plugins" as the LifeHub architecture.

LifeHub SDK may learn from Extism even if LifeHub never depends on Extism.

---

# Package identity/reproducibility

## Nix

Status: **PATTERN**

References:

- https://github.com/NixOS/nix
- https://nix.dev/
- https://nixos.org/manual/nix/stable/

Adopt concepts:

- immutable artifact identity;
- explicit dependency inputs;
- reproducible resolution;
- coexistence of versions;
- rollback-friendly installation.

LifeHub should retain and extend its current exact-digest approval model.

Candidate package identity tuple:

```text
logical package id
version
content digest
component id
component/code digest
interface version
resolved dependency/binding snapshot
```

Do not adopt:

- Nix expression language;
- Nix store layout as a LifeHub requirement;
- NixOS assumptions.

---

# Compiler/language references

## Kotlin K2 / FIR / IR

Status: **PATTERN now; implementation reference later**

References:

- https://github.com/JetBrains/kotlin
- https://kotlinlang.org/docs/k2-compiler-migration-guide.html

Adopt concepts:

- semantic frontend IR;
- explicit compiler phases;
- diagnostics as a first-class product;
- separate backend IR/lowering;
- multiple backend discipline;
- IDE/tooling integration.

Potential LifeLang pipeline:

```text
.life source
    |
parser / AST
    |
semantic frontend representation
    |
PersonIR
    |
verification / authority analysis
    |
lowering
    |
Person Runner and/or Wasm component target
```

Do not adopt:

- Kotlin syntax by imitation;
- JVM assumptions;
- Kotlin type-system features without a LifeHub semantic need.

No Kotlin compiler dependency belongs in LifeHub Engine.

---

# Service invocation reference

## Dapr

Status: **PATTERN ONLY / DO-NOT-ADOPT sidecar architecture by default**

References:

- https://github.com/dapr/dapr
- https://docs.dapr.io/concepts/dapr-services/sidecar/
- https://docs.dapr.io/developing-applications/building-blocks/service-invocation/

Study:

- stable service invocation API;
- service identity/discovery;
- platform-provided building blocks.

Do not adopt now:

- one sidecar per component;
- HTTP/gRPC as the mandatory local component data plane;
- distributed microservice assumptions.

---

# Concrete dependency policy

## Allowed immediately

Keep the already-reviewed Wasmtime Python dependency at the currently bounded version
range until a deliberate runtime upgrade PR changes it.

## Experiment-only candidates

The following may be used in isolated spikes/branches after license and platform checks:

- WebAssembly Component Model/WIT toolchain;
- wasm-tools;
- wit-bindgen;
- WASI interfaces/tooling;
- Extism SDK for an ergonomics comparison.

An experiment does not automatically justify a production dependency.

## Architecture-only references

Do not add these as LifeHub dependencies merely because we study them:

- Fuchsia;
- systemd;
- VS Code;
- Deno;
- Flatpak/XDG Portal;
- wasmCloud;
- Nix;
- Kotlin compiler;
- Dapr.

Their value is architectural unless a later host adapter or toolchain integration has a
specific reason to depend on them.

---

# Proposed upstream-facing LifeHub interfaces

To avoid locking Core to a particular upstream implementation, use LifeHub-owned narrow
interfaces around replaceable machinery.

```text
Runner
  resolve(component) -> execution plan
  start(plan, context) -> instance
  stop(instance)

InterfaceResolver
  resolve(requirement, consumer_identity) -> candidate binding

BindingAuthority
  authorize(consumer, provider, interface) -> binding snapshot
  revoke(binding)

ResourceBroker
  request(component, resource_request) -> bounded handle/value

Supervisor
  activate(component, reason)
  observe(instance)
  stop(component)
  recover(interrupted_state)

PackageResolver
  resolve(package requirement) -> immutable package snapshot
```

These names and signatures remain provisional until the next Component Model spike.

---

# Anti-vendoring rule

Do not copy upstream source files into `src/academicos/lifehub` simply because a project
contains useful code.

Before vendoring any upstream code, require all of:

1. a concrete functionality gap that a normal dependency/standard/adapter cannot solve;
2. compatible license and preserved notices;
3. a documented update/security-maintenance strategy;
4. tests proving the vendored boundary;
5. architecture review showing that the copy does not couple LifeHub Core to one host OS
   or one UI/runtime.

Default choice: **depend, generate, adapt, or learn — do not copy.**

---

# Next module experiment

The first new production-facing module should be LifeHub's own Component Model, not an
imported framework.

Recommended initial files:

```text
src/academicos/lifehub/component.py
src/academicos/lifehub/binding.py
tests/test_lifehub_component_model.py
tests/test_lifehub_binding_authority.py
```

First acceptance chain:

```text
Package A / component consumer
        |
        | requires example.echo@1
        v
Engine resolver
        |
        | host-bound consumer identity
        | exact provider package digest
        | approved binding
        v
Package B / component provider
        |
        | provides example.echo@1
        v
call succeeds

revoke binding

same consumer -> same interface -> denied immediately
```

No Web Shell, browser, workspace, widget or AcademicOS domain object may participate in
this test.
