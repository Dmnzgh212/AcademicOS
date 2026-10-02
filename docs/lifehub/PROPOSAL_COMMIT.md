# Local proposal and commit flow

Approved core-Wasm extensions may call `lifehub.propose_json`. This only stages a
change in memory. If the module traps, runs out of fuel, or fails a permission check,
the staged changes are discarded. After a successful run, the host saves pending
proposals with the package digest, extension reference, target namespace and key,
JSON payload, and the current target record ID. Repeated identical runs reuse a
pending proposal. At most eight proposals may be staged per run.

The user inspects the full payload and makes an explicit local decision:

```bash
lifehub proposals --db data/lifehub.db
lifehub approve-proposal 1 --db data/lifehub.db --installed data/lifehub-installed
# or
lifehub reject-proposal 1 --db data/lifehub.db
```

Approval checks the installed package contents, the exact package digest and the
manifest's write namespace again. In one SQLite transaction it checks that the
target record ID still matches the ID captured when the proposal was formed. A
different ID marks the proposal `stale` with no record insertion. A successful
decision appends one record and marks the proposal `committed` in the same transaction.
If identical content already exists under the same plugin, namespace and key, it is
marked `already_recorded` with no new record. Repeating an approval cannot append
twice. Rejection records `rejected`; uninstall marks pending proposals `invalidated`.
Decisions remain in the database as an audit trail.

This flow handles **local append-only records**. It does not approve email, payments,
network disclosure, device control, or other external effects. Those need a separate
authority and retry protocol. Direct native host APIs and legacy demo seeding remain
trusted host code; untrusted core-Wasm has no direct mutation import.
