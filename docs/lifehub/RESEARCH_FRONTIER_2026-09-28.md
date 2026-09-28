# LifeHub research frontier — 2026-09-28

## Purpose

This document separates prior art from the parts of LifeHub that could become genuinely distinctive. The goal is not to claim novelty prematurely. The goal is to identify a technical thesis worth proving.

## What is already well explored elsewhere

### Local-first / user-owned data
Ink & Switch articulated local-first software as a model in which users retain ownership, offline capability, long-term access, and agency over data. Solid, HAT, MyData, Databox, and many personal-data-store projects also center the individual as the point of integration.

Conclusion: local storage and user ownership are necessary, but not novel.

### Capability-based component systems
WASI, Fuchsia, seL4-style systems, object-capability systems, and related work already demonstrate that software components can start with no ambient authority and receive only explicit capabilities.

Conclusion: capability-based extension isolation is a strong foundation, but not by itself a LifeHub invention.

### Compartmentalization
Qubes demonstrates security by compartmentalization: isolate domains so a compromise does not automatically become compromise of the whole system.

Conclusion: LifeHub should assume extensions can be buggy or malicious and design containment around that assumption.

### Personal data boxes and code-to-data
Databox is the closest historical predecessor found in this research. It provided local personal-data stores, isolated third-party apps, manifests describing requested data and purposes, an arbiter enforcing access, an app store, audit logs, and an export service. Its research explicitly described bringing computation to the data and minimizing external disclosure.

Conclusion: "personal data + local apps + manifests + access control" already has substantial prior art. LifeHub must go further.

### Extensible operating systems
The exokernel work separated protection from resource management: the kernel protects resources while untrusted application-level software defines higher-level abstractions.

Conclusion: this is a powerful conceptual model for LifeHub. The kernel should protect personal data and capability boundaries while extensions define life semantics and workflows.

## The strongest LifeHub opportunity

The clearest unexplored product/system thesis is:

> An open personal-computing extension ecosystem in which arbitrary new functionality may be installed, but no extension is allowed to create an unchecked path from personal data to the external network.

This is stronger than ordinary app permissions. The platform should make *function extensibility* and *data non-egress* independent properties.

## Proposed core innovation 1 — Personal Exokernel

LifeHub should act as a personal-data exokernel.

The kernel owns only protection mechanisms:

- package identity and provenance
- extension lifecycle
- capability routing
- data access mediation
- network mediation
- durable local records
- provenance / transformation lineage
- scheduling and event delivery
- policy enforcement

The kernel must not define life-domain abstractions such as course, workout, stock, restaurant, trip, or habit.

Extensions define those semantics in user space.

This mirrors the exokernel separation of protection from management, applied to personal computing rather than hardware resource management.

## Proposed core innovation 2 — No-Bridge Invariant

A single untrusted extension execution context should never simultaneously possess:

1. the capability to read personal or derived-personal data, and
2. unrestricted external network transmission capability.

This should be enforced structurally, not by convention.

A practical extension package can be split into chambers:

### Ingress chamber

- may access explicitly allowlisted external origins
- may use approved public/query parameters and origin-bound credentials
- may write retrieved observations into local namespaces
- may not read personal namespaces

### Private compute chamber

- may read user-granted local namespaces
- may derive insights, plans, recommendations, summaries, and indexes
- has no external network capability

### Presentation chamber

- may receive explicitly granted local views/data from the host
- renders UI locally
- has no arbitrary external network capability

This split sharply reduces the need to prove arbitrary information-flow behavior inside third-party code.

## Proposed core innovation 3 — Capability Flow Compiler

Before an extension package is installable, LifeHub should compile its manifest into a capability-flow graph.

Graph nodes may include:

- external origin
- ingress process
- namespace
- local processor
- UI surface
- secret/credential
- scheduler/event source

Graph edges represent allowed information flow.

The installer rejects a package if there is a path from a protected personal-data class to an external-network sink that is not explicitly part of a narrowly defined declassification mechanism.

This turns privacy into an install-time property that can be mechanically checked, then re-enforced at runtime.

A future marketplace could therefore show a machine-verifiable statement such as:

> This package has no capability path capable of exporting personal data through standard LifeHub APIs.

This is stronger than a privacy policy or a developer promise.

## Proposed core innovation 4 — Purpose-Bound Capability Leases

A grant should eventually be richer than `(plugin, resource, operation)`.

Candidate model:

`(subject, resource, operation, purpose, scope, expiry, activation-context)`

Examples:

- read `academic.deadlines` for purpose `daily-brief`, for 24 hours
- read `fitness.plan` for purpose `today-view`, while the view is open
- read `finance.market-watchlist` for purpose `local-risk-summary`, until revoked

Purpose-based access control exists in prior research and Databox manifests also recorded purposes. The opportunity is to combine purpose-bound grants with a capability runtime, extension lifecycle, and the No-Bridge Invariant.

## Proposed core innovation 5 — Provenance-First Personal Data Fabric

Raw observations should be append-oriented and durable. Derived state should carry lineage.

Every useful record should be able to answer:

- where did this come from?
- when was it observed?
- which extension transformed it?
- what other records were inputs?
- which code/package version produced the result?
- what policy/grant enabled the computation?

Derived artifacts should be recomputable from retained observations where practical.

This enables:

- time travel
- deterministic replay
- auditing
- migration to new analyzers
- evidence-backed recommendations
- debugging incorrect suggestions

## Proposed core innovation 6 — Advisory Intelligence Boundary

LifeHub should distinguish four classes:

1. Observation — sourced fact or imported data
2. Interpretation — derived classification or estimate
3. Suggestion — proposed action or plan
4. Authority — explicit permission to change state or invoke an external action

An AI/model/analyzer may create interpretations and suggestions by default. It must not silently convert them into observations or authority.

This preserves human agency and makes AI replaceable rather than foundational to truth.

## Proposed core innovation 7 — Open Semantic Extension Fabric

LifeHub should avoid a closed ontology of life domains.

The kernel indexes extension points but should not own a final list of semantic categories. Extensions may introduce new points, schemas, protocols, and adapters. Consumers may themselves be extensions.

Interoperability should emerge through versioned protocols/data contracts rather than a mandatory global life schema.

This is the semantic analogue of keeping mechanism in the kernel and policy/abstraction in user space.

## Proposed core innovation 8 — Privacy-Verifiable Package Ecosystem

The package system should combine:

- signed package identity
- cryptographic hashes
- reproducible or attestable builds where possible
- capability manifest
- dependency manifest
- SBOM
- TUF-style compromise-resilient update metadata
- Sigstore-style provenance where appropriate
- install-time capability-flow verification

The trust question becomes two separate questions:

1. Did this package come from the publisher/source it claims?
2. Even if the package is malicious, what can its sandboxed runtime actually access and exfiltrate?

Both must be answered.

## Important non-innovations — use, do not market as inventions

LifeHub should freely reuse mature ideas for:

- local SQLite/event storage
- local-first UX
- WebAssembly/WASI sandboxing
- signed packages
- drag-and-drop dashboards
- plugin manifests
- JSON Schema
- event buses
- job schedulers
- extension registries
- command palettes

The product should not confuse assembling known primitives with inventing them.

## The strongest differentiating architecture

A useful shorthand:

```text
                       LIFEHUB
                          |
                  Personal Exokernel
                          |
        +-----------------+-----------------+
        |                 |                 |
   Package/Identity   Capability Flow   Provenance
        |               Compiler          Ledger
        +-----------------+-----------------+
                          |
                    Extension Runtime
                          |
              +-----------+-----------+
              |                       |
          Ingress Chamber        Private Compute
       network, no private read   private read, no net
              |                       |
              +-----------+-----------+
                          |
                  Local Data Fabric
                          |
                    Presentation
                          |
                         User
```

The security invariant is more important than any dashboard:

> No unchecked path from personal data to external network.

The extensibility invariant is equally important:

> New life semantics must not require kernel modification.

## Closest predecessor and how LifeHub must differ

Databox is the most important prior art found. It already had local processing, isolated apps, manifests, an arbiter, an app store, audit logs, and controlled export.

LifeHub should not merely recreate Databox with a modern UI.

Potential differentiators:

- general personal-computing platform, not primarily IoT
- arbitrary semantic extension fabric
- strict no-egress mode as a platform invariant rather than an app risk preference
- structurally separated ingress and private-compute chambers
- install-time capability-flow verification
- provenance graph for derived personal intelligence
- evidence -> interpretation -> suggestion -> authority separation
- local cross-domain composition without central cloud context
- reuse of existing local/open-source services through adapters

## Research questions that must be answered before claiming novelty

1. Can the No-Bridge Invariant be enforced robustly with WASI/component isolation on Windows/Linux/macOS?
2. Which covert channels remain even when filesystem, process, raw socket, DNS, clock, and environment capabilities are constrained?
3. Can useful real-world connectors operate when networked ingress components cannot read personal data?
4. What parameter types must be allowed for authenticated retrieval without creating an exfiltration side channel?
5. How should origin-bound credentials be represented so a connector can authenticate without reading reusable secrets?
6. How should derived-data sensitivity propagate through transformations?
7. Can capability-flow verification remain understandable to normal users?
8. Can packages be upgraded without invalidating grants, lineage, or user-owned data?
9. How can cross-extension protocols evolve without creating a central ontology bottleneck?
10. Can local models provide useful cross-domain advice without making the AI runtime a new privileged super-plugin?

## Near-term proof targets

LifeHub should not add many consumer features until it can prove these invariants with hostile test extensions.

### Proof A — unknown semantics
Install an extension using a point the kernel has never seen. No kernel code changes.

### Proof B — private compute cannot exfiltrate
Give a hostile processor access to personal data. It must be unable to open sockets, DNS, arbitrary files, subprocesses, or external URLs.

### Proof C — ingress cannot read personal data
Give a hostile connector network retrieval capability. It must be unable to access personal namespaces.

### Proof D — composition
A local analyzer receives explicit grants to academic + fitness + weather namespaces and produces a local recommendation without obtaining network capability.

### Proof E — lineage
Every output of Proof D can be traced to input records, extension package version, code identity, and grants used.

### Proof F — package compromise resilience
A tampered or unsigned package/update must be rejected. A compromised online signing role alone must not be sufficient to silently replace trusted packages.

If LifeHub can make these properties routine for third-party extensions while remaining pleasant to develop for, that would be a meaningful technical contribution rather than only a personal dashboard.
