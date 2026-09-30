# PersonIR prototype threat model and claim ledger

Status: experiment-only boundary. The target is an untrusted **serialized graph** evaluated by a trusted Python host. The host approves package scopes, supplies observations and labels, authenticates principals outside this prototype, issues opaque handles, owns policy/state/effect services, and decides where local outputs go. The prototype is not integrated into LifeHub's production loader or service entry points.

## Assets, attackers, and trust assumptions

Assets are protected observations and outputs, authority handles, local state and commit receipts, effect intents and receipts, and the user's control over external effects. An untrusted graph author can choose node IDs, supported operations, configuration strings, and dependencies in JSON. A caller might submit a malformed graph, request a protected sink, replay a request, change a request after construction, or claim a source/approval. They cannot invoke a Python callback *through the serialized IR* or receive host registry objects through its value grammar.

The trusted host, its Python process, SQLite files, policy configuration, provider adapter, and observation suppliers are outside the defended boundary. A malicious native Python plugin in that process, a compromised host, a tampered SQLite file, a dishonest observation supplier, or a malicious real provider violates those assumptions. No claim is made about process isolation for Python code, denial of service, side channels, or authenticity of observations. Core-WASM academic/email probes exercise explicit imports, but do not yet establish a general Component/WIT sandbox or end-to-end service integration.

## Attack-to-enforcement map

| Attack or failure | Current outcome | Responsible boundary and remaining limit |
|---|---|---|
| Unknown op, forward reference, malformed graph, callback value | Rejected in the graph/JSON/runtime subset | Fixed grammar and JSON copying. Resource exhaustion within admitted graphs has not been bounded generally. |
| Undeclared observation or action scope | Rejected through `PackageRunner` | Requires a trusted, approved manifest and use of that entry path. Raw trusted APIs are still callable by host code. |
| Direct protected data to effect, or mismatched disclosure destination | Rejected at verifier; host checks scoped grants again | Protected local `output` remains visible to its trusted caller; payload-field relations require host policy. |
| Fabricated grant ID or old handle after restart | Rejected by authority store | Issuer authentication and safe handoff of fresh handles are not implemented. |
| Stale state proposal, replay after grant revocation | Rejected at host commit boundary | Local lock/SQLite transaction only; no multi-service distributed transaction. |
| One-grant shared commit through direct storage call | Rejected for a configured domain and automatically required for `shared:` names | Policy is trusted host configuration. No personal approval proof, general quorum, conflict merge, or LifeHub-wide domain registry. |
| Effect replay after a completed receipt or pending interruption | Does not repeat action for the same ID | A new intent ID can represent another action; real providers need their own idempotency and trustworthy status queries. |
| Host crash after simulated provider action and before receipt | `unknown` until matched fake provider record is queried | Separate local SQLite simulator only. Missing record, old metadata, and inconclusive provider replies stay unknown. |
| Forged provenance with a freshly computed hash from native service access | **Succeeds if the caller already reaches trusted service APIs and valid handles** | Hashes bind content but do not authenticate its origin. Isolate service APIs and bind requests to a trusted session before broadening attacker control. |
| Stale/false quote, sensor reading, or approval string | Conditional host policy can reject named stale/mismatched examples; authenticity remains open | Host must source and validate evidence, configure rules, and handle current provider state. |

## Claims retained, narrowed, and rejected

| Claim | Disposition based on evidence |
|---|---|
| “The graph cannot directly perform state mutations or external effects.” | Supported **for the closed serialized-graph operator set**; requests require separate host calls. |
| “A protected flow to a declared external effect must pass a disclosure request.” | Supported **structurally** for this graph grammar; end-to-end noninterference is unproved because local outputs and host behavior remain outside it. |
| “Trace hashes prove an authentic source or a person's approval.” | Rejected. Host metadata is asserted, not attested; hashes are reproducible. |
| “The local commit is versioned, audited, and checked against live grants.” | Supported in the tested host services, including the durable SQLite variant. This is conventional MVCC/capability design. |
| “Shared writes require independent principals.” | Supported for `shared:` stores with host-configured principals and their tested direct/restart paths; not established across all LifeHub domains. |
| “External effects are exactly once.” | Rejected as a general claim. Same-ID replay is blocked in the fake host; the local provider simulator can reconcile one interrupted action. Real provider semantics remain unknown. |
| “PersonIR warrants a new language/compiler.” | Not supported by the current baseline. [The scoped decision](PERSON_IR_DECISION.md) is No-Go for a new compiler now; reopen only after affirmative comparative evidence. |

## Remaining falsification gates

1. Compare a general isolated component interface with the same grants, policy, effects, trace explanations, and examples. Measure complexity and developer work alongside overhead.
2. Demonstrate trusted evidence origin and policy approval/versioning at actual host entry points, including protected-output handling and request/session binding.
3. Exercise cross-process revocation and a real provider's idempotency and status query, including outages and ambiguous responses. Never infer a failed action solely from an absent response.
4. Reopen the [No-Go decision](PERSON_IR_DECISION.md) only if new evidence shows an advantage in at least three heterogeneous scenarios under a comparable isolated host.

This ledger is evidence-limited. Passing local tests narrows the threat model; it does not make the open gates true.

## Reproducible evidence index

| Tested boundary | Closest executable evidence |
|---|---|
| Graph grammar, protected sink, forged hash gap | `tests/test_hostile_extension.py`, `tests/test_slice1.py`, `tests/test_provenance_flow.py` |
| Approved manifest and filtered inputs | `tests/test_package.py` |
| Host policy and heterogeneous counterexamples | `tests/test_policy.py`, `tests/test_scenarios.py` |
| Shared principal policy, persistence, and legacy denial | `tests/test_joint.py` |
| Durable intent, fake provider query, absent record, and revoked replay | `tests/test_durable_effect_service.py` |
| Narrow core-WASM boundary and restart probes | `tests/test_recovery_wasm.py`, `tests/test_wasm_bridge.py` |
| Shared core-WASM host imports for academic and email | `tests/test_wasm_generic.py` |

Run from repository root: `python -m unittest discover -s experiments/person_ir/tests -q`. The test names and assertions, rather than this summary, define what was actually exercised.
