# Slice 7 hostile-extension findings

Run `python -m pytest -q experiments/person_ir/tests/test_hostile.py`.
The eight requested attack classes are exercised directly. An additional
native-host probe exposes a boundary that the data-only graph verifier cannot
protect.

| Attempt | Observed result and explicit reason |
| --- | --- |
| Undeclared state | Unknown read node fails verification; missing host-provided state view raises missing input. |
| Synthesize authority | Unknown mint node fails verification; a capability cannot cross the JSON boundary or be reconstructed from its ID. |
| Protected data to sink | Verifier rejects a protected effect input without a matching disclosure. |
| Bypass disclosure | Re-targeting through an identity transform fails structural verification; replacing an intent's disclosure tuple fails ledger validation. |
| Replay effect | The same request ID is deduplicated, and a completed request refuses another dispatch. |
| Stale commit | An older proposal returns `stale` and cannot overwrite the newer version. |
| Forge provenance | A conflicting host label fails interpretation; an unverified source fails effect enqueue. |
| Out-of-scope capability | Wrong target fails approval; revoked authority fails dispatch. |
| Reconstruct native intent | **Bypass found:** a Python caller can replace the payload of an interpreter-produced `Intent` while retaining its trace. The effect ledger accepts it as a new pending request. The test deliberately stops before approval/dispatch. |

## Threat boundary and implications

The verifier constrains **graph data**, not arbitrary Python code running in
the trusted host. A malicious extension confined to the graph cannot invoke
host APIs, supply an executor, or mint a handle. The interpreter still receives
host-asserted observations/evidence, and this prototype's Python `Intent` is a
plain dataclass. A compromised or incorrectly wired host can fabricate evidence,
reconstruct intents and invoke the host-owned ledger or registry. Such input is
outside the IR isolation boundary but inside any real integration's risk.

The discovered native-intent bypass is a **model/integration flaw**, not a
missing verifier rule: the ledger never binds a request to an authenticated
interpreter run and immutable host input snapshot. Before any real executor,
the host must own an opaque evaluation record and accept requests only through
that record, bind evidence and snapshot IDs to the run, and conduct sink-specific
validation at approval and dispatch. A token embedded in graph JSON would not
solve this. The same trust issue applies to untrusted host-produced evidence.

Other unresolved findings from `SCENARIOS.md` remain: price and sensor freshness,
joint authority for shared data, and limited computation beyond `join`/`get`.
Passing eight negative tests does not demonstrate a novel language advantage.
The conventional capability-limited baseline and comparison are still required
before deciding whether to build a compiler.
