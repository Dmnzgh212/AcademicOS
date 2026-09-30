# Conventional host API comparison — provisional

## Comparator and scope

`baseline.py` sketches a conventional capability-limited **host interface**: a component manifest declares readable observations, commit targets, and effect scopes; a session exposes `read`, `propose`, and `effect` calls. Trusted sample component functions implement the academic and email examples. The host can reuse the same `AuthorityStore`, `StateStore`, and `EffectService` as PersonIR. This intentionally holds authorization, version checks, and fake execution constant while comparing the programming interface.

The Python sample functions run in the host process and are **not safe untrusted components**. Separate executable core-WASM academic and email probes run with Node's WebAssembly engine (see below). They do not implement the Component Model, WIT, WASI, or the full request/receipt schema. This comparator assesses a narrow explicit-import boundary and request construction, not deployment overhead or a complete conventional component runtime.

## Observed comparison

| Dimension | PersonIR graph | Conventional host API sketch | Inference |
|---|---|---|---|
| Academic proposal | Explicit source/select/join/derive/propose/commit graph | Ordinary code reads two declared inputs and proposes a value | Same host version and authority semantics; no unique advantage shown. |
| Email egress | Verifier finds direct protected flow before execution; host checks disclosure and effect grants | Python session requires disclosure at effect call; core-WASM module checks recipient equality and the Node host requires declared disclosure/effect scopes | Request shape is comparable; only Python baseline has been run through the shared authority/effect service. |
| Recipient equality | Current graph cannot express equality of recipient data and sink config | Component code compares them before request | Generic predicates or host contract validation needed in IR. |
| Package source/scope declaration | `PackageRunner` now binds a host-approved manifest to graph source names, commit targets, effect scopes, and disclosure purposes | Manifest and session check names/scopes at calls | Both mediated APIs can check declared scopes; neither proves package authenticity or protects direct host service calls. |
| Provenance | Node trace on values and receipts | Host records reads and request construction; opaque code internals are not traced | PersonIR provides finer inspectable dataflow for its tiny closed op set. |
| Payment/device/shared authority | Missing freshness, predicates, bounds, quorum | Could be programmed or enforced in host policy, but not implemented/tested here | Neither prototype proves these scenarios safe. |
| Execution isolation | No arbitrary code in serialized graph; trusted Python host | Sample Python code runs in host process; core-WASM academic/email modules use explicit host imports | Core-WASM import routing is exercised, but full component isolation and end-to-end service parity remain untested. |

## Executable core-WASM boundary probe

Run `node experiments/person_ir/wasm_baseline.mjs academic`; the actual compiled WebAssembly module calls only `host.read(index)` and `host.propose(course, slot)`. With an integer-only academic fixture it returns `[2110, 4]`. The host maps indices to observation names and checks its manifest before returning a value or accepting a proposal. `undeclared` attempts to read `secret` and fails; `no_commit` reads allowed inputs but fails when it requests an undeclared commit target. The module has no other imports, and cannot receive the host's authority registry through this ABI.

Run `node experiments/person_ir/wasm_email.mjs email` for a protected email request. Its module uses only `read`, `destination`, `equal`, and `send` imports. It compares the recipient with the destination in WASM before requesting a send. The Node host records each read under a distinct opaque handle and checks that the submitted handles match their observed sources, that the effect kind/destination is declared, and that protected reads have a declared destination/purpose disclosure. The request matches the PersonIR example's payload, destination, sensitivity, disclosure purpose, and source set. `mismatch`, `undeclared`, `no_effect`, `no_disclosure`, and `forged_handle` exercise denial paths. A recipient mismatch traps before `send`; the host repeats the equality check at the sink.

These are core-WASM probes with small numeric/opaque-handle ABIs, not WASM Component/WIT implementations. Neither module can access the host's authority registry, and neither performs an external action. The email request description is not yet materialized into the shared Python `EffectRequest` and passed through `AuthorityStore`/`EffectService`; its Node host manifest and disclosure checks are separate implementations. Thus request parity is narrower than authorization, provenance, replay, and receipt parity. The host controls imports and observations; the experiment does not establish protection against a compromised host, covert channels, resource exhaustion, or malicious provider adapters. The Python baseline remains the end-to-end fake-effect comparison.

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

**Provisional decision: hold compiler work.** Continue LifeHub as an open capability host, integrate the package/input boundary, and test generic policy preconditions and multi-principal grants. Then evaluate end-to-end authority/receipt parity for an isolated component (preferably WASM Component/WIT), durable authority, and a real effect adapter with reconciliation before a final POP/PersonIR Go/No-Go. This is not a decision to abandon LifeHub or a proof that a better PersonIR is impossible.
