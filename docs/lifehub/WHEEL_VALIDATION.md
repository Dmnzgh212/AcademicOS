# Installed wheel validation

CI runs source tests, builds the wheel, creates an empty virtual environment and installs
that wheel plus the Wasm runtime, and executes `scripts/lifehub_wheel_smoke.py REPOSITORY_ROOT`.
The script uses isolated Python subprocesses from a temporary working directory
and refuses a package imported from the source checkout. It builds only the
shipped synthetic echo packages, approves their reviewed digests in disposable
storage, verifies catalog discovery, denies ungranted calls, grants and executes
host/guest calls, then revokes and checks both routes reject with no stdout.

This is an integration smoke check, not a release publication or a main merge.
It automatically approves only synthetic test fixtures inside its temporary
storage and never operates on an existing personal database or package directory.

Local reproduction can use a virtual environment with the runtime dependencies
installed, followed by a non-editable wheel installation:

```sh
python -m pip wheel . --no-deps --wheel-dir dist
python -m venv /tmp/lifehub-wheel-check
/tmp/lifehub-wheel-check/bin/python -m pip install dist/academicos-*.whl 'wasmtime>=36,<37'
/tmp/lifehub-wheel-check/bin/python scripts/lifehub_wheel_smoke.py "$PWD"
```

Use a disposable environment for these commands. The wheel loader check rejects
editable source imports. Dependencies are resolved into an empty environment;
examples are still read explicitly from the checkout. Distribution of examples,
platform portability beyond CI Linux/Python versions, and release publication
remain separate tasks.
