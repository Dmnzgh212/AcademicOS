# PersonIR experiment — slices 1–7

This is an isolated falsification experiment, not a source language or a replacement for the LifeHub kernel. Run `python -m unittest discover -s experiments/person_ir/tests -v` from the repository root. `examples/academic.py` computes a local study-block proposal from two host observations.

## Executable contract

- The host supplies `Observation(value, source, label)` and a state `base_version`. `Graph.from_json(text)` loads `Node(id, op, inputs, config)` records in topological order. No node can hold a user-defined transform or callback. Inputs are restricted to copied JSON values. A Python constructor is also available for trusted experiments.
- `source`, `select`, `join`, and `derive` produce values. `join` propagates protected labeling and unions source references. `propose` produces an inert state proposal; `commit_request` produces an inert request. Neither writes state.
- `declassify` creates an inert disclosure request with a destination and purpose. It **does not authorize disclosure**. `effect_request` creates an inert request; a protected payload requires a matching disclosure request. No node executes network, file, process, payment, email, or device operations.
- `output` is a local result delivered to the trusted caller, including protected values. It is not an external sink; the host must not expose local results to plugins or network without policy checks.

## Slice 2: host-owned authority

`AuthorityStore.issue(...)` is a **trusted host operation**. It issues an in-memory opaque handle, while `describe(handle)` exposes non-authorizing metadata: capability ID, principal, domain, agent, operation, exact resource, issuer, issue/expiry time, optional activation context/purpose, and revocation status. A serialized description or ID cannot substitute for the handle, and an unrelated registry's handle does not work.

`check_commit_request`, `check_disclosure_request`, and `check_effect_request` validate the handle's identity, current revocation state, time window, principal/domain/agent, operation, exact resource, and optional context. An external effect with protected content needs both an effect grant and a distinct destination/purpose disclosure grant. Read authority confers neither commit nor effect authority. These checks produce audit metadata, **not an executable authorization token**. No effect executor or durable commit exists yet.

Issuance policy, authenticating the issuer, chained delegation, persistent revocation, atomic effect execution, and OS isolation are outside this slice. A standalone check followed later by an action has a revocation/expiry race; the slice 3 state store holds the authority lock through its local mutation. A future external executor needs its own use-time check. The registry is currently process-local and must never be passed to an untrusted Python plugin. JSON IR code has no access to `issue`.

## Slice 3: versioned local commit

The host creates `StateStore(domain, initial)` and gives the interpreter a base version from `snapshot()`. Each proposal has a deterministic ID based on its producer/version string, node ID, target, JSON value, base version, and observation source references. This hash distinguishes recomputations; it is **not a signature or proof that evidence is genuine**.

`StateStore.commit(request, authority, handle, ...)` checks live commit authority and proposal integrity while holding authority and state locks in that order. It returns a receipt, rejects stale versions, and records completed proposal IDs so the exact same computation cannot commit twice. A new proposal that writes an already equal value is a no-op and does not advance the version. Replayed requests still need live authority. Rejecting a proposal leaves state and the original observation unchanged.

This is conventional compare-and-swap/MVCC plus an idempotency ledger and explicit request boundary. **No semantic advantage over an ordinary capability host has been demonstrated yet.** State, ledger, and revocation are in memory; process restart loses them. It does not provide durable storage, shared-domain conflict resolution, multi-process transactions, or source authentication. External effects are not committed or rolled back with local state.

## Slice 4: simulated external effects

The interpreter computes an inert `EffectRequest` with a deterministic ID over producer/version, node, host-supplied intent ID, destination, kind, material payload, sensitivity, disclosure purpose, and source references. Recomputing the same intent and inputs yields the same ID; changing an input or explicitly starting another intent yields a different ID. The hash is an identity, not an authentic signature or an external price/current-state check.

The trusted host registers explicit `FakeExecutor` instances with `EffectService`. `execute` checks live effect authority and, for protected content, separate disclosure authority. It verifies request identity, records one receipt per domain and effect ID, and returns an earlier receipt on replay **after** another live authority check. Receipts distinguish `succeeded`, definite pre-action `failed`, and post-action `unknown`. A replay of a failed or unknown ID is terminal; the service never automatically retries an uncertain action. An explicit new intent might cause another action, so the user/host must reconcile unknown outcomes first.

The fake executors only append to memory; they do not send messages, transfer money, or control devices. Changing local state after an action does not undo that action. Neither ledger nor authority state survives a restart; there is a crash window between an external action and recording its receipt. Real providers need durable intent/receipt storage, provider-side idempotency keys or reconciliation, and fresh policy and external-state validation. **Exactly-once external effects are not claimed.**

## Slice 5: trace and information flow

Runtime values, proposals, disclosures, effects, and their host receipts carry an ordered `TraceStep` chain: source reference, producer/version, node and input IDs, operation, propagated label, and proposal base state version. A `nondeterministic_source` declares an AI, clock, or sensor-like host input and requires an execution ID and engine metadata on its trusted `Observation`. This records the execution context; the IR does not run an AI model. Receipts also include the grant IDs used at commit/effect time. Request identities include the trace, so modifying it after construction without changing the identity is rejected.

The verifier propagates `protected` across `select`, `join`, and `derive`, blocks direct protected effects, prevents disclosure requests from being treated as ordinary data, and checks the declared disclosure destination against the effect destination. The host still requires a purpose-scoped disclosure grant at execution. `output` remains a **trusted local** sink and may contain protected data; the host must enforce any subsequent export. Graph code cannot declare arbitrary sources as public if the host observation labels them protected.

These are narrow structural checks, not a general information-flow theorem. The host controls observation labels and execution metadata; a malicious or mistaken source can lie, and a hash cannot authenticate provenance. There is no proof against timing/covert channels, compromised host code, arbitrary native transforms, or disclosures performed outside this host. Persisted, tamper-evident audit chains and source attestations remain future work.

## Slice 6: heterogeneous examples

`examples/` contains academic, email, payment, home-device, and collaboration graphs. `tests/test_scenarios.py` executes them against host authority, state, and fake effects. Read [SCENARIO_FINDINGS.md](SCENARIO_FINDINGS.md) before treating a passing test as a safe scenario: tests deliberately reproduce missing price freshness, device predicates, multi-principal authorization, and recipient-to-destination consistency.

## Slice 7: hostile extensions

`tests/test_hostile_extension.py` covers the planned rejection matrix and deliberately reproduces three missing boundaries. [HOSTILE_FINDINGS.md](HOSTILE_FINDINGS.md) separates graph-only rejection from host integration gaps and direct Python API forgery. A passing test that demonstrates a gap must not be counted as a defended attack.

## Host-approved package binding probe

`package.py` introduces `PackageManifest` and `PackageRunner` for a trusted host invocation. A host-approved manifest lists exact source names, commit targets, effect kind/destination pairs, and disclosure destination/purpose pairs. Binding snapshots the graph and rejects nodes outside those scopes; running filters an overprovided observation map down to the graph's approved inputs and assigns the host-approved producer/version. `tests/test_package.py` covers those checks and graph mutation after binding. The host must separately authorize every commit/effect through live grants.

The manifest is not self-authenticating, and this probe is not wired into LifeHub plugin discovery or service APIs. `Interpreter.run` remains directly callable by trusted research code without a manifest. Never expose the raw interpreter, mutable host authority store, effect service, or protected local outputs to arbitrary native extensions.

## What the first slice can and cannot establish

The verifier rejects unknown operations, malformed graphs, invalid dataflow edges, and structurally direct protected effects. The interpreter records traceable proposals, commit requests, disclosures, and effects. The host checks authority, can apply an in-memory state mutation, and can run only fake effects. The interpreter itself neither commits nor executes. Durable persistence, real effect adapters, general information-flow enforcement, and provenance authentication are **not implemented**. A `CommitRequest` is never a commit by itself; a `DisclosureRequest` is never authority.

Threat model for this slice: an untrusted **serialized graph** run by a trusted Python host. Executing arbitrary third-party Python in the host process to construct a graph would bypass this boundary. The model does not claim process isolation, a secure package sandbox, protection from malicious host code, or absence of covert channels.

Next: a feature-comparable WASM Component/WIT baseline, durable authority, and a real provider recovery evaluation before a final Go/No-Go. Do not infer a new-language advantage from these primitives alone; the comparison criteria are in `docs/lifehub/research/PERSON_IR_EXPERIMENT_PLAN.md`.

## Provisional baseline

`baseline.py` and `tests/test_baseline.py` compare the academic and email examples to ordinary host capability calls using the same authority/state/effect services. `wasm_baseline.mjs` separately executes a tiny core-WASM academic module with explicit host imports and denied manifest operations. `durable.py` probes SQLite local commit recovery and conservative effect-intent recovery; the latter is not integrated with a provider. `benchmark.py` probes Python request construction overhead. [BASELINE_COMPARISON.md](BASELINE_COMPARISON.md) records exact scope and a provisional hold on compiler work. The final comparative decision remains open.
