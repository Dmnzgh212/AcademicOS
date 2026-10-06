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

A third consumer, the [independent records text shell](../../examples/lifehub/records_shell/README.md),
receives the authorized CLI export over stdin with no LifeHub imports or database
access. Its subprocess test checks successful display, denial without output and
terminal-control escaping. Its 1 MiB input cap is a presentation bound, not a new
byte guarantee for the records API.

## Shell lifecycle

Constructing LifeHub, exporting a catalog or reading records no longer seeds
workspace layout. The reference web renderer prepares its layout when rendered;
the demo command explicitly prepares its reference workspace. `lifehub init`
initializes platform storage/discovery and no longer reports workspace items.
Existing stored layouts remain intact, and layout persistence is still in
LifeStore; this change separates startup behavior, not every storage component.
Custom contribution config is preserved by discovery without being interpreted
as reference-shell dimensions.

Reference workspace initialization skips contributions whose dimensions cannot
be converted to supported sizes, and the web shell shows their escaped refs as
unsupported-layout notices. Other contributions continue rendering. Invalid
record-limit configuration produces a fixed surface message. Package integrity
verification errors continue to fail discovery; they are not hidden as layout errors.

The reference primitive renderer accepts only an actual integer record limit
from 1 through 100. Null, booleans, strings, fractional numbers and nonfinite
values are rejected before record access, rather than coerced into a limit.
