# LifeHub v0.1 prototype acceptance

This checklist defines a bounded developer prototype, not completion of an open
platform ecosystem or of PersonIR. Acceptance does not authorize merging main,
publishing a release, or approving real personal capabilities.

| Gate | Evidence | Current assessment |
| --- | --- | --- |
| Platform/research separation | Platform tree and pytest paths omit experiments/person_ir; recovery anchors documented | Implemented; original research branches retained |
| Package lifecycle | Shipped reader and echo packages install by reviewed digest; managed bytes are verified | Covered by source tests and local wheel smoke |
| Capability enforcement | Denied before grant, allowed after exact grant, denied after revoke; controlled tampering/revalidation tests | Covered within documented local trust model |
| Runtime/service path | Approved core Wasm, bounded JSON services and installed-caller guest bridge | Executable samples and tests exist |
| Replaceable presentation | Catalog and records exported as detached contracts; stdlib shells receive JSON; kernel startup does not seed layout | Demonstrated, with reference-shell storage coupling remaining |
| Supported source matrix | 221 local tests; #28/#29 CI runs 320/321 succeed | Source matrix validated at those revisions; latest checks remain required |
| Installed distribution matrix | Fresh wheel environment and reproducible examples archive run synthetic end-to-end flows | Remote runs 320/321 passed Python 3.11 and 3.12 |
| Review and distribution | Draft PR stack #17–30; examples companion builder exists; no main merge/release | Independent cumulative review and integration decision outstanding |

## Review order

Review #17 then #18–20 for package/contract/authorization/runtime behavior;
#21–22 for discovery presentation and message boundaries; #23–25 for documentation,
records mediation and shell lifecycle; #26–27 for installed distribution and examples; #28–30 for authorization,
transport and execution snapshot fixes.
Each draft targets its preceding branch. Approval of an isolated slice is not
approval of the whole stack. Retain the research stack separately.

Before treating the prototype as ready to distribute, retain passing wheel CI for the final reviewed revision, review cumulative platform changes against the #7 recovery anchor,
resolve material findings, and build the samples companion alongside installation
instructions. See [the focused review checkpoint](PLATFORM_REVIEW_2026-10-06.md). Main integration and publication remain separate explicit decisions.

## Limits retained in this prototype

The CLI and Python shell APIs are trusted local interfaces. They are not remote
identity or multi-user boundaries. Data exports require authorized host choices;
there is no general information-flow proof. Controlled package-change tests do
not prove all filesystem race cases. Fuel does not bound compilation wall time.
Record reads have a row bound, not pagination or a total byte bound. Reference
workspace persistence remains in LifeStore, although startup is separated.
Examples are not bundled into the wheel. No real external effect executor,
Personal Mesh, WIT integration, source language or compiler is accepted here.

Do not use test counts or PR counts as a completion percentage. Report the gates
above as verified, pending or outstanding, with the exact evidence available.
