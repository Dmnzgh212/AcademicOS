# Conventional host API comparison — provisional

## Comparator and scope

`baseline.py` sketches a conventional capability-limited **host interface**: a component manifest declares readable observations, commit targets, and effect scopes; a session exposes `read`, `propose`, and `effect` calls. Trusted sample component functions implement the academic and email examples. The host can reuse the same `AuthorityStore`, `StateStore`, and `EffectService` as PersonIR. This intentionally holds authorization, version checks, and fake execution constant while comparing the programming interface.

The Python sample functions run in the host process and are **not safe untrusted components**. A separate executable core-WASM probe now runs with Node's WebAssembly engine (see below). It does not implement the Component Model, WIT, WASI, or the full request schema. This comparator assesses a narrow explicit-import boundary, not deployment overhead or a complete conventional component runtime.

## Observed comparison

| Dimension | PersonIR graph | Conventional host API sketch | Inference |
|---|---|---|---|
| Academic proposal | Explicit source/select/join/derive/propose/commit graph | Ordinary code reads two declared inputs and proposes a value | Same host version and authority semantics; no unique advantage shown. |
| Email egress | Verifier finds direct protected flow before execution; host checks disclosure and effect grants | Session conservatively marks all reads protected and requires disclosure at effect call; same grants | Graph offers earlier structural rejection and finer lineage, but same host owns actual authority. |
| Recipient equality | Current graph cannot express equality of recipient data and sink config | Component code compares them before request | Generic predicates or host contract validation needed in IR. |
| Package source/scope declaration | `PackageRunner` now binds a host-approved manifest to graph source names, commit targets, effect scopes, and disclosure purposes | Manifest and session check names/scopes at calls | Both mediated APIs can check declared scopes; neither proves package authenticity or protects direct host service calls. |
| Provenance | Node trace on values and receipts | Host records reads and request construction; opaque code internals are not traced | PersonIR provides finer inspectable dataflow for its tiny closed op set. |
| Payment/device/shared authority | Missing freshness, predicates, bounds, quorum | Could be programmed or enforced in host policy, but not implemented/tested here | Neither prototype proves these scenarios safe. |
| Execution isolation | No arbitrary code in serialized graph; trusted Python host | Sample Python code runs in host process; a separate core-WASM module has only two declared imports | Core-WASM import routing is exercised, but full component isolation and feature parity remain untested. |

## Executable core-WASM boundary probe

Run `node experiments/person_ir/wasm_baseline.mjs academic`; the actual compiled WebAssembly module calls only `host.read(index)` and `host.propose(course, slot)`. With an integer-only academic fixture it returns `[2110, 4]`. The host maps indices to observation names and checks its manifest before returning a value or accepting a proposal. `undeclared` attempts to read `secret` and fails; `no_commit` reads allowed inputs but fails when it requests an undeclared commit target. The module has no other imports, and cannot receive the host's authority registry through this ABI.

This is core WASM with a deliberately tiny numeric ABI, not a WASM Component/WIT implementation. It does not execute email, enforce PersonIR's disclosure rules, persist a commit, authenticate a package manifest, or measure end-to-end overhead. The host controls the imports and observation mapping; the experiment does not establish protection against a compromised host, covert channels, resource exhaustion, or malicious provider adapters. The previous Python baseline remains the feature comparison for academic and email.

## Restart recovery probe

`durable.py` adds a SQLite-backed local state/version/commit-receipt store. An authorized local commit writes state and its receipt in one SQLite transaction; a reopened store preserves the version and replays the receipt for the same proposal. This reuses the process-local authority registry, so grants and revocations themselves still need durable design.

`DurableEffectJournal` records an intent *before* external I/O. If a process stops before a receipt is recorded, the reopened journal reports `unknown` and refuses to begin that effect ID again. A trusted operator/provider reconciliation can then record a terminal result. The journal is a recovery primitive, **not wired into** `EffectService` or a real provider; callers must check live grants and request integrity before beginning, and preserve the same effect ID across restarts. It cannot distinguish an unsent pending intent from an externally completed action, guarantee exactly-once delivery, or prevent a new intent ID from causing a duplicate action. External provider idempotency/reconciliation remains required.

The baseline deliberately reuses the experimental request dataclasses and host services, so equality of enforcement in these tests is by construction. It demonstrates that the useful policy checks can live in an ordinary host API; it does **not** establish that a complete WASM/WIT component has identical usability, provenance, or cost.

`PackageRunner` snapshots the verified graph and filters overprovided host observations. Its manifest is an independent **host approval**, not an extension-authored authority token. The bare interpreter remains an experimental API without this binding, and the LifeHub loader and service entry points do not yet require it. A host that hands the result (including protected local outputs) directly to a plugin still violates the intended data boundary.

## Local overhead probe

Run `python -m experiments.person_ir.benchmark`. On this execution environment, one run with five repeats of 2,000 operations each returned median microseconds per request construction:

| Example | PersonIR graph | Host API sketch | Ratio |
|---|---:|---:|---:|
| Academic | 88.81 µs | 27.00 µs | 3.29× |
| Email | 86.70 µs | 40.58 µs | 2.14× |

Graphs and manifests were constructed outside the measured call; neither case commits state, executes effects, crosses a process boundary, or uses a WASM engine. The graph repeatedly verifies nodes and builds detailed traces, so this is a narrow Python implementation cost, not evidence about the performance of an optimized IR or a sandboxed component. The benchmark script is the reproducible evidence; figures will vary by machine and run.

## Decision gate

The seven PersonIR slices show useful explicit requests and inspectable lineage, but the five examples do not demonstrate safe cross-domain generality. The new package boundary handles previously reproduced source/manifest gaps on one trusted entry path; direct service forgery and domain preconditions remain. The comparator can express academic and email flows with existing host policy, and ordinary code can state recipient equality more directly. No measured or semantic advantage currently justifies a new source language/compiler.

**Provisional decision: hold compiler work.** Continue LifeHub as an open capability host, repair the package/input boundary, and test generic policy preconditions and multi-principal grants. Then evaluate a feature-comparable isolated component (preferably WASM Component/WIT), durable authority, and a real effect adapter with reconciliation before a final POP/PersonIR Go/No-Go. This is not a decision to abandon LifeHub or a proof that a better PersonIR is impossible.
