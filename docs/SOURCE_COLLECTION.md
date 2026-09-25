# Source Collection Architecture

AcademicOS treats collection as a local, deterministic subsystem. Background jobs may authenticate to the original source systems, fetch student-visible data, hash it, persist it locally, and download files. They do not invoke external AI services.

## Brightspace

Authentication is based on a dedicated persistent Chromium-family profile. A one-time interactive login completes uOttawa SSO/MFA; later background runs reuse that profile and request/capture a short-lived Brightspace bearer token locally.

The collector is read-only for academic data. It currently collects:

- account identity (`whoami`)
- active enrollments
- activity feed
- course announcements/news
- assignments and the student's submissions
- quizzes and attempts
- content table of contents, roots, and module structures
- grade values, grade objects, and final grade
- course calendar events
- due and overdue items
- course updates
- discussion forums/topics/posts
- checklists and course overview
- directly downloadable course-content files
- assignment attachments

Course mapping is automatic by default. AcademicOS compares local timetable course codes/sections with active Brightspace Course Offering enrollments. Ambiguous mappings are reported rather than guessed. A manual `[[brightspace.courses]]` entry can override an ambiguous course.

## Microsoft 365 mail

uOttawa mail collection uses Microsoft Graph delegated read-only permissions. The collector stores message metadata/body locally. Authentication tokens are cached under `.auth/` and are excluded from Git.

The preferred Inbox mode uses Microsoft Graph delta queries:

```text
first sync
  → /me/mailFolders/inbox/messages/delta
  → follow @odata.nextLink pages
  → persist @odata.deltaLink

later sync
  → request the opaque deltaLink directly
  → receive additions / updates / removals only
  → persist the next deltaLink only after the page chain completes
```

Removed messages are retained locally as tombstone source changes rather than silently disappearing from acquisition history.

A timestamp-filter Inbox collector remains available as a compatibility fallback by setting `mail.use_delta = false`.

## Incremental collection

`sync_state` stores a per-source cursor and last successful collection time.

Current cursor behavior:

- Brightspace activity feed: last-success timestamp;
- per-course Brightspace announcements: last-success timestamp;
- Microsoft 365 Inbox: opaque Graph `@odata.deltaLink` by default.

Successful source runs advance their cursor; failed or incomplete delta runs do not. In particular, if a Graph delta page chain does not reach a durable deltaLink within the configured page bound, AcademicOS refuses to advance the saved cursor.

## File manifest

Schema v4 adds a persistent `file_manifest`.

For downloadable Brightspace content and assignment attachments, AcademicOS records:

- stable source key;
- local destination path;
- remote metadata fingerprint;
- local SHA256;
- byte size;
- ETag/Last-Modified when the source provides them;
- last checked/downloaded timestamps.

If the remote metadata fingerprint is unchanged and the recorded local file still exists with the expected size, the binary request is skipped. This avoids downloading the same lecture PDFs every scheduled run just to compare bytes afterward.

## Collection health

Schema v4 also adds `source_health`. Each logical collector records:

- current status;
- last attempt;
- last successful collection;
- latest error;
- consecutive failure count;
- changed/unchanged item counts;
- downloaded-file count;
- source-specific metadata.

Inspect it locally with:

```text
academicos-health --db D:/AcademicOSData/academicos.db
```

The command labels sources as `OK`, `STALE`, or `ERROR`, making authentication expiry and silent collector failure visible before a morning brief relies on stale data.

## Local storage

Raw source objects are normalized into `source_items` with:

- stable source identifier;
- source type;
- optional course mapping;
- source timestamp;
- fetch timestamp;
- canonical content hash;
- raw text when available;
- raw JSON.

Unchanged objects are recognized by hash and do not create duplicate logical records.

Downloaded files live under the configured local `data_dir`, never inside the source-code repository.

## Scheduled operation

The intended unattended loop is:

```text
Windows Task Scheduler
        ↓
academicos-sync --config config.local.toml
        ↓
Brightspace token reuse/refresh
        ↓
Brightspace + M365 read-only collection
        ↓
source_items / local files / sync_state
        ↓
file_manifest + source_health
        ↓
(optional deterministic extraction/planning)
```

AcademicOS can register the task for the current Windows user:

```text
academicos-schedule install --config config.local.toml --minutes 30
academicos-schedule status
academicos-schedule remove
```

The scheduler command uses Windows `schtasks` and invokes the same local Python environment that installed AcademicOS. It does not install a Windows service.

A failed Brightspace endpoint is isolated so one unavailable feature does not abort collection from other endpoints or courses.

## Privacy boundary

Background collection may communicate only with the configured source systems required to retrieve the user's own data (for example uOttawa Brightspace and Microsoft Graph). Raw academic content is not sent to third-party AI services by the collection job.
