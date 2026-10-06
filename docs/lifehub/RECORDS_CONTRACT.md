# Local records contract v1

`LifeHub.read_records(plugin_id, namespace, api="lifehub.records@1", limit=8)`
returns detached JSON containing `api`, `plugin_id`, `namespace` and `records`.
`RecordsProvider` describes this interface without prescribing a renderer.
Limits are integers from 1 through 100; booleans and unknown API versions fail.
This row bound does not promise a total byte bound or pagination.

The host uses existing ScopedStore authority: a plugin may read its declared
write namespace, or a requested read namespace with an effective host grant.
Managed package verification remains in the scoped read path. Requesting data
in a contribution does not grant permission. Revocation takes effect on the next
read. Returned objects carry no authority and changing them does not write data.

Both the reference web primitive renderer and the CLI consume this contract.
The web renderer displays a fixed unavailable message when permission is denied.
The CLI outputs JSON and performs no rendering or writes:

```sh
python -m academicos.lifehub.cli records example.reader sample.records --db /tmp/reader.db --plugins /tmp/reader-plugins --limit 8
```

Use the reader example's explicit install and grant steps first. The CLI and
in-process interface are trusted local host interfaces; plugin_id is an operator
choice, not an identity that a remote client or guest can claim. This is not a
new guest import, network endpoint, or protection against a trusted Python shell
that deliberately accesses kernel internals. No permission is automatically
added, and the independent catalog shell remains metadata-only.

Tests cover requested-but-ungranted reads, explicit grant/revoke, detached values,
version/limit errors, and both CLI and web consumers.
