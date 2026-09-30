# Slice 7 — hostile extension matrix

Status: experimental Python host with untrusted **serialized graphs**. `test_hostile_extension.py` records the exact observed behavior. A passing test marked **gap** reproduces undesired behavior; it is not a security success.

| Attempt | Result | Enforcement point or missing boundary |
|---|---|---|
| Undeclared state read node or arbitrary Python/network callback | Rejected | JSON graph verifier has no such op. There is no graph-level state-view API. |
| Capability fabricated from serialized ID/metadata | Rejected | Host registry requires an issued, process-local object handle; metadata is not authority. |
| Protected data directly to external effect | Rejected | Verifier propagates protected label and requires a disclosure request. |
| Disclosure to a different destination | Rejected | Verifier requires effect and disclosure destinations to match; runtime grant also scopes purpose. |
| Effect replay and resource scope mismatch | Rejected | Live grant check precedes ledger replay; a matching effect ID has one fake action. |
| Stale state commit | Rejected | Host compares proposal base version against current local version. |
| Change provenance after request construction without changing ID | Rejected | Request identity includes the trace. |
| Read an observation the host supplied but the package never declared | **Rejected by PackageRunner; raw API gap** | The host-approved package binding rejects undeclared graph sources and passes only referenced approved observations. Direct `Interpreter.run` still accepts any matching observation map. |
| Request an operation absent from a package manifest | **Rejected by PackageRunner; raw API gap** | Binding checks commit targets, effect kind/destination, and disclosure destination/purpose independently of live grants. Direct `Interpreter.run` and direct service calls do not enforce a package manifest. |
| Forge a request and matching provenance hash through direct Python service access | **Gap outside the graph-only threat model** | The hash is publicly recomputable, not a signature. If an untrusted native plugin can call `EffectService` with a valid grant, it can manufacture lineage and payload. The host must isolate that API and authenticate interpreter-issued requests before expanding the threat model. |

## Decisions and remaining risk

Do not claim that the graph verifier proves end-to-end security. It checks a small, closed operator set; the host supplies the observation map and labels, issues grants, owns services, and controls which outputs reach plugins. `PackageRunner` now demonstrates manifest and authorized-input binding for a trusted host invocation, but is not integrated into the LifeHub loader or host service entry points. A package cannot self-approve a manifest; the host must review and store the approved scopes. The direct API forgery is an explicit reason not to run untrusted Python in the trusted host process.

Other known failures from [SCENARIO_FINDINGS.md](SCENARIO_FINDINGS.md) remain: recipient/destination equality, price freshness and amount ceilings, device predicates/freshness, and multi-principal shared authority. None is repaired by renaming a node or hashing more metadata.

This completes the **planned seven slices** plus a narrow manifest-binding probe, not the experiment's decision gate. A feature-comparable isolated component baseline, meaningful comparative measurements, durable authority/provider recovery, and a written Go/No-Go assessment are still required. The current evidence does not justify building a new source language or compiler.
