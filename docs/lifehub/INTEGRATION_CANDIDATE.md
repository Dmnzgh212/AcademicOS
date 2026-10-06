# LifeHub v0.1 integration candidate

This is the cumulative main-targeted candidate for the bounded developer prototype.
It assembles the platform slices without merging the PersonIR research stack.
It does not perform a main merge or publish a release.

## Exact recovery and scope

- Main base: `856b48a7adbb480d567d63c2582aa02d7405ce92`.
- Platform recovery: PR #7, `dc65605c0e84dcf545a8f8fdd7be176eb9c2a982`.
- Direction audit recovery: PR #16, retained separately.
- Validated implementation: PR #31, `bde9c72b70f5494a05a266b6396768fcf95932d1`.
- Original platform slices #1, #3–7 and resumed slices #17–31 remain available.
  The cumulative candidate preserves their ancestry and targets main directly.
  Merging the candidate would integrate those platform changes in one operation;
  it does not require separately merging every stacked PR.
- Research PRs #2 and #8–16 are not integration sources. Historical research
  documents remain under `docs/lifehub/research`; no `experiments/person_ir`
  implementation or research test dependency is present.

## Automated cumulative review

| Area inspected | Result and retained evidence |
| --- | --- |
| Package parsing/install/removal | Reviewed-content approval, path/file/size checks, inert installation, verified execution bytes, outgoing/incoming grant removal and staged-request invalidation |
| Capability lifecycle | Explicit scoped reads, exact service binding, approval digest matches persisted binding, old handles reject changed approved content |
| Wasm host boundary | Explicit host imports, export signatures, approved module, memory/fuel/IO/count limits, shared finite/depth/byte JSON checks |
| Result and request release | Service output withheld after grant/package changes; staged Wasm output keeps starting digest, with final database check and submission in one transaction |
| Host decisions | Proposal base-record conflict checks, package/namespace binding, explicit effect approval, at-most-one attempt and uncertain-outcome handling; synthetic executor only |
| Presentation and transport | Detached catalog/records, stdlib independent shells, escaped reference output, scoped reads, loopback Host/Origin/token checks, disabled automatic egress redirects |
| Integration scope | Main is an ancestor, diff check clean, existing AcademicOS tests retained; modified application source stays under LifeHub |

Focused findings and regression proofs are recorded in
[the review checkpoint](PLATFORM_REVIEW_2026-10-06.md). This review was performed
by the implementing assistant, not an independent human or security auditor.
No remaining blocker was identified within the declared prototype trust model;
that statement is bounded by the limitations below.

## Validation gate

The exact implementation commit above passed 228 tests and Ruff from a clean
checkout with the imported runtime path checked. GitHub run 325 passed both
Python 3.11/3.12, fresh installed-wheel smoke, and repeat-build/extracted-examples
smoke. Run 324 caught an omitted runtime file; the corrected commit is the one
included here. Final candidate CI must also be green before merging.

To repeat source checks from a clean candidate checkout:

```sh
python -m pip install -e '.[dev,wasm]'
python -m ruff check src tests examples/lifehub scripts/lifehub_wheel_smoke.py scripts/build_lifehub_examples.py
python -m pytest -q
```

Follow [wheel validation](WHEEL_VALIDATION.md) and
[examples distribution](EXAMPLES_DISTRIBUTION.md) for installed execution.
[Platform smoke](SMOKE_VALIDATION.md) also exercises the reader, independent
Shells, lifecycle rejection and real loopback HTTP requests.
Build wheel and examples from the same candidate commit. The builders and CI
exercise only temporary synthetic fixtures; no personal capabilities are granted.

## Merge and release boundary

This candidate is ready for a merge decision after its final checks pass. Main
remains unchanged until explicit merge authorization. Preserve the historical
research branches. No language/compiler expansion or real effect executor is a
prerequisite for this prototype merge. Release publication is a separate action.

Retained limits: trusted local operator APIs; no remote/multi-user identity
boundary; filesystem and SQLite updates not globally atomic; no DNS pinning or
complete SSRF sandbox; Wasm compilation wall time not fuel-bounded; row-bounded
record exports without total-byte/pagination guarantees; reference workspace
storage in LifeStore; no real external effects, Mesh, WIT Component Model, or
accepted PersonIR compiler. Linux/Python CI is not cross-platform certification.
