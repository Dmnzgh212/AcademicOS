# d2l-cli — Brightspace acquisition reference

Upstream: `Aaryan-Kapoor/d2l-cli`

Role in AcademicOS: **primary reference for the Brightspace connector**.

## Why it matters

The project demonstrates a practical way to access modern D2L Brightspace installations that rely on normal browser SSO/MFA rather than asking the user to manually manage legacy app credentials.

Key pattern:

```text
persistent Playwright Chromium profile
    -> normal SSO/MFA
    -> capture D2L bearer token
    -> reuse token with requests.Session
    -> refresh/re-auth through the browser when necessary
```

## Important mechanisms found during research

- persistent browser profile rather than a disposable login every sync;
- token capture from outgoing `Authorization` headers;
- token recovery from D2L browser storage (`D2L.Fetch.Tokens`) and auth flows;
- a read-only client for courses/enrollments, grades, assignments, submissions, quizzes, content/modules/topics, discussions, announcements/news, calendar, due/overdue items, and file downloads;
- machine-friendly JSON/Markdown output.

Relevant conceptual module split for AcademicOS:

```text
sources/brightspace/
  auth.py
  client.py
  resolver.py
  download.py
  normalize.py
```

## What AcademicOS should add

`d2l-cli` is primarily an access tool. AcademicOS needs a historical intelligence layer on top:

- stable normalized IDs;
- canonical hashes;
- snapshot/diff;
- append-only change events;
- source/evidence records;
- duplicate detection;
- mapping to Calendar/Task/Activity entities.

For example:

```text
Brightspace news item changes
 -> normalize
 -> compare previous hash
 -> announcement.changed
 -> event extraction
 -> candidate calendar/task update
```

## Privacy/security requirements

- browser profile and bearer tokens stay outside the Git repository;
- use a dedicated AcademicOS browser profile;
- source syncing may access Brightspace/uOttawa authentication endpoints, but downloaded/derived data remains local unless the user explicitly requests external AI analysis;
- connector should remain read-only wherever possible.

## Reuse strategy

Selective adaptation is preferred over running d2l-cli as a permanent sidecar service.

License observed during research: MIT. Re-verify the upstream LICENSE and pin the exact upstream commit before copying source code.
