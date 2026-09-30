# PersonIR falsification and experiment plan

**Experiment outcome (2026-09-30):** [scoped decision record](../../../experiments/person_ir/PERSON_IR_DECISION.md) — No-Go for a new PersonIR source language/compiler on the evidence from this prototype. Retain an optional data-only IR for inspectable flows; continue LifeHub as a capability host. The preferred WIT binary comparator and real-provider safety trials remain open follow-up work, and the decision does not claim they were completed. The plan below is preserved as the original evaluation rubric.

## Goal

Determine whether a small PersonIR provides a genuine semantic advantage for LifeHub or merely repackages conventional capability/runtime patterns.

Do not rewrite the current LifeHub v0.2 kernel for this experiment.

## Suggested layout

~~~text
experiments/person_ir/
    README.md
    model.py
    types.py
    verifier.py
    runtime.py
    authority.py
    state.py
    effects.py
    provenance.py
    examples/
        academic.py
        email.py
        payment.py
        home.py
        collaboration.py
    tests/
        test_authority.py
        test_provenance.py
        test_information_flow.py
        test_commit.py
        test_effect_idempotency.py
        test_hostile_extension.py
~~~

Do not introduce a parser/source language in the first slice. Construct IR graphs directly in Python or load minimal JSON.

## Slice 1 — executable semantics

Implement only enough IR to express source/observation, pure transform, join, derived value, proposal, commit request, effect request, declassification, and output.

The runtime should make ambient filesystem/network/process access unavailable to the IR by construction.

Success: a graph runs end-to-end without direct application mutation or direct external effects.

Failure: useful programs immediately require arbitrary callbacks with ambient authority.

## Slice 2 — authority

Represent capabilities/delegations separately from ordinary values.

Minimum fields:

~~~text
capability_id
principal/domain
operation
resource/scope
issuer
issued_at
expires_at?
activation_context?
revoked?
~~~

Tests:

- code cannot manufacture a valid capability from serialized data
- revoked delegation fails at use time
- expired delegation fails
- scope mismatch fails
- own-state read does not imply external effect authority

## Slice 3 — proposal/commit

Represent durable mutation as a proposal with a base state version/hash.

Tests:

- valid proposal commits
- stale proposal rejects
- unauthorized proposal rejects
- recomputation does not create duplicate commits
- rejecting a proposal does not modify evidence/observations

Explicitly compare the implementation to ordinary MVCC/transaction semantics. Record whether POP adds anything beyond naming.

## Slice 4 — effects

Create host-owned effect executors. Start with deterministic fake executors, not real email/payment/device APIs.

Tests:

- effect request alone causes no external action
- missing/revoked authority blocks execution
- same idempotency key does not execute twice
- materially changed inputs require a new effect identity or explicit reauthorization
- failed effect is recorded separately from success
- irreversible effect is never described as rolled back merely because local state changed

## Slice 5 — provenance and information flow

Important derived values/proposals/effect requests should expose enough lineage to identify source observations, transform identities, package/program version, grants/delegations used, declassification steps, and relevant state version.

Verifier tests:

- protected data cannot reach an external sink without an explicit declassification/effect path
- declassification declares destination/scope/purpose
- derived sensitivity propagates across joins
- AI/nondeterministic transforms are marked and record execution metadata

Do not promise perfect provenance for opaque/native computation.

## Slice 6 — heterogeneous examples

### Academic planning

Observed deadline + calendar availability -> proposed study block.

Stress: evidence vs suggestion, stale calendar state, reversible local proposal.

### Email

Personal context + draft + recipient -> send-email effect request.

Stress: intentional egress, declassification, irreversible effect, idempotency.

### Payment/purchase

Order + price observation + payment delegation -> purchase effect request.

Stress: high authority, price/state revalidation, expiry, duplicate prevention. Use a fake executor only.

### Smart home/device

Sensor observation + user policy/delegation -> device effect request.

Stress: time-sensitive authority, physical-world effect, offline/retry behavior. Use a fake executor only.

### Collaboration

Shared state + multiple principals -> shared-state proposal.

Stress: no single-person ownership, conflicting authority, merge/concurrency, and whether PersonalDomain<P> must be generalized.

## Slice 7 — hostile-extension tests

Create invalid IR packages that try to:

- access undeclared state
- synthesize authority
- route protected data to an external sink
- bypass declassification
- replay an executed effect
- commit against stale state
- forge provenance
- request capability outside declared scope

Reject each for an explicit reason. Record every bypass and decide whether it exposes a model flaw rather than merely patching the test.

## Baseline comparison

Implement at least one representative scenario using a conventional capability-limited component model, preferably WASM Component Model/WIT if practical.

Compare:

| Dimension | Question |
|---|---|
| Authority | Is authority explicit and inspectable? |
| Delegation | Can it expire/revoke without changing plugin code? |
| State ownership | Does durable state clearly outlive the extension? |
| Provenance | Can outputs be traced without bespoke instrumentation? |
| IFC | Can illegal egress paths be rejected structurally? |
| Proposal/Commit | Is mutation separated from computation? |
| Effects | Are external actions explicit, idempotent, and auditable? |
| Debugging | Can the system explain why a proposal/effect exists? |
| Complexity | How much framework code is required? |
| Performance | What overhead does the model add? |
| Openness | Can unknown future semantics enter without kernel changes? |

## Decision gates

Continue toward a language/compiler only if:

- at least three heterogeneous scenarios benefit from the same small IR primitives
- hostile tests are rejected without domain-specific kernel rules
- baseline comparison reveals a meaningful semantic/enforcement advantage
- user-facing capability/effect explanations can be derived from the program
- the IR remains small enough that the kernel does not become a life ontology

Stop the new-language effort if:

- most nodes become escape hatches to arbitrary host code
- authority/provenance/effects live mostly outside the IR anyway
- ordinary WASM/WIT + capability APIs are equally clear
- every domain requires new kernel node kinds
- static guarantees are too weak to justify language complexity
- developer ergonomics become substantially worse without compensating benefit

Stopping the language experiment is a valid successful research result.

## Expected artifacts

1. PERSON_IR_SPEC.md
2. executable interpreter/runtime
3. verifier with negative tests
4. five scenario programs
5. baseline implementation
6. comparison report
7. threat model
8. list of disproved/modified claims
9. decision: continue compiler work, reduce scope, or abandon PersonIR

Do not decide item 9 in advance.
