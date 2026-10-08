# Authority semantics — stage-zero executable model

Research only. No LifeHub Core imports, runtime dependency, upstream source copy,
compiler, real Wasm execution, personal data or external effects.

```sh
python research/authority_semantics/compare.py results.json
```

`compare.py` runs six synthetic fixture families through one shared abstract host:
sequential API operations (a B1 proxy) and a dependency-ordered graph (an R proxy).
Input graph storage order is reversed; explicit dependencies restore the intended
order. Operator-originated observation/grant/revoke/replacement fixtures are
trusted test orchestration, not powers given to untrusted graph nodes. Guest
claims of labels or grant authority cannot override the host-owned records.

Both frontends deliberately use the same checks. Equal traces are an equivalence
sanity check, not independent evidence that a real language or runtime is secure.
The graph has no static information-flow verifier and is **not PersonIR**. B1 is
an abstract metadata/API model, **not an executed Wasm/WIT baseline**. B0 production
behavior is not executed here. The fixture families are test scenarios, not real
plugins or evidence of independent integration.

## Observed result

All six fixture families satisfy their specified expected denials and selected
positive invariants. Sequential and graph results match:

| Family | Observed model property |
| --- | --- |
| Observation/proposal | Rejection changes the proposal, preserves the observation; rejecting evidence is denied. |
| Derived mail | Guest-claimed public/evidence metadata cannot erase inherited ownership or derived kind; disclosure denied. |
| Shared note | One owner's disclosure permission is insufficient; both modeled grants allow the synthetic release. |
| Payment | Read grant does not authorize effect execution; guest self-grant denied. |
| Device | Revocation denies execution; regrant permits modeled unknown result; retry remains denied. |
| Replacement | Effect snapshot bound before replacement cannot execute afterward. |

The checked-in `results.json` preserves fixtures, exact traces, final modeled
records and effect states for reproduction. A passing model trace is not proof
of noninterference, cryptographic identity, revocation during concurrent execution,
real-world observation truth or executor reliability. No authoring productivity,
performance or unique IR benefit has been measured.

## Why this result matters, and what it does not establish

These selected properties can be expressed in ordinary host-mediated metadata
and policy checks in a closed model. There is no demonstrated need for a new
language from these cases. Because the two frontends share the host and operation
set, this experiment cannot prove that equivalent arbitrary Wasm programs are
safe or that one approach is easier for independent developers.

The next useful comparison must use actual implementations with matched trusted
facts and host mechanisms, then independently authored tasks and adversarial
label/check omissions. In particular: control/implicit flows, untracked bytes,
unknown operations, hostile host bindings, alternate authorization paths and
multi-person policy conflict are **not modeled**. The selected all-owners rule is
one synthetic policy, not a settled multi-person consent model.

Keep comparison failures and conventional solutions. Do not weaken the ordinary
baseline to create an apparent IR advantage. Do not promote this miniature host
into the production Engine or replace mature authorization libraries with it.
M1 independent integration and acceptance remain separate.
