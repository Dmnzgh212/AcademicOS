# Real uOttawa Account Validation

This runbook validates AcademicOS against the user's actual Windows machine and uOttawa source systems without performing any write operation against Brightspace or Microsoft 365.

## 1. Prepare the local environment

From the AcademicOS repository root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\first_run_windows.ps1
```

The script:

- creates `.venv` with Python 3.11 if needed;
- installs AcademicOS with Brightspace and Microsoft 365 optional dependencies;
- creates `config.local.toml` from the example if it does not already exist;
- runs the local-only doctor.

It does **not** log into Brightspace, access email, register a scheduled task, or send data to an AI service.

## 2. Check the local config

The default Brightspace host is:

```toml
[brightspace]
enabled = true
host = "https://uottawa.brightspace.com"
```

For the first live validation, Microsoft 365 may remain disabled:

```toml
[mail]
enabled = false
```

That lets Brightspace be validated independently of Microsoft app-registration setup.

## 3. Run the live Brightspace doctor

```powershell
.\.venv\Scripts\academicos-doctor.exe --live --bootstrap-auth --config config.local.toml
```

If AcademicOS does not already have a valid Brightspace session, a dedicated persistent browser opens. Complete the normal uOttawa SSO/MFA flow. AcademicOS saves only its local browser profile and captured Brightspace bearer token under `.auth/`, which is excluded from Git.

The doctor then performs minimal GET-only probes:

- Brightspace `whoami`;
- active enrollments;
- local-course discovery if a timetable has already been imported;
- one mapped course's news;
- assignments;
- quizzes;
- content TOC;
- grades;
- calendar;
- updates.

Endpoint failures are reported separately because individual Brightspace features can legitimately be disabled or permission-restricted by a course or institution.

## 4. Share the audit result safely

A redacted JSON report is written by default to:

```text
data/audits/latest-doctor.json
```

The report intentionally excludes:

- Brightspace bearer tokens;
- cookies;
- Microsoft access tokens;
- email addresses/account IDs;
- email bodies;
- course material bodies;
- downloaded files.

The terminal output or this JSON report can be shared for troubleshooting.

## 5. If no timetable is imported yet

The account and authentication probes can still pass. Course discovery may show:

```text
WARN brightspace.course_discovery mapped=0 ...
```

That is expected until the semester timetable exists in the local AcademicOS database.

Once the timetable is imported, rerun the doctor and the mapping check should become meaningful.

## 6. Microsoft 365 validation

Microsoft 365 support uses delegated read-only `User.Read` + `Mail.Read` permissions and a public-client application ID.

After a valid client ID is configured:

```toml
[mail]
enabled = true
client_id = "YOUR_PUBLIC_CLIENT_APP_ID"
use_delta = true
```

Then rerun:

```powershell
.\.venv\Scripts\academicos-doctor.exe --live --bootstrap-auth --config config.local.toml
```

If no cached token exists, MSAL starts Microsoft device-code authentication. The doctor only verifies account identity and a one-item Inbox read; it does not advance the production delta cursor or download attachments.

## 7. Only after live validation succeeds

Run the real collection once manually:

```powershell
.\.venv\Scripts\academicos-sync.exe --config config.local.toml
```

Then inspect health:

```powershell
.\.venv\Scripts\academicos-health.exe --db D:\AcademicOSData\academicos.db
```

If source health looks correct, scheduled collection can be installed:

```powershell
.\.venv\Scripts\academicos-schedule.exe install --minutes 30 --config config.local.toml
```

Do not install the scheduled job before the first manual sync is known to work.

## Validation success criteria

Brightspace first-live validation is considered successful when:

- local database is schema v4;
- data directory is writable;
- a valid/recoverable Brightspace session exists;
- `whoami` succeeds;
- active enrollments are returned;
- course discovery either maps imported courses or clearly reports why it cannot;
- major course endpoints either pass or fail in an isolated, explainable way.

Full source-collection validation is considered successful only after one real `academicos-sync` run also produces healthy `source_health` rows and expected local files/source items.
