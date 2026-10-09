# LifeHub — Core Thesis & Highest-Level Engineering Direction

> **2026-10-08 latest project decision (controlling): [LH-D-LOCAL-002 — Localization-first reuse and low-barrier user validation](LOCALIZATION_AND_USER_ACCEPTANCE_DIRECTIVE.md).** Open architecture is not an unfiltered external-plugin ingress. Prioritize lawful selective local copying/adaptation of mature application code; preserve maintained dependencies for complex infrastructure when safer. Engineers/AI assistants own integration and security verification. Ordinary users only need import/run/revoke/error-report workflows. An external human software developer is **not** mandatory for the M1 technical gate. Older contradictory language below has been reconciled; M1 acceptance still requires explicit review.

**Status:** Reaffirmation proposed for review; not an already-merged directive or a claim of M1 acceptance.
**Scope:** Product identity, sovereign-person authority, architecture, reuse/research discipline and milestone governance.
**Priority:** These project-wide principles constrain stage-specific implementation plans. The separate [M1 acceptance gate](https://github.com/Dmnzgh212/AcademicOS/blob/docs/lifehub-m1-acceptance-gate/docs/lifehub/M1_ACCEPTANCE.md) describes the current delivery checkpoint, **not** the final product identity.

> This file consolidates previously stated project guidance and repository research/handoff material. It is **not** a verbatim reproduction of any unpublished separate "highest approval" or "new rules" document; attach that original text for exact source-level reconciliation if one exists.

## I. The fundamental mission

**LifeHub is an open, person-centered computing platform, not a finished application.**

> **LifeHub does not define your digital life. It provides the mechanisms by which you assemble it.**

The aim is an open, extensible substrate comparable **in openness and platform role** to Linux/Android or an engine used by many applications; it is **not** a claim to be a new OS kernel, a browser renderer, or a replacement for their security models.

An **independent, locally adapted module**, whether built by project engineers, an AI assistant or a later outside contributor, must be able to install, run and communicate through controlled, documented contracts **without app-specific modification to LifeHub Core**. Outside authorship is not a prerequisite for Engine technical verification. Upstream code has no automatic import, execution or data authority; the default product path is to select useful mature open-source code and turn it into a reviewed, replaceable LifeHub-local capability. AcademicOS, a course planner, mail assistant, task manager, calendar, AI assistant, or robotic system may be applications **on** LifeHub; none defines LifeHub itself.

**A dashboard, approval inbox, calendar, widget container, or Web app is not evidence that the platform exists.** These can be optional replaceable Shells or apps. When every optional Shell is absent or closed, the Engine and approved background software must still operate.

## II. Person sovereignty: authority, state, and effects

The founding shorthand is:

> **Software proposes. The Person commits.**

For engineering accuracy, the fuller expression is:

> **Software proposes. Authority commits. The Person is the root of authority.**

This does **not** mean that each operation needs a human click. A person may issue narrowly scoped, revocable, time/resource-bounded delegation; a valid previously delegated authority can authorize an automatic commit. A plugin must not mint or escalate its own authority. The Engine enforces these boundaries; a policy convention in a plugin is not enough.

- **Observation/Evidence** records something that happened outside the system (an email arrived, a transaction occurred, an announcement was published); this fact must not be rewritten just because a person declined a proposal.
- **Derived/Interpretation** is a computation or inference; it must not silently be promoted into evidence.
- **Proposal** suggests a change to durable personal intent/state; **Commit** requires relevant authority and appropriate consistency/revalidation checks.
- **EffectRequest** is not an Effect. Irreversible external acts (sending email, paying, controlling a device) require an explicit effect authority and controlled executor.
- **Provenance, accountability and audit** should travel with the relevant changes, permissions and external actions wherever implementable.
- **Private by default, not immobile by dogma:** authorized communications, sharing and AI use are legitimate. Personal information must not silently leave its boundary; egress/disclosure requires an explicit, scoped authority/declassification path.

The user is not a mutable software object. `PersonalDomain` refers to a person-associated **digital computing/authority domain**, not software modifying the human being. The possibility of multi-person/shared authority remains a research problem, not something to simplify away.

## III. Platform boundaries that must not drift

```text
CLI / Desktop / Web / Mobile / other replaceable Shells
                         |
                 versioned local API
                         |
                     LifeHub Engine
    package identity | discovery | capability routing
    supervised runtime | durable state | mediated data/effects
                         |
                 host OS / permitted adapters
```

1. **Engine first, Shell replaceable.** No Engine import or lifecycle dependency on the reference Web, page layout, or any UI technology. Do not route core responsibilities back into a dashboard.
2. **Mechanisms in Core; life domains outside Core.** Core knows packages, identity, contracts, capabilities, routing, execution/lifecycle, protected local storage, policy, audit, provenance, and mediated effects. Core does **not** hard-code a final taxonomy of `course/health/stock/trip/habit/robot` applications or UI widgets.
3. **Open components, constrained authority.** Packages declare provided/required interfaces and requested capabilities. Discovery is not consent; installation is not unlimited permission. Routing/bindings come from the trusted host, never from a JSON claim of caller or provider identity.
4. **Default-deny execution and disclosure.** Approved immutable package/snapshot identity; capability grants bound to their intended resources and lifetime; revoke/uninstall/reinstall must not resurrect stale authority. Untrusted app code does not become privileged in-process Python/native code merely by being packaged.
5. **Long-running software is a first-class use case.** Real guest work after all Shells close, truthful readiness/state, supervision, controlled restart, interruption history, cleanup, and resource ceilings matter more than a static catalogue.
6. **Interoperability without owning the app.** Applications communicate through versioned interfaces and mediated data, not private source-code imports, a shared unbounded SQLite connection, or unrestricted access to each other's filesystem.
7. **Interchangeable AI and extensible infrastructure.** AI models and application-specific intelligence are replaceable components. No permanent vendor, model, calendar, email provider, or front end is allowed to become LifeHub's definition.

## IV. Reuse established technology; invent only where there is a gap

> **2026-10-08 最新修订：** 应用层优先选择性复制、裁剪并本地化成熟开源代码，统一接口与权限，经过工程安全验证才纳入 LifeHub；复杂底层基础设施仍依赖安全、可维护的成熟实现，不为“复制”而重写。小型功能可自行编写。参见 [LH-D-LOCAL-002](LOCALIZATION_AND_USER_ACCEPTANCE_DIRECTIVE.md)。**历史 2026-10-07 决议适用于不与最新决议冲突的部分：** 大型成熟模块先查、先用、先接入做适配测试，发现具体问题后局部修改；小型简单模块允许按效率自行编写，不为复用而增加复杂依赖。**研究成熟方案不等于已经完成实际集成；不得研究完后默认从头重写。** 具体执行程序、对 PR #63/#64 的裁决、许可与证据要求见 **[LH-D-REUSE-001 — 工程复用最高指导](ENGINEERING_REUSE_DIRECTIVE.md)**。

**Do not reinvent common infrastructure simply to look novel.**

- **For app/domain functionality, localize first:** search mature OSS; when legally compatible, selectively copy the needed source modules into a controlled local package, trim unnecessary dependencies, adapt LifeHub contracts and security, test and track upstream updates. Do not default to direct unfiltered upstream plugin ingestion.
- **For foundational infrastructure**, prefer maintained mature libraries, system APIs or locally version-pinned dependencies; copying or reimplementing a VM, crypto, database or OS primitives without compelling evidence is unsafe.
- Reuse already-installed project dependencies and learn from relevant open-source projects before writing a new module. Keep *reference/inspiration*, *adopted dependency*, and *copied source code* as separate decisions.
- Copying a module is **not automatically simpler** than using its maintained library: first inspect license/attribution obligations (including copyleft implications), security history, transitive assumptions, maintenance cost and platform compatibility. Never copy an entire project by default.
- Preserve the trust model: reusing `Wasmtime`, `SQLite`, OS process controls or mature supervision mechanisms does not itself prove complete isolation, real-time guarantees, memory/CPU containment, or cryptographic trust.
- LifeHub's original work should be the **composition, authority/provenance semantics and open personal-computing contracts** where ordinary tools cannot meet a demonstrated need—not a fresh VM, RPC, compiler, storage engine, cryptographic primitive, or UI toolkit merely for its own sake.

**Evidence threshold for changing Core:** an actual independent integration blocker shared by unrelated apps, a reproduced security/lifecycle violation, or a concrete platform contract gap. No speculative Core expansions and no performance claims without measurement.

## V. Research is important, but separate from shipping runtime

Person-Oriented Programming (POP), PersonIR/LifeIR and a future easy-to-use LifeLang-like development language are part of the long-term vision **and are not to be forgotten**. An approachable open developer language (as easy to adopt as good conventional tooling) remains a possible future destination, not a deliverable required to declare today's Engine viable.

The latest project guidance **reopens disciplined PersonIR semantics research**; it does **not** overturn the evidence-based **No-Go for productionizing a new source language/compiler now**:

- Keep experiments separate from `src/academicos/lifehub` production dependencies. Do not move `experiments/person_ir` into Engine simply to satisfy a milestone.
- First demonstrate or falsify semantics for person-associated authority, delegated commits, provenance, information flow, proposals and external effects. Use heterogeneous scenarios (e.g. academic work, communication, payment, devices, multi-person collaboration) and adversarial tests.
- Compare with a conventional capability-limited Wasm/WIT or other mature baseline. A new compiler is justified only by a **specific reproducible enforcement, expressiveness or developer-experience advantage** that ordinary APIs/policies cannot reasonably provide.
- Evaluate WIT/Component Model as an **isolated interoperability experiment** until a validated engineering requirement justifies adoption. Passing a small typed-echo spike is not authority to widen Core.
- **A failed PersonIR hypothesis must not jeopardize LifeHub.** Preserve useful findings on authority, provenance and effects in ordinary platform contracts.

Research reopening and production freeze are different decisions. Do not frame either as a permanent rejection of human-oriented programming.

## VI. Development and audit policy

**Proof of Engine engineering progress = separately packaged, reviewed local modules exercising actual platform capabilities**, not an outside programmer's identity. **Proof of a useful product** additionally requires actual user need and proportional engineering cost; a working two-package test demo is not automatically a worthwhile application. Engineering/AI integration and security review are the developer responsibility; end-user usability validation should require only guided import, run, permission review/revoke and error reporting.

Prefer the observable sequence `build → package → review → install → run through an actual Engine process → communicate via granted interface → revoke/deny → stop/crash/recover`. Use more than one non-Core application scenario and real installed-artifact validation for the M1 technical gate. Independent external **human** authorship is **not** mandatory for M1; it may be evaluated later as a separate ecosystem/SDK objective. Self-written fixtures still need actual runnable, permission-constrained behavior and honest evidence.

- Green CI, rising pytest count, hundreds of PRs, code volume or an invented completion percentage are **supporting indicators only**; none answers whether the platform can actually run independent software.
- Use real Windows and Linux installed-artifact smoke runs, bounded faults, reproducible commands and retained logs. State precisely what is verified, limited, or unverified.
- Keep stage work coherent. The current **M1 — Background Supervisor** technical acceptance checklist (being revised to remove the mandatory external-human-author gate) is in [the dedicated documentation PR](https://github.com/Dmnzgh212/AcademicOS/pull/56). M1 is not the whole project. Technical M1 acceptance, public SDK planning and useful-application prototypes are separate decisions. Small, time-boxed useful-module experiments may proceed alongside M1 review **if they do not block security closure or become substitute acceptance evidence**. Do not hold every useful app hostage to an unrelated author gate; do not expand low-value demos merely because CI is green.
- Work continuously between milestone gates. Routine PR-by-PR leadership reports are unnecessary. Escalate urgent security/data-loss defects, changes to the project thesis/trust boundary or blocked design decisions. Otherwise submit a consolidated evidence package at M1.
- Stacked runtime PRs remain Draft until individual CI/code review and a separate integration decision; documentation-only agreement does not authorize a main merge.

## VII. Non-negotiable drift checks

Stop and request direction if an implementation:

1. Makes Web/Dashboard/AI/calendar the mandatory runtime or the definition of LifeHub.
2. Requires editing Core for each new kind of third-party application.
3. Allows plugins to self-grant authority, conceal egress, directly alter protected personal state, or execute uncontrolled external effects.
4. Confuses daemon uptime with background **guest** work, or passing tests with real integration.
5. Promotes research prototypes or new syntax into production without falsifiable comparative evidence.
6. Rewrites well-supported open-source infrastructure without a demonstrated need.
7. Declares a product release, complete security isolation, M1 completion or universal compatibility without corresponding evidence.

### Relation to older material

Read the [2026-09-28 handoff](HANDOFF_2026-09-28.md), [research frontier](RESEARCH_FRONTIER_2026-09-28.md), [direction audit](DIRECTION_AUDIT_2026-10-03.md), and [accepted platform baseline](PLATFORM_STATUS.md) for history and evidence.

The older mainline direction audit said **No-Go for the compiler** and the v0.1 engineering line kept PersonIR research frozen during platform acceptance. Later project guidance reopened **semantics research**, **not** automatic compiler production. This document keeps both boundaries explicit rather than silently choosing one old sentence.

**One-sentence north star:** Build a person-sovereign, locally controlled computing Engine that can absorb and adapt **worthwhile, sufficiently complex** existing code into reviewed, replaceable local capabilities under revocable authority; tiny functions remain simple. Shells, AI and research languages are interchangeable, and ordinary users should import/run/revoke/report errors without doing engineering.
