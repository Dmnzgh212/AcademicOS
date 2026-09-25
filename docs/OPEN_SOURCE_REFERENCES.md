# Open-Source Reference Catalog

Listing a project here does not mean its code has been copied.

| Project | Primary value | Reuse status |
|---|---|---|
| Aaryan-Kapoor/d2l-cli | Brightspace SSO/token/API client | Planned selective adaptation |
| jiujiastudy / 救驾 | deterministic planner/state machine | Conceptual adaptation |
| tom1030507/OpenNotebookLM | SQLite hybrid RAG/citations | Planned selective adaptation |
| PndaMan/cortex | study OS/OCR/lecture UX | Reference |
| potlakai/nus | brief/due/quest/capture UX | Reference |
| FluxureCalendar/Fluxure | chunking/slot scoring/schedule quality | Reimplement concepts; AGPL caution |
| super-productivity/super-productivity | timeboxing/actual vs estimate | Reference/selective adaptation after license review |
| GothenburgBitFactory/taskwarrior | dynamic urgency | Reimplement concepts |
| TimefoldAI/timefold-solver | hard/soft constraints | Reference |
| google/or-tools | future Python CP-SAT scheduler | Potential dependency |
| ActivityWatch/activitywatch | optional activity feedback | Optional reference/integration |
| tanavc1/local-llm-autotune | Ollama context/profiling | Reimplement vetted parts; exclude telemetry |
| ArthurusDent/optimal-ollama | context/VRAM sweet-spot search | Reimplement strategy |
| xbrxr03/local-llm-gpu-bench | TTFT/prefill/decode benchmark | Reimplement methodology |
| peva3/SmarterRouter | cache/VRAM management | Selective concepts |
| microsoft/LLMLingua | local prompt compression | Potential optional dependency |
| FasterDecoding/Medusa | speculative decoding | Research |
| solo1337-del/zoom-recording-downloader | shared Zoom technique | Technique only |
| georgeb3/zoom-recording-downloader | Zoom OAuth downloader | Reference |
| ricardorodrigues-ca/zoom-recording-downloader | Zoom OAuth downloader | Reference |
| Harshal-Bsys27/ai-study-planner | study planner comparison | Reference |
| Muhammed-Shameel/AI-Planner | availability/calendar analytics UX | Reference |
| xavifernando/super-productivity-ai-calendar-planner | timeblocking plugin UX | Reference |

## License discipline

Before copying substantial code:
1. verify the current LICENSE;
2. record upstream commit SHA;
3. check compatibility;
4. preserve notices;
5. record derived files in `THIRD_PARTY_NOTICES.md`.

Known from research:
- `Aaryan-Kapoor/d2l-cli` — MIT
- `tom1030507/OpenNotebookLM` — MIT
- `microsoft/LLMLingua` — MIT
- `FluxureCalendar/Fluxure` — AGPL-3.0
- `TimefoldAI/timefold-solver` — Apache-2.0

Other licenses must be re-verified before code reuse.
