# Independent catalog shell

This shell uses only Python's standard library. It imports no LifeHub modules,
opens no database, and knows no closed list of extension points or life domains.
It consumes the versioned JSON catalog over stdin and renders text or static HTML.
All entries, including unknown contribution types, remain visible as metadata.

```sh
lifehub catalog --db DB --plugins INSTALLED | python -I examples/lifehub/catalog_shell/shell.py
lifehub catalog --db DB --plugins INSTALLED | python -I examples/lifehub/catalog_shell/shell.py --style html > catalog.html
```

This is a metadata shell, not a replacement for every workspace/review feature.
It does not fetch personal records, grant permissions, or activate entrypoints.
HTML escapes metadata and contains no scripts or external resources; text quotes
control characters. Stdin is capped at 1 MiB. Catalog JSON is an inspectable
contract, not an executable plugin UI format. Invalid/unsupported catalogs fail.

Tests pass a real kernel-generated catalog to this script in isolated Python
mode for both renderings. That verifies a shell consumer can operate without
LifeHub imports and preserve unknown extension points. Existing CLI and web
shells remain separate consumers; this sample adds no renderer knowledge to Core.
