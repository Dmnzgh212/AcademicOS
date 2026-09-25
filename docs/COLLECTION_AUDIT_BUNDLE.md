# Collection Audit Bundle

`academicos-audit` creates one shareable diagnostic JSON file for troubleshooting real AcademicOS source collection.

## Recommended first live validation

From the AcademicOS repository root on Windows:

```powershell
.\.venv\Scripts\academicos-audit.exe --live --bootstrap-auth --config config.local.toml
```

When Brightspace has not been authenticated yet, the live/bootstrap mode may open the persistent login browser so normal uOttawa SSO/MFA can complete.

The generated file is written by default to:

```text
<data_dir>/audits/collection-audit-YYYYMMDD-HHMMSSZ.json
```

Use `--output` to choose another local path.

## Included information

The bundle uses an allow-list. It contains only information useful for diagnosing the collector:

- AcademicOS version;
- Python/platform summary;
- SQLite schema version;
- table row counts;
- doctor PASS/WARN/FAIL checks;
- source-health freshness and counters;
- endpoint compatibility states;
- value-free response shape summaries;
- Brightspace endpoint coverage percentages;
- source feature/configuration flags.

## Explicitly excluded

The bundle does not query or serialize the following database payload columns:

- `source_items.raw_text`;
- `source_items.raw_json`.

It also intentionally excludes:

- bearer/JWT tokens;
- cookies;
- Microsoft access tokens;
- school email addresses;
- announcement/email body text;
- assignment or quiz content;
- grade values;
- downloaded PDFs/PPTs/files;
- file contents.

Diagnostic error strings are additionally redacted for common email/token/URL/user-home patterns before being written.

## Why one bundle

Before this command, a debugging session could require separate output from:

```text
academicos-doctor
academicos-health
academicos-capabilities
academicos-coverage
```

Those commands remain useful interactively. The audit bundle simply combines their non-sensitive state into a consistent machine-readable artifact.

## After the live audit

If the live audit shows Brightspace authentication and the expected endpoints are usable, run one real sync:

```powershell
.\.venv\Scripts\academicos-sync.exe --config config.local.toml
```

Then run another local bundle:

```powershell
.\.venv\Scripts\academicos-audit.exe --config config.local.toml
```

The second bundle will include source-health, manifest/cursor counts, and coverage learned from the real synchronization without making additional live authentication calls.
