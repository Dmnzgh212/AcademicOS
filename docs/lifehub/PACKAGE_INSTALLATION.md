# LifeHub package installation (first slice)

Installable packages are ZIP files containing a versioned `plugin.toml` at the archive root.
They may include static assets and synthetic `seed.json`. Nothing in the ZIP is executed.

```bash
lifehub review-package ./example.zip
lifehub install-package ./example.zip --approve-hash <sha256-content>
lifehub plugins --plugins data/lifehub-installed
lifehub serve --plugins data/lifehub-installed
lifehub uninstall-package demo.example
```

`review-package` prints the plugin identity, version, requested permissions, contributions,
and a canonical SHA-256 content digest. Review those permissions and pass that exact digest
to `install-package`. The installer reads the ZIP again, rejects unsafe paths, symlinks,
duplicate entries and oversized contents, then stores an approval tied to the installed
package's version and bytes. It refuses a changed archive and refuses to replace an
installed ID. To change a package, uninstall it and review/install the new ZIP; the old
cross-plugin read grants are cleared by uninstall. Local records are retained.

The managed directory uses the same database as the LifeHub commands (default
`data/lifehub.db`). Pass matching `--db` and `--plugins data/lifehub-installed` when
opening the installed packages. LifeHub verifies package contents on discovery and on
host-mediated storage/network calls. The database records the managed directory so
removing its marker does not turn a previously managed directory into a trusted demo
directory. The repository's `lifehub_plugins` remains a development/demo directory.

This is an approval gate for host-mediated packages. Approved core-WebAssembly modules
can be run through the restricted runtime described in `WASM_RUNTIME.md`. Modules can
stage local change proposals; only the separate host decision described in
`PROPOSAL_COMMIT.md` writes the proposed record.
Declared external effect requests enter a separate review and recovery ledger in
`EFFECT_LEDGER.md`; this release only supplies a local fake executor.
Untrusted native Python, JavaScript, and binaries are not launched. A future executable
runtime for those formats needs a separate isolation model.
Changes by another process between a verification and a file read remain outside the
guarantees of this initial filesystem-backed slice.

Capability handles bind their manifest and installed content digest at creation.
After uninstall/reinstall with different approved content, old storage and egress
handles reject access, including replacements with an identical manifest. Obtain
new handles to use the replacement's permissions. This is sequential lifecycle
validation, not an atomic filesystem/database concurrency guarantee.
