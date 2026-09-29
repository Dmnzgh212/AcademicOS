# Slice 6 — heterogeneous scenario findings

Status: executable counterexamples against the current small IR, not a POP validation or product security assessment. All external actions use in-memory fake executors. Reproduce with `python -m unittest discover -s experiments/person_ir/tests -v`.

| Scenario | What works with common primitives | Observed limit |
|---|---|---|
| Academic planning | Two observations become a local proposal. Versioned commit rejects a stale alternative; evidence remains distinct. | No calendar conflict or time-constraint solver; the example proposes a pair of values, not a validated schedule. |
| Email | Protected context passes through an explicit disclosure request, exact destination/purpose grants, a fake effect, and replay ledger. | A recipient *value* in the payload can disagree with the graph's configured destination. The verifier has no dependent relation tying them together. |
| Payment | Order and observed price become a protected purchase request; effect and disclosure grants are checked. | A newer quote can exist while an old price is still executed. A destination-scoped grant lacks amount/currency ceilings and fresh quote binding. The fake executor must not be mistaken for a safe purchase implementation. |
| Smart home | A nondeterministic sensor observation and policy value become an auditable fake device request. | The graph lacks a predicate: a below-threshold reading still produces an action. Old sensor data remains executable under a non-expiring grant. Physical-world timing and acknowledgement require host checks. |
| Collaboration | A shared domain can store a proposed change with version checking. | Approval strings are ordinary, unverified data. A single principal's grant can commit to the shared domain; no joint authority/quorum or merge policy is expressed. |

## Consequence for the hypothesis

The same small graph and request primitives can **represent data movement** in five domains. That is weaker than safely expressing the decision rules in five domains. The academic and email paths demonstrate some usable separation of computation and authority, but the email recipient mismatch remains unresolved. Payment, devices, and shared state expose material missing semantics. Counting these examples as five successful security demonstrations would be false.

Do not add `Payment`, `Thermostat`, or `Course` node kinds to make the tests green. Investigate generic, inspectable preconditions (freshness, equality and bounded values), effect-specific policy at the host, and multi-principal authorization. Each candidate must be tested against an ordinary capability-limited component host. If the needed logic mostly lives in host adapters and policies, this weighs against a new PersonIR language.

These examples do not test untrusted native execution, source authenticity, durable recovery, or real provider idempotency. They also do not provide a conventional-runtime baseline. The Go/No-Go decision remains open.
