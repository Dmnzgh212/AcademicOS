# PersonIR experiment — slices 1–3

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

## What the first slice can and cannot establish

The verifier rejects unknown operations, malformed graphs, invalid dataflow edges, and structurally direct protected effects. The interpreter records source references, proposals, commit requests, disclosures, and effects. The host checks authority and can apply a local state mutation in slice 3. The interpreter itself never commits. Effect executors, effect idempotency, persistence, robust information flow, and provenance authentication are **not implemented**. A `CommitRequest` is never a commit by itself; a `DisclosureRequest` is never authority.

Threat model for this slice: an untrusted **serialized graph** run by a trusted Python host. Executing arbitrary third-party Python in the host process to construct a graph would bypass this boundary. The model does not claim process isolation, a secure package sandbox, protection from malicious host code, or absence of covert channels.

Next: host-owned fake effect executors and their idempotency ledger (slice 4). Before language work, compare with a conventional capability-limited runtime as specified in `docs/lifehub/research/PERSON_IR_EXPERIMENT_PLAN.md`.
