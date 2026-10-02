# Local review inbox

Run the local shell with the same database and installed package directory used by
the CLI:

```bash
lifehub serve --db data/lifehub.db --plugins data/lifehub-installed
```

Open the loopback address printed by the command and select **Review inbox**. Pending
local changes show the target namespace, key, base record, approved package digest,
and full proposed JSON. **Commit change** checks the package and current base record
again before adding a record; **Reject** closes the proposal. A changed target is
marked stale and is not overwritten.

Effect cards show the exact kind, destination, purpose, package digest, and full
payload. **Approve request** records the disclosure decision without dispatching.
The separate **Run local test** button is available only for `test.record`, which
writes a fake delivery into the local database. A pending or approved request can
be rejected or canceled. In-flight and unknown outcomes remain visible and cannot
be retried from this page; investigate them through the ledger and CLI.

The shell binds to loopback. Requests to the decision endpoint require the session
token, an allowed loopback Host and matching Origin when supplied. The page escapes
extension content before displaying it and sends no reviewed payload to a remote
service. The CLI remains available for scripted review and recovery.
