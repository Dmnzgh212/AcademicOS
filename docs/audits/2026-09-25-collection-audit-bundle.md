# Audit — Sanitized Collection Audit Bundle

Date: 2026-09-25

## Scope

This audit covers the one-command diagnostic artifact used for real uOttawa/Windows collection validation.

Implemented:

- `academicos-audit` CLI;
- allow-listed collection audit payload;
- doctor summary integration;
- SQLite schema/table counts;
- source-health summary;
- endpoint capability summary;
- Brightspace coverage summary;
- source/config feature flags;
- timestamped local output under `<data_dir>/audits/`;
- common diagnostic-string redaction;
- Windows bootstrap handoff to the one-command live audit.

## Privacy model

The audit bundle does not serialize source payload tables generically.

It deliberately does **not** read or copy:

- `source_items.raw_text`;
- `source_items.raw_json`;
- bearer/JWT tokens;
- cookies;
- Microsoft access tokens;
- mail/announcement body content;
- assignment/quiz source content;
- grade values;
- downloaded academic file content.

Only explicit diagnostic fields are selected.

Diagnostic strings are additionally redacted for:

- email addresses;
- Bearer credentials;
- JWT-like tokens;
- common Windows/POSIX user-home path segments;
- URL paths/query strings.

## Negative leakage test

The test suite intentionally inserts fake private material into local source storage and source-health error text, including:

- a fake professor/email body;
- an email address;
- a fake access-token value;
- a fake Bearer credential;
- a grade-like value;
- a private URL path.

The generated audit bundle is then serialized and asserted not to contain those values while still reporting the `source_items` row count.

This verifies that the bundle is based on an allow-list rather than accidental full-row serialization.

## User workflow

Initial live validation:

```powershell
.\.venv\Scripts\academicos-audit.exe --live --bootstrap-auth --config config.local.toml
```

After one real source synchronization:

```powershell
.\.venv\Scripts\academicos-sync.exe --config config.local.toml
.\.venv\Scripts\academicos-audit.exe --config config.local.toml
```

The second audit reflects learned endpoint capabilities, coverage, source freshness, cursor/manifest counts, and sync health without performing another interactive login.

## Final verification

GitHub Actions final matrix for the integrated slice:

- Python 3.11 — success;
- Python 3.12 — success;
- Ruff correctness checks — success;
- pytest — **75 passed** on Python 3.11.

## Remaining limitation

The bundle itself is CI verified, but Windows PowerShell bootstrap execution and institution-specific uOttawa authentication/API responses still require the user's real Windows/uOttawa environment. Those are intentionally the remaining deployment-validation items rather than simulated as completed.
