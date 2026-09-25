# Staged First Live Sync

AcademicOS should not make the first real uOttawa connection by immediately running the full unattended collector.

The first live collection is intentionally staged:

```text
live audit
   ↓
staged first sync
   ↓
sanitzed audit / coverage review
   ↓
full sync
   ↓
Windows Task Scheduler
```

## Command

```powershell
.\.venv\Scripts\academicos-first-sync.exe --config config.local.toml
```

If Microsoft 365 is enabled and interactive authorization is still required:

```powershell
.\.venv\Scripts\academicos-first-sync.exe --config config.local.toml --interactive-mail-auth
```

## What it reads

Brightspace:

- account identity enough to verify the session;
- active enrollments;
- automatic local-course mapping;
- announcements;
- assignments;
- quizzes;
- content table of contents;
- grades endpoint availability;
- calendar endpoint availability;
- updates.

Microsoft 365, when enabled:

- account identity;
- one Inbox **metadata-only** probe (`id`, timestamps, `hasAttachments`).

The staged mail probe does not request subject, body, body preview, sender, or recipients.

## What it writes locally

- ordinary deduplicated `source_items` snapshots for Brightspace top-level datasets;
- account identity snapshots used by normal collection;
- `endpoint_capabilities` results so later syncs can avoid known unavailable Brightspace endpoints.

These are local-only writes and are safe for a later full sync to encounter again.

## What it deliberately does not do

- does not advance `sync_state` cursors;
- does not create a Microsoft Graph delta cursor;
- does not download Brightspace files;
- does not download mail attachments;
- does not crawl nested assignment submissions;
- does not crawl quiz attempts;
- does not crawl discussion posts;
- does not expand all content modules;
- does not run announcement-to-calendar candidate extraction;
- does not install or invoke Windows Task Scheduler.

The important property is that a failed or partial first run cannot make the later full collector believe that unseen data has already been consumed.

## After staged validation

Generate another sanitized audit bundle:

```powershell
.\.venv\Scripts\academicos-audit.exe --config config.local.toml
```

Review:

- mapped course count;
- Brightspace endpoint coverage;
- unsupported/forbidden/transient endpoint status;
- errors from staged validation;
- absence of unexpected source failures.

Then run the real collector:

```powershell
.\.venv\Scripts\academicos-sync.exe --config config.local.toml
```

Only after the full sync is healthy should periodic Windows scheduling be enabled.
