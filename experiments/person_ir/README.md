# PersonIR experiment, slice 1

This is the first executable falsification experiment from
`docs/lifehub/research/PERSON_IR_EXPERIMENT_PLAN.md`. It is separate from the
LifeHub kernel. Graphs are constructed as immutable Python `Node`/`Program` data;
there is no parser, callback node, import mechanism, filesystem/network/process
operation, or host effect executor in this interpreter.

The verifier checks ordered references, node shapes, a fixed transform set, and
that a commit request points to a proposal. The interpreter accepts JSON-compatible
host observations and state snapshots, produces derived values with source labels,
and returns proposed commit/effect requests as **data**. It does not apply either.
Protected values require a destination-specific declassification marker before
they can form an effect request. This marker is an *untrusted request*, not an
authorization or proof of safe disclosure. A future authority layer must validate
the principal, scope, current state, purpose, revocation, and actual sink at use time.

This slice deliberately supports only `identity` and `get` transforms, and a
two-value join. If representative programs need arbitrary Python callbacks, that
counts against this IR design rather than justifying an unsafe escape hatch.

Run tests from the repository root:

```bash
python -m pytest -q experiments/person_ir/tests
```

Next slices: explicit authority, stale-state commits, fake effect executor,
provenance/information-flow checks, heterogeneous scenarios, then comparison with
the existing conventional Wasm capability host. No claim of a new language or
compiler follows from this first slice.
