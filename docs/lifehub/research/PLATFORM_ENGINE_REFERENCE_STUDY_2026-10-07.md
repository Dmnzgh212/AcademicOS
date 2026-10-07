# LifeHub Platform Engine Reference Study — 2026-10-07

## Why this study exists

LifeHub must not become a Web application with a plugin API.

The target is a local, open personal-computing platform whose core can run without any
browser or UI shell. This study reviews mature open-source/runtime projects that already
solve adjacent problems so LifeHub can reuse sound design patterns instead of inventing
generic infrastructure badly.

The goal is not to copy one project wholesale. No single project has the exact LifeHub
goal. The useful approach is to learn one architectural lesson from each project and keep
the LifeHub-specific semantic layer separate.

---

# Executive conclusion

The strongest external references are:

1. **Fuchsia Component Framework** — component model, runners, resolvers, capability routing.
2. **Wasmtime + WebAssembly Component Model/WIT** — typed portable component ABI and host linking.
3. **systemd** — lifecycle supervision, dependency management, activation, readiness and recovery.
4. **VS Code Extension Host + Agent Host** — shell/runtime separation, lazy activation and persistent host/client protocol.
5. **XDG Desktop Portal / Flatpak** — mediated access to host resources and user-granted permissions.
6. **Deno** — runtime layering and permission checks at privileged host-operation boundaries.
7. **Kotlin K2 compiler** — practical compiler architecture with frontend IR, backend IR, diagnostics and multiple targets.

Useful secondary references:

8. **wasmCloud** — runtime import/export linking and provider abstraction.
9. **Extism** — simple host/guest Wasm embedding and host-function ergonomics.
10. **Nix** — package identity, immutable/content-addressed artifacts and reproducible dependency thinking.
11. **Dapr** — useful service invocation ideas, but its sidecar/microservice model is too network-centric for the LifeHub core.

The main architectural lesson is:

> LifeHub should not invent generic component execution, IPC, package identity,
> supervision or sandbox mediation from scratch. Its original work should concentrate
> on the person-oriented semantic layer: PersonalDomain, authority, provenance,
> proposal/commit, effect mediation and declassification.

---

# 1. Fuchsia Component Framework

Official references:

- https://fuchsia.dev/fuchsia-src/concepts/components/v2/introduction
- https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities
- https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities/runner
- https://fuchsia.dev/fuchsia-src/concepts/components/v2/environments

## What Fuchsia gets right

Fuchsia treats a **component** as the fundamental software unit.

A component declares:

- how it runs;
- which capabilities it provides;
- which capabilities it requires;
- which runner executes it;
- how its environment resolves and launches it.

Most importantly, a component does not gain arbitrary ambient access merely because it
exists. Capabilities must be routed.

Fuchsia also separates:

- **component manager** — framework-level orchestration;
- **runner** — runtime-specific execution;
- **resolver** — package/component URL resolution;
- **capability routing** — provider/consumer authority;
- **environment** — selects runners/resolvers for a realm.

This is extremely close to the architecture LifeHub needs.

## LifeHub lesson

The existing LifeHub `runner` field is directionally correct, but still too attached to
the old extension/contribution model.

LifeHub should evolve toward:

```text
Package
  |
  +-- Component declarations
  |     |
  |     +-- runner
  |     +-- provides
  |     +-- requires
  |     +-- activation
  |     +-- lifecycle policy
  |
  +-- interfaces
  +-- resources
  +-- package identity
```

The Engine should own resolution and capability binding.

A component should not choose a provider by opening a global service name or passing an
identity in a message.

## What NOT to copy

Do not copy Fuchsia's full realm hierarchy, FIDL stack, kernel handles, or OS-specific
component tree model.

LifeHub runs above Windows/Linux/macOS rather than replacing the host OS.

We need the **component-framework principles**, not a Fuchsia clone.

## Proposed LifeHub adoption

High priority.

Introduce a first-class `ComponentManifest` separate from UI extension contributions.

---

# 2. Wasmtime + WebAssembly Component Model + WIT

Official references:

- https://docs.wasmtime.dev/
- https://component-model.bytecodealliance.org/
- https://component-model.bytecodealliance.org/design/wit.html
- https://github.com/bytecodealliance/wasmtime

## What it gets right

Wasmtime's Component Model introduces a typed, portable component boundary.

Important concepts:

- components import and export interfaces;
- WIT defines typed interfaces/worlds;
- host bindings can be generated;
- a linker resolves imports;
- resource handles can cross component boundaries safely;
- current component-model work includes async/future/stream support.

This is stronger than inventing our own JSON RPC as the long-term universal ABI.

## LifeHub lesson

LifeHub should distinguish three layers:

```text
Interface definition
        |
        v
WIT / typed ABI
        |
        v
LifeHub authority + routing
        |
        v
actual provider binding
```

WIT can answer:

> What shape does this interface have?

LifeHub must answer:

> Who is allowed to call it?
> Which provider satisfies it?
> Under what package identity?
> Can the binding be revoked?
> What authority/provenance rules apply?

Do not mix these concerns.

## What NOT to copy

WIT does not define person-oriented behavior, authority policy, PersonalDomain semantics
or proposal/commit rules.

Therefore WIT is not a replacement for PersonIR.

## Proposed LifeHub adoption

Very high priority for Component IPC research.

Before inventing a new LifeHub wire schema, prototype one `provides/requires` route
using WIT-generated bindings or a WIT-shaped interface model.

---

# 3. systemd

Official references:

- https://systemd.io/
- https://systemd.io/ARCHITECTURE/
- https://systemd.io/FILE_DESCRIPTOR_STORE/
- systemd service/socket/watchdog manuals

## What systemd gets right

systemd is a mature long-lived service manager.

Important lessons:

- service lifecycle is owned by the manager, not by UI tools;
- clients use a control protocol, while the manager owns process state;
- activation can be on-demand;
- readiness is explicit;
- watchdogs distinguish "process exists" from "service is healthy";
- restart behavior is policy, not hardcoded behavior;
- dependencies form a managed graph;
- socket activation lets the manager own an endpoint before the service exists;
- state can survive or be transferred across service restarts in carefully designed ways.

## LifeHub lesson

LifeHub Supervisor should stop at neither:

```text
running / stopped
```

nor:

```text
restart=yes/no
```

It needs explicit concepts such as:

```text
desired_state
observed_state
readiness
health
activation_reason
restart_policy
restart_backoff
dependency_ready
last_failure
attempt_count
```

The Shell should only observe/control this state.

## Strong design lesson

A service being alive is not equivalent to being ready.

LifeHub should eventually distinguish:

```text
STARTING
READY
DEGRADED
STOPPING
FAILED
```

rather than only process-style lifecycle states.

## What NOT to copy

Do not reproduce systemd's enormous unit configuration language or Linux-specific cgroup,
namespace and fd-passing machinery at this stage.

## Proposed LifeHub adoption

High priority after Component Model and routing are stable.

---

# 4. VS Code Extension Host and Agent Host

Official references:

- https://code.visualstudio.com/api/advanced-topics/extension-host
- https://code.visualstudio.com/api/references/activation-events
- https://code.visualstudio.com/api/extension-capabilities/overview
- https://code.visualstudio.com/docs/agents/concepts/agent-host
- https://code.visualstudio.com/blogs/2026/08/26/agent-host-architecture

## Why this project is especially important for LifeHub

VS Code contains two architectural lessons from different generations.

### Extension Host

Extensions run outside the main UI process.

The extension system uses:

- contribution declarations;
- activation events;
- extension host processes;
- runtime/location selection;
- stable API boundaries;
- lazy loading.

Extensions are also prevented from directly mutating the editor DOM.

This preserves the freedom to change the UI independently.

### Agent Host

In 2026 VS Code went one step further for long-running agents.

Agent sessions used to be tied too closely to the extension host/editor window. VS Code
moved them into a dedicated **Agent Host** process with a host protocol. Clients connect
to the host, but sessions can continue independently.

This is directly relevant to LifeHub.

Our earlier Web-first mistake is analogous to tying durable runtime state to a UI host.

## LifeHub lesson

The desired relationship is:

```text
LifeHub Desktop ------+
LifeHub CLI ----------+----> LifeHub Engine
Future Mobile --------+
Third-party Shell ----+
```

The Engine owns long-lived component/session state.

A Shell connection must not define the component lifetime.

## Activation lesson

VS Code's activation-event model is worth adapting:

```text
manual
on_boot
on_interface_call
on_event
on_resource
on_schedule
```

But the activation declaration must be generic and Engine-owned.

## What NOT to copy

VS Code extensions historically have broad host permissions. The VS Code documentation
explicitly notes that normal Extension Host extensions may have the same operating-system
permissions as VS Code itself.

LifeHub must be stricter.

Our capability boundary should be closer to Fuchsia/Flatpak/Deno than classic VS Code
extensions.

## Proposed LifeHub adoption

Very high priority as an architectural reference for shell independence and activation.

---

# 5. XDG Desktop Portal + Flatpak

Official references:

- https://flatpak.github.io/xdg-desktop-portal/docs/
- https://github.com/flatpak/xdg-desktop-portal
- Flatpak sandbox permission documentation

## What it gets right

A sandboxed application should not need broad filesystem/device/system authority merely
to perform a useful user-mediated action.

Portals provide brokered interfaces such as:

- file selection;
- URI opening;
- printing;
- document access.

The portal can mediate a user's choice and then grant access to exactly the selected
resource.

This is much better than:

```text
app gets entire home directory
```

## LifeHub lesson

This maps naturally to future LifeHub Effects and declassification.

Instead of granting:

```text
filesystem.read = C:\Users\...
```

for an entire component, LifeHub may expose broker capabilities such as:

```text
person.file.choose
person.contact.choose
person.calendar.share
person.location.share
external.send
```

The Engine can return a narrow resource handle/value after approval.

## Permission-store lesson

Permissions should be host-owned and keyed by trusted application/component identity.

The UI that asks the user and the backend implementing a resource need not be the same
thing.

## What NOT to copy

Do not make every capability interactive.

LifeHub also needs durable delegated authority and noninteractive policy decisions.

## Proposed LifeHub adoption

Very high priority for future Effects/Declassification and host-resource access.

---

# 6. Deno

Official references:

- https://docs.deno.com/runtime/fundamentals/security/
- https://docs.deno.com/runtime/reference/permissions/
- https://github.com/denoland/deno/blob/main/doc/architecture.md

## What Deno gets right

Deno's source architecture is explicitly layered:

```text
CLI
runtime
extensions
core
V8/Tokio
```

Lower layers do not depend upward on CLI concerns.

That is exactly the rule LifeHub is now enforcing for Shell -> Engine.

Deno also enforces sensitive permissions at native host-operation boundaries.

JavaScript code cannot bypass a Rust permission check merely by constructing an object
that says it has authority.

## LifeHub lesson

Every privileged Engine operation should converge on a small set of host boundaries.

For example:

```text
Component call
     |
     v
Engine operation
     |
identity lookup
capability check
snapshot/package check
     |
privileged host action
```

The most important security checks should not be scattered throughout application logic.

## Resource-table lesson

Deno uses managed resource handles for native objects such as open files/sockets.

LifeHub may eventually need a generic host-managed resource-handle model for capabilities
that are more precise than service names.

## What NOT to copy

Deno's permissions are primarily process/runtime permissions. LifeHub needs richer
person-oriented authority, provenance and policy semantics.

## Proposed LifeHub adoption

High priority for runtime layering and privileged operation boundaries.

---

# 7. Kotlin K2 / FIR compiler

Official repository:

- https://github.com/JetBrains/kotlin

Relevant architecture:

- `compiler/fir/` — K2 frontend IR
- `compiler/ir/` — backend IR
- JVM/JS/Wasm/Native backends
- explicit compiler phases
- strong diagnostic infrastructure

## What Kotlin gets right

Kotlin is valuable to LifeHub for two different reasons.

### Developer experience

The language tries to minimize ceremony while retaining static analysis.

### Compiler architecture

K2/FIR separates frontend semantic resolution from backend IR.

A useful high-level lesson:

```text
Source
  |
Frontend IR
  |
semantic resolution/type analysis
  |
backend IR
  |
lowering
  |
target backend
```

This suggests LifeLang should probably not directly lower parser nodes into PersonIR
execution structures.

We may eventually need:

```text
LifeLang AST
     |
semantic frontend representation
     |
PersonIR
     |
target lowering
```

## Diagnostics lesson

Compiler usability depends as much on diagnostics as syntax.

If a LifeLang program violates authority rules, the compiler should explain:

- which value carries protected provenance;
- which operation requires authority;
- which authority is missing;
- where a declassification boundary is required.

A technically correct compiler with incomprehensible errors would fail the Kotlin-like
ergonomics requirement.

## What NOT to copy

Do not copy Kotlin syntax, nullable types, coroutines or JVM assumptions mechanically.

The reason to study Kotlin is compiler/product discipline, not syntax aesthetics.

## Proposed LifeHub adoption

Research now; implementation only after PersonIR semantics stabilize.

---

# 8. wasmCloud

Official references:

- https://wasmcloud.com/docs/v1/concepts/
- https://wasmcloud.com/docs/v1/concepts/linking-components/
- https://wasmcloud.com/docs/v1/concepts/providers/

## What it gets right

wasmCloud separates:

- portable Wasm components;
- reusable capability providers;
- imports/exports;
- runtime link definitions.

A component refers to an interface rather than hardcoding a provider.

This is strongly aligned with LifeHub's future `requires/provides` routing.

## Valuable LifeHub lesson

A component should declare:

```text
requires keyvalue/store
```

not:

```text
connect to RedisPlugin42
```

The Engine/operator chooses the binding.

That makes providers replaceable.

## Provider lesson

Long-lived resource providers and short-lived/stateless computational components may need
different lifecycle treatment.

LifeHub should not assume every component is the same kind of runtime workload.

## What NOT to copy

wasmCloud is optimized for distributed cloud/edge deployment and a network lattice.

LifeHub's first priority is a single-user local computer.

Do not import NATS, distributed discovery, scaling or cloud placement complexity unless a
real future requirement appears.

## Proposed LifeHub adoption

Strong conceptual reference for interface linking; avoid distributed machinery.

---

# 9. Extism

Official references:

- https://extism.org/
- https://github.com/extism/extism

## What it gets right

Extism solves a practical problem:

> How can a host safely embed third-party Wasm plugins and expose a small, controlled
> set of host functions?

Its Host Function model is easy to understand and its many host/guest SDKs show strong
developer ergonomics.

## LifeHub lesson

LifeHub SDK design should be significantly easier than raw Wasmtime embedding.

A developer should not have to understand Wasm memory plumbing to write a normal LifeHub
component.

There should eventually be ergonomic SDK abstractions around:

- input/output;
- service calls;
- records;
- effects;
- capabilities;
- runtime context.

## What NOT to copy

Extism is fundamentally an embedded plugin framework, not a full platform manager.

If LifeHub copied Extism's product model directly, we would return to:

```text
host application + plugins
```

instead of:

```text
platform + independent software
```

## Proposed LifeHub adoption

Use as SDK/embedding inspiration, not as the platform architecture.

---

# 10. Nix

Official references:

- https://github.com/NixOS/nix
- https://nixos.org/manual/nix/stable/

## What it gets right

Nix treats build inputs/outputs and immutable store identity as first-class concepts.

This is useful for LifeHub package integrity and reproducibility.

Relevant ideas:

- content-addressed/immutable artifacts;
- explicit inputs;
- stable artifact identity;
- reproducible resolution;
- old versions can coexist;
- rollback becomes possible because replacement is not destructive mutation.

## LifeHub lesson

The existing exact-digest package approval is a good foundation.

Future package metadata should distinguish:

```text
package logical identity
package version
package content digest
component digest
interface version
resolved dependency set
```

Capability grants should continue binding to immutable package identity where security
depends on exact code.

## What NOT to copy

Do not build a full Nix expression language or purely functional OS/package graph.

LifeHub only needs the package-identity and reproducibility lessons.

## Proposed LifeHub adoption

Medium priority during package-system refinement.

---

# 11. Dapr — useful partial reference

Official references:

- https://docs.dapr.io/concepts/dapr-services/sidecar/
- https://docs.dapr.io/developing-applications/building-blocks/service-invocation/

## Useful lesson

Dapr makes application code call stable platform building-block APIs rather than directly
embedding every infrastructure dependency.

Service identity and discovery are mediated by the sidecar/platform.

This is conceptually useful.

## Why it is NOT a primary LifeHub model

Dapr's architecture assumes distributed applications and commonly uses local HTTP/gRPC
sidecars.

For LifeHub, introducing a sidecar per component would likely add unnecessary:

- processes;
- networking;
- serialization;
- operational complexity.

LifeHub should first use a direct local Engine-managed component boundary.

## Proposed LifeHub adoption

Study service-discovery semantics only.

Do not adopt sidecar architecture by default.

---

# Cross-project synthesis

## Pattern A — UI must not own durable runtime

Seen in:

- VS Code Agent Host
- systemd
- Deno layering
- Fuchsia component manager

LifeHub rule:

```text
Shell disconnect != component death
```

---

## Pattern B — programs should depend on interfaces, not providers

Seen in:

- Fuchsia capability routing
- Wasm Component Model
- wasmCloud linking
- Dapr service invocation

LifeHub rule:

```text
requires interface X
        |
        v
Engine-authorized binding
        |
        v
provider Y
```

The consumer should not receive authority to choose arbitrary providers.

---

## Pattern C — privileged access is mediated at a host boundary

Seen in:

- Deno ops/permissions
- Flatpak portals
- Fuchsia capabilities
- Extism host functions

LifeHub rule:

```text
untrusted component
      |
      v
typed host boundary
      |
identity + authority check
      |
      v
resource/effect
```

---

## Pattern D — runtime and language are separate

Seen in:

- Fuchsia runners
- Wasmtime
- Kotlin multiplatform backends
- VS Code multiple extension hosts

LifeHub rule:

```text
Engine
 |
 +-- Wasm Runner
 +-- Person Runner
 +-- future runner
```

LifeLang must not become synonymous with LifeHub.

---

## Pattern E — package code identity must be stronger than a display name

Seen in:

- Nix
- Wasm artifact model
- existing LifeHub digest-bound grants

LifeHub rule:

Never authorize a component only because a message or manifest string claims a known
name.

Host-resolved package identity and exact code snapshot remain authoritative.

---

# Concrete design changes recommended for LifeHub

The following are now stronger candidates for the next Engine work.

## 1. Split executable components from extension contributions

Do not evolve `workspace.widget` into the new component system.

Add a dedicated component model.

Candidate conceptual manifest:

```toml
[[components]]
id = "worker"
runner = "lifehub.wasm"
activation = "on-demand"
restart = "on-failure"

provides = [
  "example.course-info@1"
]

requires = [
  "lifehub.records@1",
  "person.notifications@1"
]
```

Syntax is provisional.

The conceptual split is not.

---

## 2. Add an Engine-owned binding graph

The Engine needs an explicit structure roughly equivalent to:

```text
Requirement
  component=A
  interface=foo@1

Binding
  consumer=A
  interface=foo@1
  provider=B
  provider_package_digest=...
  grant_snapshot=...
```

Do not let the caller pass a provider identity in a request and have the Engine trust it.

---

## 3. Separate control plane from component data plane

Current `lifehub.engine-control@1` is for clients controlling the Engine.

Do not overload it as component IPC.

Create a separate conceptual boundary:

```text
Control plane:
Shell/CLI -> Engine

Data/service plane:
Component -> capability-bound interface -> Component/provider
```

This mirrors lessons from systemd, VS Code and component runtimes.

---

## 4. Add Engine environment/runtime selection

Fuchsia suggests a useful concept:

```text
Engine Environment
  |
  +-- available runners
  +-- resolvers
  +-- trusted host providers
  +-- default policy
```

LifeHub does not need Fuchsia realms now.

But the runner registry should eventually be part of explicit Engine configuration rather
than arbitrary package-controlled runtime installation.

---

## 5. Add lazy activation before always-on background execution

Borrow from VS Code and systemd.

A provider/component should be able to activate because:

- a required interface is first called;
- an event arrives;
- a schedule triggers;
- Engine starts;
- user explicitly starts it.

This avoids running every installed package forever.

---

## 6. Add readiness separate from running

Borrow from systemd.

A runner returning a process handle should not automatically mean the component is ready
to serve interface calls.

---

## 7. Keep permissions host-bound

Borrow from Deno/Fuchsia/Portal.

Every sensitive operation should derive caller identity from the Engine execution context.

Never from payload fields.

---

## 8. Investigate WIT before extending JSON service ABI

The current bounded JSON service ABI is useful as a prototype and compatibility layer.

Before making it the permanent component model, build one experimental WIT-based component
route.

Compare:

- type safety;
- language support;
- async support;
- resource handles;
- generated bindings;
- authorization integration;
- error quality.

---

## 9. Preserve LifeHub's own research frontier

None of the reviewed systems directly provides:

```text
PersonalDomain
Evidence
Derived state
Provenance
Person-rooted authority
Proposal -> Commit
Declassification
Effect semantics
```

That is where LifeHub/PersonIR research may still be distinctive.

Do not waste originality budget rebuilding generic component infrastructure that mature
projects already solve better.

---

# Proposed next experimental sequence

Do not implement all references at once.

Recommended order:

```text
Experiment A
Formal ComponentManifest separate from contributions
          |
Experiment B
provides/requires resolver + immutable binding
          |
Experiment C
two local components call through Engine-bound interface
          |
Experiment D
revoke binding -> next call fails
          |
Experiment E
on-demand activation of provider
          |
Experiment F
provider crashes -> supervisor/restart/readiness behavior
          |
Experiment G
same interface with Wasm provider and fake native/test provider
          |
Experiment H
prototype same interface using WIT/Component Model
```

Only after this should the project decide how much of the current JSON service path should
remain.

---

# Reference priority matrix

| Project | Primary lesson | LifeHub relevance | Copy level |
|---|---|---:|---|
| Fuchsia | components/runners/capability routing | Critical | architecture |
| Wasmtime/WIT | typed portable interfaces | Critical | reuse where possible |
| systemd | supervision/activation/readiness | Critical | semantics |
| VS Code Host architecture | UI independence/lazy activation | Critical | architecture |
| XDG Portal/Flatpak | mediated authority/resource access | Critical | security pattern |
| Deno | layered runtime/host-bound permission checks | High | runtime discipline |
| Kotlin K2 | compiler phases/diagnostics/tooling | High later | compiler discipline |
| wasmCloud | imports/exports/provider links | High | selected concepts |
| Extism | host/guest SDK ergonomics | Medium-high | developer UX |
| Nix | immutable package identity/reproducibility | Medium | package ideas |
| Dapr | service abstraction | Low-medium | concepts only |

---

# Final recommendation

The next major LifeHub design should be influenced primarily by this combination:

```text
Fuchsia
  component model
      +
Wasmtime/WIT
  portable typed ABI
      +
systemd
  supervision/activation
      +
VS Code Agent Host
  shell-independent persistent host
      +
Flatpak Portals + Deno
  mediated/default-deny authority
      +
LifeHub research
  PersonalDomain / PersonIR semantics
```

Kotlin should guide the future language/compiler **developer experience**, not the Engine
architecture.

This keeps the project open without making it shapeless:

- generic platform mechanics are learned or reused from mature systems;
- LifeHub-specific research remains focused on the relationship between software,
  authority and a person's persistent digital state.
