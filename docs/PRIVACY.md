# Privacy and Data-Egress Policy

## Goal

Academic and personal data may be acquired from original source systems and stored locally, but background processing must not silently transmit that data to unrelated third-party services.

## Allowed background network access

Examples:
- uOttawa/Brightspace and required authentication endpoints
- selected academic email source
- Zoom recording source when configured
- package/model downloads during explicit installation/model management

## Local processing by default

Run locally:
- SQLite storage
- hashing/diffing
- calendar/event processing
- scheduling
- local parsing where possible
- local embeddings
- OCR/vision when local models are configured
- Ollama inference
- local LLM performance optimization
- local brief generation

## External AI

Cloud AI is allowed only through explicit user-triggered actions or a future user-enabled policy.

Default:

```toml
cloud_policy = "explicit_only"
background_cloud_calls = false
```

No background sync job may silently summarize course content through a cloud AI provider.

## Outbound Gate

All cloud-AI calls should route through one controlled abstraction and record provider, user-triggered action, selected sources, approximate payload size, and timestamp.

## Telemetry

Do not import remote telemetry, Supabase mirrors, or analytics code unless explicitly reviewed and needed.

## GitHub

The repository contains source code and non-sensitive design documentation only.

Do not commit Brightspace data, course files, announcements, email bodies, grades, IDs, tokens, cookies, browser profiles, transcripts, note photos, SQLite DBs, embeddings, or indexes.

## OneDrive/private sync

A user-chosen private sync location such as OneDrive may be used as `data_dir`. This is an explicit storage decision and is distinct from silent telemetry.
