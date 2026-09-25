# Sync Run Ledger + Data Completeness Audit

Date: 2026-09-25

Status: implemented and CI verified.

## Scope

This slice completed the Sync Run Ledger as a user-visible reliability feature rather than only a database table.

Implemented:
- full-sync run classification: `COMPLETE`, `PARTIAL`, `FAILED`, or `EMPTY`;
- all-source failures are classified as `FAILED` rather than `PARTIAL`;
- top-level `sync_all()` exceptions leave a content-free failed ledger entry before the exception is re-raised;
- latest and recent run queries;
- source-level rows for each run;
- `academicos-runs` CLI with bounded history and optional source detail;
- Morning Brief collection-quality warnings;
- Dashboard Attention inherits the same deterministic warnings through Morning Brief;
- freshness warning when the latest complete tracked sync is more than two hours old.

## User-facing semantics

`academicos-runs --limit 10 --sources` shows newest runs first without exposing source payloads.

Morning Brief / Dashboard warnings:
- `DATA UNKNOWN`: no tracked source sync exists yet;
- `DATA FAILED`: latest tracked sync failed at the top level or all sources failed;
- `DATA PARTIAL`: at least one source was partial/failed while some usable source data exists;
- `DATA EMPTY`: a tracked run produced no source results;
- `DATA STALE`: latest complete run is older than the current freshness threshold.

When a collection-quality warning exists, AcademicOS suppresses the otherwise reassuring `No immediate academic risk detected` message so incomplete data is not presented as an all-clear state.

## Privacy

The run ledger stores only:
- run IDs and timestamps;
- mode/status;
- counts of sources/items/downloads;
- source keys;
- source status and error count.

It does not copy exception text, email/announcement bodies, grades, downloaded files, tokens, cookies, or other source payloads into the ledger.

## Verification

Final GitHub Actions run for the code slice: `36194038858`.

Verified on:
- Python 3.11: Ruff passed, pytest passed;
- Python 3.12: Ruff passed, pytest passed.

Python 3.11 snapshot: **87 passed**.

Covered regression cases include:
- all-failed source classification;
- mixed partial/healthy source classification;
- newest-first run history;
- source detail lookup;
- top-level collector exception persistence as `FAILED`;
- `DATA UNKNOWN` before first tracked sync;
- `DATA PARTIAL` propagation into Morning Brief and rendered Dashboard;
- stale complete-run warning;
- suppression of false all-clear messaging when source completeness is uncertain.

## Remaining real-world validation

CI proves deterministic behavior, not uOttawa account behavior. The next source-collection validation step remains real Windows/uOttawa execution of live audit -> staged first sync -> full sync -> scheduled sync.
