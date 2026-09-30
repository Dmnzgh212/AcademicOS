# General component comparator — execution gate

Status: **interface candidate, not an executed Component Model baseline**. The executable comparators remain `baseline.py` (trusted Python functions) and the two manually constructed **core-WASM** modules in `wasm_baseline.mjs` and `wasm_email.mjs`. Their imports and integer/opaque-handle shapes are scenario-specific. They cannot establish the usability, toolchain cost, or typed boundary of a general WIT component.

The local environment used for this probe has Node 24, but no `wasmtime`, `wasm-tools`, `cargo`, `rustc`, `clang`, or component binding generator on `PATH`. Node executes the existing core-WASM modules. The candidate [WIT world](wit/comparator.wit) has not been parsed by `wasm-tools`, compiled into a component, or instantiated. Tool availability is an environmental observation, not a claim that the Component Model cannot support this design.

The [Component Model WIT reference](https://component-model.bytecodealliance.org/design/wit.html) defines packages, interfaces, records, variants, `option`, `result`, and worlds. The [worlds guide](https://component-model.bytecodealliance.org/design/worlds.html) describes imports supplied by the host and exports invoked by it. The [running guide](https://component-model.bytecodealliance.org/creating-runnable-components.html) distinguishes a typed WIT description from a component binary and a compatible host. The candidate follows that division; its syntax still needs validation with a WIT toolchain.

## Candidate contract and deliberate limits

`host.read(name)` returns host-controlled JSON data, source reference, and sensitivity flag. The host must enforce a separately approved source manifest; a string named by the component is never itself authority. `host.propose` and `host.request-effect` accept data-only requests and return opaque request IDs. They **do not commit state or execute effects**. The trusted host later materializes a `CommitRequest` or `EffectRequest`, checks content and provenance against its own observations/session, and applies the same live grant, policy, journal, and receipt services used by PersonIR. No capability handle or issuer API crosses the WIT boundary. The component `run` export permits scenario logic to use these generic imports.

The `value-json` and `payload-json` fields are a deliberately conservative transport choice. They avoid encoding PersonIR graph nodes or domain-specific `Payment`/`Calendar` types in WIT, but force the host to parse, bound, copy, and validate JSON at every submission. They also leave transformation lineage opaque: source refs describe what the component read, while the host cannot infer its intermediate computation from WIT alone. The existing Python `ComponentSession` similarly records reads but cannot verify arbitrary internal calculations. If full lineage is a required product feature, compare the cost of instrumentation or a typed host value API against PersonIR's closed graph trace rather than assuming parity.

## Fair executable comparison required before a final decision

| Gate | Same test for both approaches | Status |
|---|---|---|
| Artifact and isolation | Compile the WIT world and at least one guest to an actual component; inspect imports and run it with a host that supplies only approved functions | Open; candidate `.wit` has not been validated or executed |
| Two use cases | Run academic proposal and protected email through the **same** generic imports; add a third nontrivial scenario without new host ABI operations | Open; existing core-WASM examples use separate narrow ABIs |
| Request fidelity | Host binds returned request IDs to the current session, input snapshots, declared scopes, payload, and explicit intent; forged IDs/values are rejected | Open; Python email bridge does this only for one hardcoded payload shape |
| Shared host enforcement | Both outputs go through the same durable state/effect APIs, live grant checks, optional evidence policy, and replay handling | Partly demonstrated for the narrow email bridge and Python comparator, not the candidate component |
| Adversarial calls | Try undeclared reads, false source refs, missing disclosure, changed destination/value, direct host-service calls, stale state, and replay after revocation | Open for this WIT world; earlier core-WASM probes cover selected cases |
| Cost and explanation | Compare code size, framework glue, authoring/debugging time, inspectable trace, and repeated construction/execution cost under comparable isolation | Open; existing Python microbenchmark excludes WASM host round trips |

An executed WIT baseline may show that ordinary code plus host capabilities is sufficient, or expose a real explanation/static-check advantage for a restricted IR. Until the same interface and host checks are exercised in both paths, neither inference is established. The provisional compiler hold in `BASELINE_COMPARISON.md` remains warranted by the evidence already collected; this file does not raise the experiment's completion percentage by itself.
