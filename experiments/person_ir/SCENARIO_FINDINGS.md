# Slice 6 — heterogeneous scenario findings

Status: executable counterexamples against the current small IR, not a POP validation or product security assessment. All external actions use in-memory fake executors. Reproduce with `python -m unittest discover -s experiments/person_ir/tests -v`.

| Scenario | What works with common primitives | Observed limit |
|---|---|---|
| Academic planning | Two observations become a local proposal. Versioned commit rejects a stale alternative; evidence remains distinct. | No calendar conflict or time-constraint solver; the example proposes a pair of values, not a validated schedule. |
| Email | Protected context passes through an explicit disclosure request, exact destination/purpose grants, a fake effect, and replay ledger. | A recipient *value* in the payload can disagree with the graph's configured destination. The verifier has no dependent relation tying them together. |
| Payment | Order and observed price become a protected purchase request; effect and disclosure grants are checked. | A newer quote can exist while an old price is still executed. A destination-scoped grant lacks amount/currency ceilings and fresh quote binding. The fake executor must not be mistaken for a safe purchase implementation. |
| Smart home | A nondeterministic sensor observation and policy value become an auditable fake device request. | The graph lacks a predicate: a below-threshold reading still produces an action. Old sensor data remains executable under a non-expiring grant. Physical-world timing and acknowledgement require host checks. |
| Collaboration | A shared domain can store a proposed change with version checking. | Approval strings are ordinary, unverified data. A single principal's grant can commit to the shared domain; no joint authority/quorum or merge policy is expressed. |

## Follow-up host policy probes

`policy.py` adds a **host-approved optional gate** for new effects: bounded numbers, field comparisons, destination equality, and fresh current evidence bound to an effect payload and source reference. The same rule types reject the email recipient mismatch, payment above a ceiling or against a changed/old quote, and a below-threshold or stale sensor command. `EffectService` and `DurableEffectService` evaluate a configured policy after live grant and request-integrity checks but before a new fake action; receipt replay still requires authority and does not repeat a decision against current evidence. The original unconfigured services remain permissive in the counterexample tests.

`joint.py` adds a trusted shared-domain gate requiring separate live commit grants from two specified principals. The `approvals` payload strings cannot stand in for either handle. `StateStore.commit` now verifies all co-signers while holding its authority/state locks and writes their grant IDs into the same receipt as the state mutation. A `DurableStateStore` restart retains both IDs, and replay rechecks the same number of distinct principals. This is a durable audit of **which grants were checked**, not proof that the people personally approved the content.

These remedies are **host policy**, available to PersonIR and conventional components alike. The host must supply authentic current evidence, approve policy rules and require the joint gate for shared-domain mutations. A direct trusted-host call to `StateStore.commit` can still create a new shared-domain commit with one grant. No source attestation, provider-side freshness, external-state transaction, cross-process revocation/action atomicity, or general multi-person governance is demonstrated. A predicate in a graph alone would not resolve these use-time requirements.

## Consequence for the hypothesis

The same small graph and request primitives can **represent data movement** in five domains. That is weaker than safely expressing the decision rules in five domains. The academic and email paths demonstrate some usable separation of computation and authority; an optional host policy now rejects the email recipient mismatch. Payment, devices, and shared state still require trusted, use-time evidence and governance. Counting these examples as five successful security demonstrations would be false.

Do not add `Payment`, `Thermostat`, or `Course` node kinds to make the tests green. The generic host checks cover the named examples but need a trusted evidence and policy lifecycle, enforced shared-domain routing, and comparison against a general isolated component ABI. Their location in the host currently weighs against a unique PersonIR-language advantage.

These examples do not test untrusted native execution, source authenticity, durable recovery, or real provider idempotency. They also do not provide a conventional-runtime baseline. The Go/No-Go decision remains open.
