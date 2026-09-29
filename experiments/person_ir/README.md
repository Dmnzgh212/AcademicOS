# PersonIR experiment — slice 1

This is an isolated falsification experiment, not a source language or a replacement for the LifeHub kernel. Run `python -m unittest discover -s experiments/person_ir/tests -v` from the repository root. `examples/academic.py` computes a local study-block proposal from two host observations.

## Executable contract

- The host supplies `Observation(value, source, label)` and a state `base_version`. `Graph.from_json(text)` loads `Node(id, op, inputs, config)` records in topological order. No node can hold a user-defined transform or callback. Inputs are restricted to copied JSON values. A Python constructor is also available for trusted experiments.
- `source`, `select`, `join`, and `derive` produce values. `join` propagates protected labeling and unions source references. `propose` produces an inert state proposal; `commit_request` produces an inert request. Neither writes state.
- `declassify` creates an inert disclosure request with a destination and purpose. It **does not authorize disclosure**. `effect_request` creates an inert request; a protected payload requires a matching disclosure request. No node executes network, file, process, payment, email, or device operations.
- `output` is a local result delivered to the trusted caller, including protected values. It is not an external sink; the host must not expose local results to plugins or network without policy checks.

## What the first slice can and cannot establish

The verifier rejects unknown operations, malformed graphs, invalid dataflow edges, and structurally direct protected effects. The interpreter records source references, proposals, commit requests, disclosures, and effects. Host-owned authorization, state version checks, effect executors, idempotency, persistence, robust information flow, and provenance authentication are **not implemented**. A `CommitRequest` is never a commit; a `DisclosureRequest` is never authority.

Threat model for this slice: an untrusted **serialized graph** run by a trusted Python host. Executing arbitrary third-party Python in the host process to construct a graph would bypass this boundary. The model does not claim process isolation, a secure package sandbox, protection from malicious host code, or absence of covert channels.

Next: capability handles issued and checked by the host (slice 2), followed by versioned commits and effect ledgers. Before language work, compare with a conventional capability-limited runtime as specified in `docs/lifehub/research/PERSON_IR_EXPERIMENT_PLAN.md`.
