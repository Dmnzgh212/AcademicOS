# Roadmap

## Phase 0 — Bootstrap
- structure
- SQLite schema design
- configuration
- privacy/egress policy
- source/evidence model
- tests

## Phase 1 — Calendar v0.1
- import timetable
- recurring course sessions
- Truth Calendar
- Plan Calendar
- overrides
- manual tasks
- local week/day views
- morning brief
- evening summary

## Phase 2 — Brightspace academic events
- adapt vetted portions of d2l-cli
- SSO/token/session handling
- announcements
- assignments/deadlines
- quizzes
- calendar
- hashing/snapshot/diff
- candidate extraction
- alerts

## Phase 3 — Academic email
- relevant-sender/course filtering
- email-to-course linking
- event/task extraction
- evidence/confidence
- duplicate detection

## Phase 4 — Adaptive planner
- chunking
- urgency/workload pressure
- free/busy
- slot scoring
- actual-time tracking
- personal duration multipliers
- event-driven replanning
- schedule quality
- weekly capacity

## Phase 5 — Local LLM optimizer
- Ollama hardware/model profiling
- TTFT/prefill/decode benchmarks
- context sweet-spot discovery
- KV cache/Flash Attention experiments
- stable context buckets
- prompt prefix stability
- exact response cache
- optional prompt compression
- speculative decoding tuning

## Phase 6 — Course knowledge
- immutable source downloads
- Docling/local parsing
- chunking
- FTS5
- sqlite-vec
- hybrid retrieval
- citations

## Phase 7 — Lecture model
- Zoom transcript acquisition
- timestamp preservation
- slides/transcript/note alignment
- local OCR/vision
- unified Lecture entity

## Phase 8 — AI Tutor
- provider abstraction
- Ollama local provider
- explicit cloud API provider
- RAG context builder
- FAST/DEEP modes
- source-grounded tutoring
