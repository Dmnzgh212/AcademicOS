# Installed platform smoke test

Run the smoke with the Python interpreter of a non-editable wheel environment:

```sh
/path/to/wheel-venv/bin/python -I scripts/lifehub_platform_smoke.py "$PWD"
```

The script refuses a platform imported from the supplied source checkout. It uses
a temporary database/package directory, shipped synthetic reader and echo packages,
and a loopback HTTP server on an ephemeral port. It deletes temporary data on exit
and stops the server. No existing personal database or external service is used.
The final output is a JSON PASS result; any failed assertion/request exits nonzero.

| Smoke path | Expected behavior |
| --- | --- |
| Echo host/guest calls | Denied before grant; exact reviewed grant enables both; revoke denies both without stdout |
| Catalog Shell | Installed reader visible in text and static HTML; unsupported input rejected without partial output |
| Reader and records Shell | Denied before grant; synthetic record readable after grant; independent consumer renders it |
| HTTP reference Shell | Health, page and assets respond; untrusted Host, missing token and wrong Origin rejected; valid layout POST succeeds |
| Lifecycle failure paths | Revoke denies read/run; tamper denies discovery/run; uninstall clears catalog and prevents execution |

CI runs this after installing the candidate wheel in a fresh environment, on both
supported Python versions. It complements source regression tests, including
controlled replacement/revocation during execution. It is a bounded smoke test,
not exhaustive security, performance, portability or real-data acceptance.

Initial local smoke passed against the PR #32 candidate wheel. The smoke harness
and CI step add validation only; they do not change platform runtime behavior.
