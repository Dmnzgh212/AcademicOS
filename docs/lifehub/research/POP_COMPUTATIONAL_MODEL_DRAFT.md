# POP computational model — draft 0

Status: research hypothesis, not a settled language design.

## Research question

What changes if the persistent unit of digital state, authority, provenance, and accountability is a person-associated computational domain rather than an application?

The formal object is a digital domain associated with a person; it is not a definition of the human being.

## Core domain

~~~text
D_P = <IdentityRef, State, History, Authority, Policy>
~~~

A program should not receive D_P wholesale. It receives a capability-limited view.

~~~text
View_P(D_P, C)
~~~

## Candidate primitives

### Observation<T, Source>

A value observed from a source at a time, with provenance. It is not automatically trusted, interpreted, or accepted as personal intent.

### Derived<P, T, Provenance>

A value computed from observations and/or other authorized local values. Its lineage must be representable.

### Capability<P, Operation, Scope>

Runtime authority for a scoped operation. Static analysis may track requirements, but runtime possession and validity remain authoritative.

### Delegation<P, Agent, Capability>

A grant derived from person-associated authority allowing an agent to exercise a capability under explicit scope, policy, and optional expiry/activation conditions. Delegation must be revocable.

### Proposal<P, Transition>

A requested durable state transition. Producing a proposal is computation; it is not a commit.

A proposal should normally carry target state/domain, base version/hash, transition, producer/version, provenance, required authority, preconditions, and a stable identity where needed.

### Commit

Host-owned operation validating a proposal against current state, policy, and authority.

~~~text
Commit(D_P, Proposal, AuthorityContext) -> D'_P | Rejected
~~~

### EffectRequest<P, Effect>

A requested interaction with an external system or physical world. Producing an EffectRequest does not mean the effect occurred.

### EffectReceipt

A durable record of attempted/authorized external effect execution, including idempotency identity, relevant inputs, authority, executor, result, and external receipt/reference where available.

### Declassify<P, T, Destination, Purpose>

An explicit authorized path allowing protected personal information to cross a confidentiality/egress boundary under declared scope.

## Candidate program semantics

~~~text
Program_P :
    (AuthorizedView_P, Inputs, Capabilities)
      -> (DerivedValues, Proposals, EffectRequests)

Commit(State_P, Proposal, Authority_P) -> State'_P

Execute(EffectRequest, DelegatedAuthority_P, Policy) -> EffectReceipt
~~~

## Epistemic/authority separation

~~~text
Observation
    ->
Interpretation / Derived
    ->
Proposal
    ->
Authority
    ->
Commit / Effect
~~~

Rejecting a proposal must not rewrite an observation. Accepting a proposal must not retroactively turn an inference into evidence.

## Candidate invariants

These are hypotheses to test, not proven properties.

- No ambient authority: IR code starts without unrestricted filesystem, network, process, device, secret, or cross-domain state access.
- Authority cannot be synthesized from ordinary data.
- Computation is not commitment: durable mutation passes through host-owned commit.
- External/physical effects are explicit effect requests executed by host-owned executors.
- Durable personal state can outlive individual applications/extensions.
- Important derived values and proposals preserve inspectable provenance.
- Delegated automation authority is independently revocable.
- Protected personal information has no silent egress path; disclosure is explicit and authorized.

## Threat-model boundary

Initial experiments may assume untrusted extension code but a trusted LifeHub kernel/runtime/verifier, constrained OS capabilities, authenticated package identity, and host-owned effect executors.

Do not claim protection against a compromised kernel/OS, hardware attacks, arbitrary covert/timing channels, physical observation, or a malicious external service after authorized disclosure unless specifically demonstrated.

## Stale proposals

Bind proposals to a base state version/hash and optional preconditions.

At commit time, stale proposals must be rejected, explicitly rebased, or recomputed. Silent application against materially changed state is unsafe.

## Incremental recomputation and effects

Recomputing an EffectRequest must not imply repeating the effect.

The runtime must distinguish:

1. computing an effect request
2. authorizing it
3. executing it
4. recording/observing its result

Use stable effect identities/idempotency keys. An effect ledger improves auditability but cannot undo irreversible outside-world actions.

## Multi-person state

A single PersonalDomain<P> is insufficient for collaboration.

Shared resources need an authority model that does not pretend one participant owns all state. The experiment should be willing to generalize or reject the single-person abstraction if collaboration breaks it.

## Determinism

Treat wall-clock time, randomness, network observations, model/AI outputs, and sensor readings as explicit inputs/effects rather than hidden ambient state.

AI outputs should carry execution provenance where practical and should not be assumed deterministic.

## Relationship to conventional systems

This model intentionally reuses transactions/version checks, capability security, effect systems, information-flow control, event/provenance systems, sandboxing, and dataflow/incremental computation.

The research question is whether their composition around a person-associated durable domain creates a useful thin waist that is materially clearer or more enforceable than a conventional capability host.

If not, do not preserve the abstraction for branding reasons.

## Minimal PersonIR candidate

Do not freeze syntax. Start with a tiny graph/IR.

Possible node classes:

~~~text
Source
Transform
Filter
Join
Aggregate
StateView
Derive
Propose
Effect
Declassify
Emit
~~~

Possible edge metadata:

~~~text
schema
provenance
security_label
authority_requirements
~~~

Possible node metadata:

~~~text
inputs
outputs
required_capabilities
determinism
effect_class
producer/version
~~~

## Static versus dynamic enforcement

Depending on how restrictive the IR is, static verification may check interface/schema existence, declared capability classes, illegal protected-data sinks, explicit declassification, structural proposal/effect boundaries, and some provenance completeness.

Runtime enforcement still likely owns capability validity/revocation, state preconditions, dynamic scope, delegated authorization, rate limits, credential use, actual network/device access, idempotency, and process isolation.

Do not promise absence of all covert channels, rollback of external effects, exact permission inference for unrestricted code, or safety against a compromised trusted computing base.

## Falsification criterion

PersonIR earns further investment only if it makes important properties materially enforceable and inspectable while being simpler or more reliable than ordinary WASM/capability components plus host policy.

Otherwise keep LifeHub open and capability-based without inventing a new language.
