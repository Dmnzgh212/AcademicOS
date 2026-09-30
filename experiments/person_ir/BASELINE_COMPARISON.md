# Conventional host API comparison — provisional

## Comparator and scope

`baseline.py` sketches a conventional capability-limited **host interface**: a component manifest declares readable observations, commit targets, and effect scopes; a session exposes `read`, `propose`, and `effect` calls. Trusted sample component functions implement the academic and email examples. The host can reuse the same `AuthorityStore`, `StateStore`, and `EffectService` as PersonIR. This intentionally holds authorization, version checks, and fake execution constant while comparing the programming interface.

The Python sample functions run in the host process and are **not safe untrusted components**. Separate executable core-WASM academic and email probes run with Node's WebAssembly engine (see below). A trusted Python bridge now passes the email request through the same authority and fake-effect services. These probes do not implement the Component Model, WIT, WASI, or a general component ABI. The comparison remains narrow.

## Observed comparison

| Dimension | PersonIR graph | Conventional host API sketch | Inference |
|---|---|---|---|
| Academic proposal | Explicit source/select/join/derive/propose/commit graph | Ordinary code reads two declared inputs and proposes a value | Same host version and authority semantics; no unique advantage shown. |
| Email egress | Verifier finds direct protected flow before execution; host checks disclosure and effect grants | Core-WASM checks recipient equality; Node host checks scopes/handles; Python bridge materializes an effect for the same authority/effect service | Both paths now run through live grants, replay, and fake receipts. The bridge performs email-specific payload validation. |
| Recipient equality | Current graph cannot express equality of recipient data and sink config; optional host policy checks the effect payload | Component code compares them before request; same host policy can check it again | The use-time guard is conventional host policy, not a unique IR property. |
| Package source/scope declaration | `PackageRunner` now binds a host-approved manifest to graph source names, commit targets, effect scopes, and disclosure purposes | Manifest and session check names/scopes at calls | Both mediated APIs can check declared scopes; neither proves package authenticity or protects direct host service calls. |
| Provenance | Node trace on values and receipts | Host records reads and request construction; opaque code internals are not traced | PersonIR provides finer inspectable dataflow for its tiny closed op set. |
| Payment/device/shared authority | Generic optional host policy checks bounds/current evidence/field relations; joint host gate checks two grants and persists both IDs with a commit | The same host checks can guard conventional component requests | Current evidence authenticity, enforced shared-domain routing, cross-process atomicity and real providers remain open. |
| Execution isolation | No arbitrary code in serialized graph; trusted Python host | Sample Python code runs in host process; core-WASM academic/email modules use explicit host imports | Core-WASM import routing is exercised, but full component isolation and end-to-end service parity remain untested. |

## Executable core-WASM boundary probe

Run `node experiments/person_ir/wasm_baseline.mjs academic`; the actual compiled WebAssembly module calls only `host.read(index)` and `host.propose(course, slot)`. With an integer-only academic fixture it returns `[2110, 4]`. The host maps indices to observation names and checks its manifest before returning a value or accepting a proposal. `undeclared` attempts to read `secret` and fails; `no_commit` reads allowed inputs but fails when it requests an undeclared commit target. The module has no other imports, and cannot receive the host's authority registry through this ABI.

Run `node experiments/person_ir/wasm_email.mjs email` for a protected email request. Its module uses only `read`, `destination`, `equal`, and `send` imports. It compares the recipient with the destination in WASM before requesting a send. The Node host records each read under a distinct opaque handle and checks that the submitted handles match their observed sources, that the effect kind/destination is declared, and that protected reads have a declared destination/purpose disclosure. The request matches the PersonIR example's payload, destination, sensitivity, disclosure purpose, and source set. `mismatch`, `undeclared`, `no_effect`, `no_disclosure`, and `forged_handle` exercise denial paths. A recipient mismatch traps before `send`; the host repeats the equality check at the sink.

The trusted `wasm_bridge.py` now snapshots host observations, launches the email module in a Node subprocess, verifies the resulting description against those snapshots and the approved manifest, and uses `ComponentSession` to create a conventional `EffectRequest`. Tests then pass it through the same `AuthorityStore` and `EffectService`: missing disclosure and revoked effect grants block it; the same intent replays one fake action and its receipt. The bridge checks the email payload shape and source values in trusted code, which is a cost and constraint of this comparator, not a generic provenance solution.

These are core-WASM probes with small numeric/value-handle ABIs, not WASM Component/WIT implementations. The WASM module itself cannot access the host's authority registry or external action; the Node and Python host code are trusted. Authorization/receipt parity is now demonstrated for one fake email flow, but not for general components, durable authority, real provider behavior, or end-to-end crash recovery. The host controls imports and observations; the experiment does not establish protection against a compromised host, covert channels, resource exhaustion, or malicious provider adapters.

## Restart recovery probe

`durable.py` adds SQLite-backed authority, local state/version, and commit receipts. An authorized local commit writes state and its receipt in one SQLite transaction; a reopened store preserves the version and replays the receipt for the same proposal. `DurableAuthorityStore` persists grant metadata and revocations. At trusted host startup it builds **new in-process object handles** for stored grants; serialized grant IDs and old handles cannot authorize a request. Expiry and revocation are checked at use time, including a revocation written by another registry instance. Tests reopen both authority and effect services and replay only after live authorization. The host must authenticate its startup and session before distributing recovered handles; issuer authentication and that distribution policy are not implemented.

`DurableEffectService` now uses `DurableEffectJournal` with the same request-integrity and live-grant checks as the in-memory service. It commits an intent *before* calling a fake executor and records the resulting receipt afterward. Completed receipts replay across service restarts only after a fresh grant check. Tests interrupt execution after the fake action but before recording its receipt: the restarted service reports `unknown`, raises `EffectUncertain`, and never calls the executor again for that effect ID. A WASM email request also replays its durable receipt across a service restart. The low-level journal can record a reconciled terminal result, but a trusted reconciliation workflow producing a complete receipt is not implemented.

This is a conservative fake-effect recovery path, not a real provider adapter. The pending journal row does not contain a completed receipt, and the service cannot distinguish an unsent intent from an externally completed action. The durable authority probe reads revocation from SQLite at check time, but a different process could revoke between its check and an external action; no cross-process transaction or lease spans that interval. It cannot guarantee exactly-once delivery or prevent a new intent ID from causing a duplicate action. Provider-side idempotency/reconciliation remains required.

The baseline deliberately reuses the experimental request dataclasses and host services, so equality of enforcement in these tests is by construction. It demonstrates that the useful policy checks can live in an ordinary host API; it does **not** establish that a complete WASM/WIT component has identical usability, provenance, or cost.

`PackageRunner` snapshots the verified graph and filters overprovided host observations. Its manifest is an independent **host approval**, not an extension-authored authority token. The bare interpreter remains an experimental API without this binding, and the LifeHub loader and service entry points do not yet require it. A host that hands the result (including protected local outputs) directly to a plugin still violates the intended data boundary.

`EffectPolicy` is an optional trusted host gate applied before a new fake action, not extension-authored authority. Generic rules express numeric bounds, comparisons of payload paths, destination equality, and binding a payload path to a fresh current observation. `JointCommitService` requires two distinct live grants from host-specified principals; the state transaction persists both checked grant IDs in its receipt. These controls work on ordinary request objects from either programming model, strengthening the conventional-host explanation. Their inputs, policy approval, and enforced routing remain trusted host responsibilities.

## Local overhead probe

Run `python -m experiments.person_ir.benchmark`. On this execution environment, one run with five repeats of 2,000 operations each returned median microseconds per request construction:

| Example | PersonIR graph | Host API sketch | Ratio |
|---|---:|---:|---:|
| Academic | 88.81 µs | 27.00 µs | 3.29× |
| Email | 86.70 µs | 40.58 µs | 2.14× |

Graphs and manifests were constructed outside the measured call; neither case commits state, executes effects, crosses a process boundary, or uses a WASM engine. The graph repeatedly verifies nodes and builds detailed traces, so this is a narrow Python implementation cost, not evidence about the performance of an optimized IR or a sandboxed component. The benchmark script is the reproducible evidence; figures will vary by machine and run.

## Decision gate

The seven PersonIR slices show useful explicit requests and inspectable lineage, but the five examples do not demonstrate safe cross-domain generality. The package boundary handles previously reproduced source/manifest gaps on one trusted entry path; direct service forgery remains. Optional host policy and joint-grant checks reject the named use-time counterexamples without adding domain nodes to IR. The comparator can express academic and email flows with existing host policy, and ordinary code can state recipient equality more directly. No measured or semantic advantage currently justifies a new source language/compiler.

**Provisional decision: hold compiler work.** Continue LifeHub as an open capability host, integrate the package/input boundary and policy lifecycle, and require joint routing for shared domains. Then evaluate a general component ABI (preferably WASM Component/WIT), authenticated grant restoration/cross-process revocation, and a real effect adapter with reconciliation before a final POP/PersonIR Go/No-Go. The durable and host-policy probes close local gaps but do not remove those gates. This is not a decision to abandon LifeHub or a proof that a better PersonIR is impossible.
