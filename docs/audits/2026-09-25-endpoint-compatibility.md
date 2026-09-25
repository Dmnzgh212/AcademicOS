# Audit — Endpoint Compatibility Layer

Date: 2026-09-25

## Scope

This audit covers the Brightspace institution-compatibility slice added after the first real-account validation tooling.

Implemented:

- schema v5;
- `endpoint_capabilities` persistence;
- value-free response-shape summaries;
- capability-aware Brightspace course collection;
- cooldown/re-probe policy;
- live doctor persistence of endpoint capability results;
- `academicos-capabilities` sanitized CLI/JSON report;
- migration and behavior tests.

## Cooldown policy

| Condition | Learned status | Re-probe |
|---|---|---:|
| success | supported | normal collection |
| HTTP 404 / 405 | unsupported | 30 days |
| HTTP 403 | forbidden | 12 hours |
| HTTP 401 | auth_error | immediately after auth repair |
| HTTP 429 / 502 / 503 / 504 | transient | 10 minutes |
| other error | error | 1 hour |

The policy is intentionally conservative: authentication errors are not mistaken for endpoint incompatibility, and temporary service failures are not permanently disabled.

## Privacy audit

Capability records do not store academic response values.

Allowed diagnostic material:

- endpoint name;
- status;
- HTTP status;
- timestamps;
- top-level response keys / list item key names;
- item count;
- bounded error summary.

Excluded:

- bearer tokens;
- cookies;
- email addresses;
- grades;
- announcement text;
- assignment names/content;
- response values.

## CI findings

The first integrated CI run failed with four findings:

1. two pre-existing schema assertions still expected v4 after schema v5 was introduced;
2. the doctor test still expected `schema=v4`;
3. capability cooldown appeared not to prevent a second request.

The fourth finding exposed a real logic bug:

```python
wanted = include or DEFAULTS
```

When every requested endpoint was in cooldown, the capability wrapper produced an empty set. The base collector interpreted that empty set as falsy and therefore expanded it back to the default full dataset list, causing the supposedly disabled endpoint to be requested again.

Fix:

- the capability wrapper now treats an empty post-filter set as a complete no-op and does not call the base collector;
- schema assertions were updated to v5;
- migration coverage now verifies `endpoint_capabilities` exists after upgrading from v1/v4.

## Final verification

GitHub Actions matrix:

- Python 3.11 — success;
- Python 3.12 — success;
- Ruff correctness checks — success;
- pytest snapshot — **70 passed** on Python 3.11.

## Remaining real-world validation

CI cannot prove uOttawa-specific endpoint permissions or response shapes.

The next real-account sequence remains:

```powershell
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\first_run_windows.ps1
.\.venv\Scripts\academicos-doctor.exe --live --bootstrap-auth --config config.local.toml
.\.venv\Scripts\academicos-capabilities.exe --json-out data\audits\capabilities.json
```

The resulting doctor/capability reports are designed to be shareable for debugging without exposing raw academic content or authentication secrets.
