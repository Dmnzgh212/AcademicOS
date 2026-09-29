# Conventional host API comparison — provisional

## Comparator and scope

`baseline.py` sketches a conventional capability-limited **host interface**: a component manifest declares readable observations, commit targets, and effect scopes; a session exposes `read`, `propose`, and `effect` calls. Trusted sample component functions implement the academic and email examples. The host can reuse the same `AuthorityStore`, `StateStore`, and `EffectService` as PersonIR. This intentionally holds authorization, version checks, and fake execution constant while comparing the programming interface.

No WASM/WIT runner is installed in this environment. Python sample functions run in the host process and are **not safe untrusted components**. This comparator assesses interface expressiveness and call-time controls, not sandbox security, deployment overhead, or a complete conventional component runtime. Both sides still lack durable recovery and real provider adapters.

## Observed comparison

| Dimension | PersonIR graph | Conventional host API sketch | Inference |
|---|---|---|---|
| Academic proposal | Explicit source/select/join/derive/propose/commit graph | Ordinary code reads two declared inputs and proposes a value | Same host version and authority semantics; no unique advantage shown. |
| Email egress | Verifier finds direct protected flow before execution; host checks disclosure and effect grants | Session conservatively marks all reads protected and requires disclosure at effect call; same grants | Graph offers earlier structural rejection and finer lineage, but same host owns actual authority. |
| Recipient equality | Current graph cannot express equality of recipient data and sink config | Component code compares them before request | Generic predicates or host contract validation needed in IR. |
| Package source/scope declaration | Missing from graph experiment | Manifest and session check names/scopes at calls | Baseline sketch closes two integration gaps at its mediated API. It has no OS sandbox. |
| Provenance | Node trace on values and receipts | Host records reads and request construction; opaque code internals are not traced | PersonIR provides finer inspectable dataflow for its tiny closed op set. |
| Payment/device/shared authority | Missing freshness, predicates, bounds, quorum | Could be programmed or enforced in host policy, but not implemented/tested here | Neither prototype proves these scenarios safe. |
| Execution isolation | No arbitrary code in serialized graph; trusted Python host | Sample Python code runs in host process | Not a comparable sandbox test. |

The baseline deliberately reuses the experimental request dataclasses and host services, so equality of enforcement in these tests is by construction. It demonstrates that the useful policy checks can live in an ordinary host API; it does **not** establish that a complete WASM/WIT component has identical usability, provenance, or cost.

## Local overhead probe

Run `python -m experiments.person_ir.benchmark`. On this execution environment, one run with five repeats of 2,000 operations each returned median microseconds per request construction:

| Example | PersonIR graph | Host API sketch | Ratio |
|---|---:|---:|---:|
| Academic | 88.81 µs | 27.00 µs | 3.29× |
| Email | 86.70 µs | 40.58 µs | 2.14× |

Graphs and manifests were constructed outside the measured call; neither case commits state, executes effects, crosses a process boundary, or uses a WASM engine. The graph repeatedly verifies nodes and builds detailed traces, so this is a narrow Python implementation cost, not evidence about the performance of an optimized IR or a sandboxed component. The benchmark script is the reproducible evidence; figures will vary by machine and run.

## Decision gate

The seven PersonIR slices show useful explicit requests and inspectable lineage, but the five examples do not demonstrate safe cross-domain generality. Hostile tests expose source/manifest binding gaps. The comparator can express academic and email flows with existing host policy, and ordinary code can state recipient equality more directly. No measured or semantic advantage currently justifies a new source language/compiler.

**Provisional decision: hold compiler work.** Continue LifeHub as an open capability host, repair the package/input boundary, and test generic policy preconditions and multi-principal grants. Then evaluate at least one actual isolated component (preferably WASM Component/WIT) and durable recovery before a final POP/PersonIR Go/No-Go. This is not a decision to abandon LifeHub or a proof that a better PersonIR is impossible.
