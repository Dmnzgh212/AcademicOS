# Authority semantics — stage-zero executable model

Research only. No LifeHub Core imports, runtime dependency, upstream source copy,
compiler, personal data or external effects. The stage-zero model below does
not execute Wasm; the separate stage-one probe does, with a custom research ABI.

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

## Stage one: real core-Wasm implicit-flow probe

```sh
python -m pip install 'wasmtime>=36,<37'
python research/authority_semantics/wasm_flow.py wasm-results.json
```

`wasm_flow.py` uses the existing Wasmtime major-version baseline, without imports
from LifeHub Core. A custom research host supplies a synthetic bit and observes
released i32 values in memory. No network, filesystem/WASI or real effect API is
linked into guests. Module fuel and store limits are applied; no OS containment
or timing-side-channel guarantee is claimed.

| Experiment | Observed output | Interpretation |
| --- | --- | --- |
| Secret-dependent branch emitting literal 0/1, literal-only negative control | [0] versus [1] | This deliberately incomplete host leaks the synthetic bit through control dependence. It is not a fair conventional baseline or an identified production bug. |
| Same guest, conservative execution-wide private label, no delegation | [] for both bits | An ordinary host can block this observed release without a new language. |
| Read/drop private bit, emit constant 7, conservative label | [] for both bits | Conservative tracking rejects this value even though it is independent of the bit in this specific module. Precision costs need evaluation. |
| Emit constant 7 without private access | [7] | Public-only execution remains usable. |
| Branch with explicitly delegated disclosure | [1] | Authorized disclosure is distinct from a leak. |
| Trusted test revokes before output check | [] | Already processed revocation prevents release; this is not concurrent revocation testing. |

The WAT sources and nine exact runs are retained in `wasm_flow_results.json`.
The negative control is deliberately broken to validate that the probe can see a
leak; **no superiority claim may use that negative control as B1**. The meaningful
ordinary baseline here is the conservative host. No PersonIR is executed. This
is not a production ABI or LifeHub installed-package execution proof, and does
not replace M1 evidence.

This probe observes one in-memory output channel only. It does not cover timing,
termination, traps, repeated invocation interactions, shared memory, arbitrary
foreign imports or full implicit-flow enforcement. An IR would need its own
validated semantics and escape-path checks before a stronger claim was justified.
The possible next question is precision: can existing IFC/instrumentation or a
restricted auditable graph permit this constant result without unsafe release,
and at what measured authoring/runtime cost? No compiler decision follows yet.
