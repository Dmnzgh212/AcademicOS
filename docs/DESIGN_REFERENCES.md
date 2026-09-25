# Design References

This preserves the research behind AcademicOS so future maintainers and coding agents do not repeat the same discovery work.

## Aaryan-Kapoor/d2l-cli
Primary Brightspace reference:
- persistent Playwright SSO profile
- bearer token capture/refresh
- read-only Valence API
- courses, grades, assignments, quizzes, content, discussions, news, calendar
- attachment/file download

AcademicOS adds normalization, snapshots, hashes, diffs, and append-only change events.

## jiujiastudy / 救驾
Planner/state philosophy:
- JSON source of truth
- fresh collection before deadline reports
- script plans before AI wording
- MUST / SHOULD / PARKING
- normal / behind / stuck / overload states
- AI optional

## tom1030507/OpenNotebookLM
Knowledge layer:
- SQLite
- FTS5/BM25
- sqlite-vec
- hybrid retrieval
- reciprocal-rank fusion
- heading-aware chunks
- local embeddings
- citation validation
- CJK-aware retrieval ideas

## PndaMan/cortex
Product/data-model inspiration:
- Subjects -> Topics -> Sources
- local-first study OS
- documents/audio/images
- handwriting OCR with vision
- lecture/transcript model
- FSRS, quizzes, mastery

## potlakai/nus
UX inspiration:
- brief
- due
- quest
- capture
- crunch-week visibility

## FluxureCalendar/Fluxure
Strong Calendar v0.1 reference:
- pure scheduling engine
- greedy placement
- candidate slots
- priority ordering
- task chunking
- free/busy
- Gaussian ideal-time scoring
- buffer compliance
- dependency continuity
- schedule quality
- minimal calendar diff

Important: AGPL-3.0. Reimplement concepts independently unless the project licensing strategy deliberately changes.

## super-productivity/super-productivity
- timeboxing
- actual time tracking
- estimate vs spent
- remaining work
- planner UX
- local/privacy-first design

AcademicOS extends this with a personal estimation-bias model.

## GothenburgBitFactory/taskwarrior
Use dynamic urgency as a concept:
- due
- age
- blocking/blocked
- scheduled status
- coefficients
- dependencies
- recurrence

Replace generic urgency with academic factors.

## TimefoldAI/timefold-solver
Reference for:
- hard/soft constraints
- pinned planning entities
- timetabling
- score-based optimization

## google/or-tools
Future Python-native solver option:
- CP-SAT
- interval variables
- no-overlap
- combinatorial optimization

## ActivityWatch/activitywatch
Optional future feedback:
- local-first time tracking
- active app/window
- browser activity
- AFK events

Do not make passive tracking mandatory.

## tanavc1/local-llm-autotune
Borrow ideas:
- hardware profiling
- dynamic context
- stable context buckets
- memory pressure
- keep-alive
- TTFT metrics

Exclude telemetry/Supabase code and verify parameters against current Ollama.

## ArthurusDent/optimal-ollama
Borrow:
- context sweep
- VRAM spillover detection
- per-model sweet spot
- throughput/VRAM/RAM evaluation

## xbrxr03/local-llm-gpu-bench
Borrow benchmark methodology:
- cold load
- TTFT
- prefill tok/s
- decode tok/s
- context scaling
- GPU/VRAM telemetry

## peva3/SmarterRouter
Borrow selectively:
- exact response cache
- embedding cache
- LRU/TTL
- model profiling
- VRAM-aware management

Be conservative with semantic answer reuse for academic tutoring.

## microsoft/LLMLingua
Potential local preprocessing:
- LLMLingua
- LongLLMLingua
- LLMLingua-2
- selective prompt compression

Do not compress formulas/code/definitions blindly.

## FasterDecoding/Medusa
Research reference:
- multi-token/speculative generation

Prefer Ollama-supported speculative/MTP paths first.

## Zoom recording projects
- `solo1337-del/zoom-recording-downloader`: shared-link technique only; no license found during research, so do not copy code verbatim.
- `georgeb3/zoom-recording-downloader`: owner/API scenario reference.
- `ricardorodrigues-ca/zoom-recording-downloader`: owner/API scenario reference.

## Generic study planners reviewed
- `Harshal-Bsys27/ai-study-planner`
- `Muhammed-Shameel/AI-Planner`
- `xavifernando/super-productivity-ai-calendar-planner`

Useful mainly for UI/product comparison, not as the core AcademicOS scheduler.
