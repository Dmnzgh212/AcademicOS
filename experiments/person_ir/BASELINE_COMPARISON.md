# PersonIR versus the existing capability-limited Wasm host

The executable baseline in `tests/test_baseline.py` installs a core Wasm module
through the existing package approval path. It submits the same reviewed advisor
message payload as the PersonIR email scenario, using the host's `test.record`
fake executor. The manifest permits only `advisor@example.org`; a module asking
for another destination traps without staging an effect. Approval, dispatch,
deduplication and replay refusal occur in the existing LifeHub host. This is a
fixed-payload representative, not a dynamic email adapter or a WIT Component
Model implementation. Both sides perform fake effects only.

| Dimension | PersonIR experiment | Existing core Wasm host |
| --- | --- | --- |
| Authority | Exact opaque in-process handle with principal, scope and use-time check. | Approved package manifest and host grants constrain imports/targets; host checks on request and dispatch. |
| Delegation | Handle expiry, revocation and activation context are explicit. | Grants and package approval can be revoked; the current baseline does not demonstrate equivalent expiry/context for effects. |
| State ownership | Separate versioned SQLite store survives graph evaluation. | LifeStore persists beyond a Wasm invocation; proposals survive restart. |
| Provenance | Source/producer/version/node trace travels with requests, subject to honest host evidence. | Package identity and request records exist; equivalent input lineage needs extra host instrumentation. |
| Information flow | Verifier rejects protected-to-sink paths without matching whole-value release. | No static data-flow labels; manifest destination limits do not prove what data was disclosed. |
| Proposal/commit | Graph emits a request; versioned host commits separately. | `propose_json` stages a change; separate host review/commit. |
| Effects | Graph emits a request; host ledger approves, dispatches once and records uncertainty. | `request_effect_json` stages a request; host review, fake dispatch and deduplication. |
| Explanation | Trace explains graph steps and source evidence, but whole-value release can overdisclose. | Manifest and request explain target/purpose; causal input explanation needs custom logging. |
| Complexity | New verifier, interpreter, authority, stores and provenance vocabulary, plus a host binding still needed. | Existing core Wasm package/runtime/manifest APIs; dynamic data transformation belongs in component code. |
| Performance | No representative throughput benchmark; Python graph tests alone cannot support a speed claim. | Fuel and memory limits exist; this small fixed WAT test is not a comparable benchmark. |
| Openness | Unknown computations require new verified ops or host observations; `join` merely packages values. | General component computation runs in sandbox under a narrow set of host imports. |

## Modified and disproved claims

- “Proposal/commit and effect separation require a new language” is disproved
  by the existing Wasm host and its tests.
- “Graph labels provide structural egress checks” holds within verified graph
  data, but depends on trusted host labels, whole-value release and an
  authenticated interpreter output. `HOSTILE_FINDINGS.md` demonstrates native
  intent reconstruction with a falsely preserved trace.
- “One small IR handles five domains” is true only as request plumbing. Planning,
  price freshness, sensor freshness and joint authority remain host/domain work.
- No performance or developer productivity advantage has been measured.

## Decision

**Reduce scope: do not start a new PersonIR compiler now.** Keep the existing
Wasm capability host as the executable plugin boundary. Consider the graph
verifier and trace vocabulary as an optional declarative policy/workflow layer
for limited flows, after binding evaluation results to trusted host snapshots
and comparing the same dynamic scenario with a Wasm component. This decision
can change if a later benchmark demonstrates enforcement or explanation that
the conventional host cannot reasonably reproduce.

The implementation is core Wasm with explicit imports, not WIT Component Model.
The baseline therefore answers the practical current-host question while
leaving Component Model ergonomics for a separate comparison. It does not
authorize real email, payment or device effects.
