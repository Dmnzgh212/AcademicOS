# Developer examples companion archive

From the checkout:

```sh
python scripts/build_lifehub_examples.py /tmp/lifehub-examples.zip
python -m zipfile -e /tmp/lifehub-examples.zip /tmp/lifehub-examples
```

The archive contains the shipped reader, echo provider/client, independent catalog
and records shells, their READMEs, and the installed-wheel smoke script. It does
not contain the platform wheel, personal data, generated plugin binaries, research
implementation or source kernel. Python source builders create plugin ZIPs after
Wasm dependencies are installed. Build grants no authority.

Provide this archive alongside the matching wheel when distributing the developer
prototype. Installation, review, grant and revoke are explicit in the sample
READMEs. The archive's top-level README also explains synthetic smoke approvals.
No release is published by the builder or CI. ZIP entries use fixed timestamps,
permissions and ordering; repeat builds from unchanged files match byte-for-byte.

CI verifies repeat builds, extracts the archive outside the checkout and runs its
smoke script with the freshly installed wheel. This proves the echo package flow
uses distributed example files. Other sample flows retain their source tests;
this is not a cross-platform release acceptance or compiler delivery.
