# PersonIR executable subset — specification of the current prototype

Status: descriptive specification of `model.py`, `verifier.py`, `runtime.py`, and their host services as of the current experiment. This document is **not** a proof that the implementation satisfies a security theorem or a proposal for a new source language. The experiment plan is `docs/lifehub/research/PERSON_IR_EXPERIMENT_PLAN.md`.

## Boundary and data model

A program is an ordered tuple of `Node(id, op, inputs, config)`. The JSON loader admits at most 1,000 nodes in text of at most 1,000,000 characters, rejects duplicate JSON keys and non-finite JSON constants, and calls `verify`. A Python `Graph` constructor is for trusted experiments; `Interpreter.run` still calls `verify`. Runtime observations must contain JSON-compatible values of depth at most 32. These are input checks, not a general resource or time budget.

The interpreter receives a graph, a trusted observation map, a nonnegative state `base_version`, a nonempty `producer` (program/version identifier), and a nonempty `intent_id`. The graph does not receive capability handles, a state store, an executor, filesystem, process, or network API. The host controls which observations are supplied. `PackageRunner` can snapshot a graph under a separately host-approved manifest and filter the supplied map; this boundary is not yet required by LifeHub's real loader.

`Value = (data, label, sources, trace)`, where `label ∈ {public, protected}`, `sources` is a set of host-provided source strings, and `trace` is an ordered sequence of `TraceStep`s. Source strings, labels, execution metadata, and the manifest's producer are **claims supplied by the trusted host**, not authenticated statements from a device, AI model, or external service. A `Proposal`, `DisclosureRequest`, `CommitRequest`, or `EffectRequest` is inert data until a host API checks it and acts.

## Static graph judgment

Write `Γ ⊢ n : (kind, label)` for the result of checking node `n` against previously accepted nodes `Γ`. Nodes are checked in order, so every input ID must already appear and each node ID must be unique. The verifier enforces exact arity and exact config-key sets:

| Operation | Inputs | Configuration | Result and label rule |
|---|---:|---|---|
| `source`, `nondeterministic_source` | 0 | `name`, `label` | Ordinary data; declared `public` or `protected` |
| `select` | 1 data | `key` | Ordinary data; preserve parent label |
| `join` | 2 data | none | Ordinary pair; `protected` if either input is protected |
| `derive` | 1 data | none | Ordinary copy; preserve parent label |
| `propose` | 1 data | `target` | Inert proposal, not ordinary data |
| `commit_request` | 1 proposal | none | Inert commit request |
| `declassify` | 1 data | `destination`, `purpose` | Inert disclosure request |
| `effect_request` | 1 data or disclosure | `kind`, `destination` | Inert effect request; protected data needs disclosure whose destination matches |
| `output` | 1 data or request | none | Local result for the trusted caller |

All configuration values must be nonempty strings. A request is never an ordinary data input to `select`, `join`, `derive`, `propose`, or `declassify`. A protected `Value` cannot feed `effect_request` directly. The verifier checks a **declared flow path** only. It does not check that a recipient field inside a payload equals the destination, authenticate source labels, or prevent the trusted caller from leaking a protected `output` afterward.

## Evaluation rules

Evaluation maps previously computed node IDs to results and runs each node once in graph order. It makes copied JSON data, not executable callbacks. The following rules describe the prototype's consequential behavior:

1. `source` fetches `observations[name]`, checks its label and nonempty source string against the declaration, copies its JSON value, and records a source trace step. `nondeterministic_source` additionally requires nonempty execution ID and engine strings; it does not run the engine.
2. `select` copies the named key of an object. `join` creates a two-element list and unions source sets. `derive` copies its input; there is no arbitrary transform or conditional expression in this subset. Traces retain upstream steps and append the current step.
3. `propose` copies data, records `base_version`, and hashes producer, node, target, value, version, sorted sources, and trace into `proposal_id`. `commit_request` wraps that proposal. These steps do not mutate state.
4. `declassify` copies data into a request with a destination, purpose, sources, and trace. It does not remove sensitivity or release data. `effect_request` on that request constructs a protected effect; on public data it constructs a public effect. Its hash includes producer, node, intent, kind, destination, payload, label, disclosure purpose, sorted sources, and trace. These steps do not call an external service.
5. `output` places the computed object into the local `RunResult.outputs`. A trusted caller can see a protected result; the interpreter does not mediate subsequent use by that caller.

The SHA-256 IDs identify exact material inputs under the specified JSON encoding. They are neither signatures nor evidence of authentic provenance. A caller with direct Python service access can construct data and calculate matching IDs. The traced source and producer fields are therefore useful for explanation and debugging under the trusted-host assumption, not a proof of where an observation came from.

## Host transition contract

The execution boundary is `request -> host checks -> host operation -> receipt`. Relevant invariants of the present implementation are:

| Host transition | Preconditions checked at use | Successful local transition | Replay / unresolved outcome |
|---|---|---|---|
| State commit | Live scoped commit grant(s), proposal hash/content, base version; configured `required_principals` checked even for a direct call | Update one local target/version and store an audit receipt; durable variant stores state and receipt in one SQLite transaction | Existing proposal receipt replays only after live grant checks. A stale new proposal rejects. `shared:` domains require a configured principal list. |
| Effect execution | Live scoped effect grant, separate purpose/destination disclosure grant for protected data, effect hash/content; optional host policy for a **new** action | Call an explicit fake executor after checks, then record `succeeded`, definite `failed`, or `unknown` receipt | Completed receipt replays after live grants. Durable pending intent blocks retry. A trusted query of the separate fake provider ledger can reconcile only a matching recorded action; absent proof stays unknown. |

Authority IDs and descriptions are audit metadata. The process-local handle object is the credential; the trusted authority registry issues it. The durable registry creates fresh handle objects on startup and reads revocations at check time. The host must authenticate its own startup, principals, issuer, and distribution of restored handles; this prototype does not implement those steps.

Local state atomicity and fake provider reconciliation do not imply atomicity between a host process, a second process, and a real provider. A different `intent_id` creates a different effect identity and can describe another action. Host policy rules and the `shared:` naming convention are conventional host controls available to a component model too; neither follows intrinsically from the graph grammar.

## Conformance and open proof obligations

The runnable evidence is `python -m unittest discover -s experiments/person_ir/tests -q`, `HOSTILE_FINDINGS.md`, `SCENARIO_FINDINGS.md`, and `BASELINE_COMPARISON.md`. Tests cover selected examples and negative cases, not all graphs or all host integrations. The next comparison needs a general isolated component ABI, an explicit policy/evidence issuance lifecycle, real provider status/idempotency behavior, integration with LifeHub entry points, and an argument about any advantage over the conventional host API. See `THREAT_MODEL.md` for attacker control and failed claims.
