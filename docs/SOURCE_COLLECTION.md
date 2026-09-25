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

uOttawa mail collection uses Microsoft Graph delegated read-only permissions. The collector stores message metadata/body locally and can download supported attachments. Authentication tokens are cached under `.auth/` and are excluded from Git.

The inbox collector supports a `since` timestamp and bounded pagination.

## Incremental collection

`sync_state` stores a per-source cursor and last successful collection time. Successful source runs advance their cursor; failed runs do not. The next run reuses the cursor for endpoints that support incremental time filtering, including Brightspace announcements/activity feed and Microsoft 365 Inbox.

This reduces network traffic and avoids repeatedly processing an entire semester of unchanged data.

## Local storage

Raw source objects are normalized into `source_items` with:

- stable source identifier
- source type
- optional course mapping
- source timestamp
- fetch timestamp
- canonical content hash
- raw text when available
- raw JSON

Unchanged objects are recognized by hash and do not create duplicate logical records.

Downloaded files live under the configured local `data_dir`, never inside the source-code repository.

## Scheduled operation

The intended unattended loop is:

```text
Windows Task Scheduler
        ↓
academicos-sync --config config.toml
        ↓
Brightspace token reuse/refresh
        ↓
Brightspace + M365 read-only collection
        ↓
source_items / local files / sync_state
        ↓
(optional later deterministic extraction/planning)
```

A failed endpoint is isolated so one unavailable Brightspace feature does not abort collection from other endpoints or courses.

## Privacy boundary

Background collection may communicate only with the configured source systems required to retrieve the user's own data (for example uOttawa Brightspace and Microsoft Graph). Raw academic content is not sent to third-party AI services by the collection job.
