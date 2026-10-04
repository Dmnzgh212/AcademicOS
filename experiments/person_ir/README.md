# PersonIR experiment, slices 1–7

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
authorization or proof of safe disclosure. The host checks principal, scope and
revocation at use time; real executors would also need sink-specific validation.

Slice 2 adds a host-owned `AuthorityRegistry`. It issues opaque in-process handles
with principal, domain, operation, exact resource, issuer, issue/expiry time,
optional activation context, and revocation status. An intent can be checked with
`require_intent` at use time. Read, commit and effect operations are distinct;
serialized IDs and reconstructed handles fail registry identity checks. Graph data
cannot carry a handle. This is an in-process experiment: arbitrary native Python
with access to the trusted host/registry remains outside its threat model. The
commit path checks the capability at use.

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

Slice 4 adds a separate SQLite effect ledger and a local fake delivery executor.
Generating an effect request only enqueues it. An exact-scope grant permits an
explicit approval, and dispatch checks the grant again at use time. The ledger
marks `in_flight` before calling the trusted host executor. A known negative
outcome becomes `failed`; an exception after the call begins becomes `unknown`.
An interrupted process can leave `in_flight` until an operator confirms the old
executor stopped and marks it unknown. Neither state is automatically retried.
Request identity includes the disclosed payload, purpose, destination and sources,
so changed payload yields a new request and needs a separate decision. The host
rechecks the disclosure destination when enqueuing. A local state edit cannot
undo a completed effect. The default executor writes only a fake delivery in the
local database; this experiment makes no real network, email, payment or device
call. A trusted host may inject a test executor, but untrusted IR cannot supply
one. Authorization and delivery durability are conventional capability and
outbox/idempotency patterns, not evidence of novelty by themselves.

Slice 5 propagates a trace of host-asserted observation IDs, producers/versions,
program version, node identities, disclosure destination/scope/purpose and any
state version supplied by the host. Commit and effect rows retain that trace and
the capability ID used at the actual decision/dispatch. A nondeterministic or AI
result must enter as a host observation carrying an execution ID; this tiny IR
has no arbitrary nondeterministic transform callback. The verifier propagates
protected labels across joins and rejects an external sink unless the entire
value has a matching whole-value disclosure. The interpreter compares graph
source labels with host evidence. The effect ledger refuses sources without a
host label or a matching disclosure path.

These checks depend on a trusted host providing honest evidence and binding the
state version to its snapshot. They do not authenticate arbitrary native Python
objects, prove what an opaque producer actually did, prevent covert channels,
or make a disclosure marker itself into authority. The explicit effect grant and
host executor remain the use-time authority boundary. No partial-value
declassification is modeled; the verifier rejects unsupported scopes.

This slice deliberately supports only `identity` and `get` transforms, and a
two-value join. If representative programs need arbitrary Python callbacks, that
counts against this IR design rather than justifying an unsafe escape hatch.

Run tests from the repository root:

```bash
python -m pytest -q experiments/person_ir/tests
```

Slice 6 has five runnable graphs and boundary tests; see `SCENARIOS.md`.
Slice 7 exercises eight hostile-extension classes and documents a native-host
intent reconstruction bypass in `HOSTILE_FINDINGS.md`. The conventional Wasm
capability baseline and comparison remain before a compiler decision. No claim
of a new language or compiler follows from these slices.
