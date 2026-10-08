# Original upstream PROV reuse experiment

Implements LH-D-REUSE-001 in isolation. Concrete need: export the existing
synthetic trusted-host records and their derivation/attribution relations using
an actual maintained implementation, rather than building a new PROV serializer.
This is a research-record adapter, not a production plugin or M1 proof.

## Choice and supply boundary

Use upstream `trungdong/prov` **3.1.0**, MIT, Python >=3.10. Upstream source:
https://github.com/trungdong/prov/tree/3.1.0 (release commit
`67f0c7797cde89ccab0c5b91fb138bca81c610ac`). Package metadata:
https://pypi.org/project/prov/3.1.0/ . The release is in the upstream 3.x
maintenance line; this is not a complete vulnerability audit or certification.

The installed wheel SHA256 is
`c70f2785e353bc3366f4711d7a5488380249026498fcf6274c71f783f2773545`, matching
published metadata. The requirements file pins this wheel hash. Base installation
has no unconditional runtime dependencies; RDF/XML/plot extras are excluded.
The wheel retains upstream MIT copyright/license in its dist-info/licenses/LICENSE.
No upstream source is copied, changed or vendored. Redistribution must preserve
that notice. Do not promote this experimental pin into production automatically.

Alternatives considered: a handwritten JSON export would not implement an
interoperable PROV serializer; RDF/graph extras add an unnecessary surface for
this JSON-only task. Reuse the base library behind a small export-only adapter.
Removal of this adapter/dependency leaves Core and the prior research intact.

## Real execution and limits

```sh
python -m venv /tmp/prov-reuse
/tmp/prov-reuse/bin/python -m pip install --require-hashes -r research/authority_semantics/prov-requirements.txt
/tmp/prov-reuse/bin/python research/authority_semantics/prov_adapter.py /tmp/prov-results.json
```

Local Python 3.12 execution passed all six existing synthetic families: ordinary
API and graph record documents compare equal; original library serialization and
deserialization preserve each document. Two malformed host fixtures (unsupported
kind and dangling source) raise errors in the adapter. Retained output is
`prov_results.json`; research CI reproduces it on Python 3.11/3.12.

Concrete mapping: evidence/derived/proposal are PROV entities with LifeHub research
attributes, input edges become derivation, owner assertions become agent attribution.
Attribution does not mean ownership, consent or capability proof. Rejected proposal
status remains separate from evidence. Effects, grants, snapshot enforcement,
revocation and execution are intentionally not mapped into an authorization engine.

An adversarial attribution assertion successfully roundtrips through the library.
That is expected: provenance serialization is not authentication. There is no
import-to-grant/host-state API. Only trusted synthetic host records are exported;
untrusted or personal-data ingestion, byte/depth bounds, signatures, concurrency,
remote transport, installed Engine execution and Windows behavior are unverified.

The upstream library is now actually reused for this bounded task. The inputs
remain synthetic and the same shared-host fixtures; this adds no independent
integration or PersonIR superiority evidence. No Core/dependency/production ABI
change, no compiler. M1 remains separate and unaccepted.
