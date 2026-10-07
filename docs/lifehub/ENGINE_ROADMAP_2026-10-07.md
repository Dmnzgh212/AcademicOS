# LifeHub Engine Roadmap — 2026-10-07

## Purpose

LifeHub is being built as an **open personal computing platform engine**.

It is not a website, dashboard, calendar, widget framework, or AcademicOS rewrite.

The platform should remain useful if every optional UI shell is deleted.

Core product direction:

> Open like Linux/Android, engine-oriented like browser/component runtimes, with a
> future internal language that aims for Kotlin-like developer ergonomics.

The engine is the priority. UI is a client of the engine.

---

## Current baseline

LifeHub v0.1 platform prototype is already in main.

The current post-v0.1 Engine track is a stacked series of Draft PRs:

- #35 — shell-independent Engine foundation
- #36 — execution supervisor and recovery
- #37 — authenticated local engine control plane
- #38 — persistent local Engine daemon
- #39 — isolate optional Web shell from the platform path
- #40 — move workspace presentation persistence out of the platform store

Important direction change:

The old reference Web shell is now legacy/optional presentation. It must never define
the LifeHub platform architecture.

---

## Non-negotiable architecture rule

Dependency direction is one-way:

```text
Desktop / CLI / Web / Mobile / Third-party shells
                      |
                      v
                LifeHub Engine
                      |
        runtime / packages / IPC / state
                      |
                Host operating system
```

The reverse dependency is forbidden.

Engine/runtime/package/capability/storage code must not depend on:

- HTML
- CSS
- browser state
- workspace layout
- widget rendering
- http.server
- a specific shell

A shell may depend on Engine contracts.

The Engine may not depend on shell concepts.

---

## Platform acceptance principle

For every new abstraction ask:

> Can a third party build something we did not anticipate without modifying LifeHub Core?

The platform model must be able to support software such as:

- IDEs
- compilers
- databases
- music players
- background services
- AI agents
- robotics/control software
- connectors
- shells
- domain applications

If the model only naturally explains cards, widgets, courses, food, markets, tasks, or
other preselected product domains, the abstraction is too narrow.

---

# Phase 1 — Finish the engine/shell separation

Status: **in progress**

Goals:

- keep the reference Web shell entirely optional;
- keep its persistence and layout schema outside the platform store;
- preserve compatibility only through shims/migrations;
- ensure normal Engine imports do not load Web modules;
- ensure a clean Engine database contains no widget/workspace tables.

Required test:

```text
no browser
no Web shell import
      |
start Engine
      |
discover package
      |
run component
      |
IPC / capability checks
      |
stop component
      |
PASS
```

Do not add new Web features during this phase.

---

# Phase 2 — Formal Component Model

The current `contributes + runner` design is transitional.

Executable components must become first-class platform concepts, separate from
presentation extensions.

Target concepts:

```text
Package
├── Components
├── Interfaces
├── Capabilities
└── Resources
```

A component should eventually describe at least:

- component id
- runner
- contract/interfaces
- provided interfaces
- required interfaces
- activation policy
- restart policy
- lifecycle
- package identity
- package digest

Do not hardcode product-domain component types such as course, fitness, finance, or
calendar into the Engine.

---

# Phase 3 — Capability and dependency routing

Move from manually connecting software to Engine-mediated routing.

Target model:

```text
Consumer component
      |
      | requires interface X
      v
Capability / Service Router
      |
      | approved binding
      v
Provider component
```

Requirements:

- deny before grant/binding;
- package identity is host-bound;
- package updates invalidate stale bindings;
- revocation takes effect immediately;
- a component cannot manufacture authority through message payloads;
- no ambient access to arbitrary global services.

Reuse the strongest v0.1 service-grant and digest-binding ideas instead of replacing
them with weaker generic plumbing.

---

# Phase 4 — Engine-native component IPC

The current control plane handles Shell/CLI -> Engine.

The platform also needs Component -> Component communication.

Required semantics:

- typed/versioned interfaces
- request/response
- async events
- streams where justified
- timeout
- cancellation
- caller identity binding
- capability check on every boundary
- backpressure/resource limits
- fail-closed behavior when provider identity changes

Study and reuse WIT / WebAssembly Component Model where it solves generic interface
problems.

Do not invent a new serialization format merely to appear original.

---

# Phase 5 — Background runtime and supervision

Build a real component supervisor, not a collection of one-shot function calls.

Target lifecycle features:

- manual activation
- on-demand activation
- event activation
- boot activation
- health state
- graceful shutdown
- crash limits
- restart policy
- exponential/backoff behavior
- dependency readiness
- resource accounting

Current states already include:

```text
running
completed
stopped
failed
interrupted
```

Keep crash recovery explicit. Never pretend in-memory runner handles survive process
death.

---

# Phase 6 — Package system as software delivery

A LifeHub package is not a widget bundle.

Target lifecycle:

```text
fetch
inspect
review
verify
install
resolve
activate
update
rollback
uninstall
```

Future package contents may include:

- components
- Wasm
- PersonIR
- interface definitions
- resources
- migrations
- metadata
- signatures

Continue to preserve digest-bound review/install semantics.

Later research areas:

- signatures
- publisher identity
- dependency locking
- reproducible packages
- package registries

---

# Phase 7 — PersonalDomain semantic layer

This is where LifeHub may become meaningfully different from conventional component
platforms.

Do not assume apps own the person's persistent digital state.

Candidate domain:

```text
PersonalDomain<P>
├── Evidence / Observations
├── Mainline accepted state
├── Derived state
├── Authority / delegation
├── Policy
├── Provenance
└── History / receipts
```

Third-party software should operate on bounded views and produce:

- derived information
- proposals
- effect requests

It should not automatically receive arbitrary durable mutation authority.

Working principle:

> Software proposes. Person-rooted authority commits.

Important nuance:

Observed external facts such as an email arrival, a weather reading, or a transaction
can be recorded as evidence without pretending the user "approved" their existence.

---

# Phase 8 — PersonIR v0

PersonIR research is reopened, but a source language must not be designed first.

Start from IR semantics.

Candidate first-class operations:

- Observe
- ReadView
- Transform
- Derive
- Propose
- RequestEffect
- Declassify
- Emit

IR edges/values may need metadata for:

- schema
- provenance
- confidentiality
- integrity
- purpose
- authority requirements

`Commit` should not be an ordinary untrusted program instruction. It belongs at the
runtime/authority boundary.

PersonIR must earn its existence by making important properties more explicit,
verifiable, or simpler than conventional Wasm + host-policy code.

---

# Phase 9 — Person Runner

PersonIR must fit the same platform instead of becoming another parallel platform.

Target:

```text
LifeHub Engine
      |
Runner Registry
      |
+--------------------+
|                    |
lifehub.wasm     lifehub.person
|                    |
Wasm               PersonIR
```

The Engine remains multi-runtime.

---

# Phase 10 — LifeLang compiler prototype

Only after PersonIR semantics survive real scenarios.

Working language name: **LifeLang**.

The language should learn from Kotlin's developer experience rather than copy Kotlin
syntax.

Design goals:

- concise
- readable
- statically analyzable
- strong diagnostics
- useful type inference
- safe defaults
- low ceremony
- good interoperability
- IDE/tooling friendliness

The developer should not manually write low-level IR concepts such as provenance
nodes or authority edges.

Desired compiler pipeline:

```text
.life source
   |
parser / AST
   |
semantic analysis
   |
PersonIR
   |
verifier
   |
capability/effect/provenance derivation
   |
Person Runner and/or Wasm/WIT target
```

Do not freeze syntax before the semantics are validated.

---

# Phase 11 — SDK and developer experience

A platform is not complete merely because its runtime works.

Provide:

- package scaffolding
- component/interface definitions
- capability declarations
- local testing harness
- package build/review tools
- diagnostic output
- debugger/tracing hooks
- documentation for third-party developers

The third-party developer path should not require reading Engine internals.

---

# Phase 12 — Independent shells

Only after the Engine and SDK contracts are stable enough.

Possible clients:

- Desktop Shell
- CLI Shell
- Mobile Shell
- reference Web Shell
- third-party shells

No shell is privileged as the definition of LifeHub.

A shell is the face.

The Engine is the platform.

---

# AcademicOS boundary

AcademicOS must stop acting as the conceptual parent of LifeHub.

Long-term target:

```text
LifeHub Platform
├── Academic Suite
├── Home Automation
├── Notes
├── AI Agents
├── Finance
├── Robotics
└── arbitrary third-party software
```

Existing AcademicOS code may be preserved and migrated gradually, but it must not
dictate LifeHub Engine abstractions.

---

# Anti-regression rules

Do not allow the project to drift back into:

- dashboard-first architecture
- calendar/todo product architecture
- widget framework
- AI chat page
- Web application as platform
- AcademicOS 2.0

Do not change Engine abstractions merely because a page needs something.

Engine changes require a platform reason such as:

- generic lifecycle need
- capability/authority issue
- component interoperability
- package/runtime problem
- state/security invariant
- repeated requirement across unrelated software

---

# Validation discipline

Each coherent slice should:

1. open a Draft PR;
2. run Ruff;
3. run full pytest;
4. build/install wheel;
5. run installed-wheel smoke;
6. preserve fail-closed security behavior;
7. avoid merging until cumulative architecture review is clean.

Every 2–4 Engine PRs, perform a cumulative architecture audit.

Tests being green proves implementation consistency, not architectural correctness.

---

# Next execution order

Strict priority:

```text
1. Finish Web/Shell separation
2. Finish presentation-state extraction
3. Formal Component Model
4. provides/requires capability routing
5. Engine component IPC
6. background/supervisor semantics
7. package-system refinement
8. PersonalDomain
9. PersonIR v0
10. Person Runner
11. LifeLang compiler prototype
12. SDK
13. independent Desktop Shell
14. real unrelated third-party applications
```

Do not jump to Desktop/UI work before the platform contracts are strong enough.

---

# Near-term milestone

The next meaningful platform milestone is not a better page.

It is this chain:

```text
Windows starts LifeHub Engine
        |
no browser
        |
install .lhpkg
        |
resolve component
        |
start component A
        |
A calls component B through Engine routing
        |
authority/capability is checked
        |
revoke
        |
next call fails immediately
        |
restart Engine
        |
state/lifecycle remains coherent
```

Then the language milestone:

```text
hello.life
    |
LifeLang compiler
    |
PersonIR
    |
verifier
    |
Person Runner
    |
LifeHub Engine
```

Those two chains, not a website screenshot, define whether LifeHub is becoming the
platform requested by the project.
