# AcademicOS Research Archive

This directory turns the project's open-source discovery work into maintainable engineering notes.

The files here are **research dossiers**, not vendored copies of upstream projects. They record what was inspected, what AcademicOS may reuse, and where licensing or architecture requires caution.

## Rules

1. Keep the upstream repository name and relevant source paths.
2. Record the reason the project matters to AcademicOS.
3. Separate **ideas to reimplement** from **code that may be adapted**.
4. Verify the upstream license and a concrete commit/tag immediately before copying substantial source code.
5. Any actual copied/derived code must also be recorded in `THIRD_PARTY_NOTICES.md`.
6. Prefer small, auditable adaptations over importing an entire application stack.

## Current dossiers

### Brightspace
- `brightspace/d2l-cli.md`

### Scheduling and time management
- `scheduling/jiujiastudy.md`
- `scheduling/fluxure.md`
- `scheduling/super-productivity.md`
- `scheduling/taskwarrior.md`
- `scheduling/constraint-solvers.md`
- `scheduling/activitywatch.md`

### Knowledge / study OS
- `knowledge/open-notebooklm-cortex.md`

### Local LLM optimization
- `llm/local-llm-autotune.md`
- `llm/ollama-benchmarking.md`
- `llm/caching-compression-speculation.md`

### Zoom
- `zoom/shared-recording.md`

## Research date

Initial archive assembled 2026-09-25 from the design research that preceded Calendar v0.1.
