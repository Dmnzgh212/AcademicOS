# PersonIR experiment, slices 1–3

This is the executable falsification experiment from
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

Slice 2 adds a host-owned `AuthorityRegistry`. It issues opaque in-process handles
with principal, domain, operation, exact resource, issuer, issue/expiry time,
optional activation context, and revocation status. An intent can be checked with
`require_intent` at use time. Read, commit and effect operations are distinct;
serialized IDs and reconstructed handles fail registry identity checks. Graph data
cannot carry a handle. This is an in-process experiment: arbitrary native Python
with access to the trusted host/registry remains outside its threat model. The
commit path checks the capability at use; an external executor is not connected.

Slice 3 connects commit requests to a separate host-owned SQLite store. The host
reads a state snapshot, gives only its JSON value to the interpreter, and prepares
a durable proposal bound to the snapshot's version and content hash. An explicit
commit checks the current capability, principal/domain, target, and base version
inside an immediate transaction. Stale proposals do not overwrite current state;
repeat evaluation deduplicates the same proposal, and repeat commit does not append
another version. Rejecting a proposal changes only its decision row. A trusted host
must bind the snapshot it read to the input passed to the interpreter; this
experiment does not authenticate arbitrary Python `Intent` objects from native
code. The capability registry is in memory and must survive for a pending grant to
remain usable after restarting the SQLite store.

**Baseline comparison:** The version/hash check, transaction, deduplication and
proposal status are conventional MVCC/CAS and idempotency patterns. This slice
does not establish a novel PersonIR advantage. The open question is whether the
full composition with authority, provenance and effects is clearer or more
enforceable than the same mechanisms in the conventional Wasm host.

This slice deliberately supports only `identity` and `get` transforms, and a
two-value join. If representative programs need arbitrary Python callbacks, that
counts against this IR design rather than justifying an unsafe escape hatch.

Run tests from the repository root:

```bash
python -m pytest -q experiments/person_ir/tests
```

Next slices: fake effect executor,
provenance/information-flow checks, heterogeneous scenarios, then comparison with
the existing conventional Wasm capability host. No claim of a new language or
compiler follows from these slices.
