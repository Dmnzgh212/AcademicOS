# Generic core-Wasm reader

This sample is a domain-neutral package. It requests read access to `sample`,
reads `sample.records` only when explicitly run, and returns the serialized byte
count. It neither writes records nor stages effects. The catalog consumer and
CLI are independent of a calendar or approval inbox.

From the repository root, after installing `.[dev,wasm]`:

```sh
python examples/lifehub/reader/build.py /tmp/lifehub-reader.zip
lifehub review-package /tmp/lifehub-reader.zip
lifehub install-package /tmp/lifehub-reader.zip --approve-hash DIGEST --db /tmp/reader.db --installed /tmp/reader-plugins
lifehub catalog --db /tmp/reader.db --plugins /tmp/reader-plugins
lifehub run-wasm example.reader:read --db /tmp/reader.db --installed /tmp/reader-plugins
```

Replace `DIGEST` with the reviewed digest. The first run must fail because
requested read access is not an effective grant. Continue explicitly:

```sh
lifehub grant-read example.reader sample --db /tmp/reader.db --plugins /tmp/reader-plugins
lifehub run-wasm example.reader:read --db /tmp/reader.db --installed /tmp/reader-plugins
lifehub revoke-read example.reader sample --db /tmp/reader.db --plugins /tmp/reader-plugins
lifehub run-wasm example.reader:read --db /tmp/reader.db --installed /tmp/reader-plugins
lifehub uninstall-package example.reader --db /tmp/reader.db --installed /tmp/reader-plugins
```

The granted run returns the byte length of a JSON array (empty if no host records
exist). The revoked run fails again. `tests/test_lifehub_sample_package.py`
uses the shipped builder and manifest, installs through the real CLI, seeds one
host record, discovers via CLI JSON, executes through the kernel, checks denied
scope/revocation, and verifies uninstall removes discovery and activation.

This is core-Wasm, not WASI or Component Model. Install approval and capability
grants remain separate. Build does not install or grant permissions.
