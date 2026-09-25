# OpenNotebookLM and Cortex — local knowledge/study-OS references

Upstreams:
- `tom1030507/OpenNotebookLM`
- `PndaMan/cortex`

Role in AcademicOS: references for the later **course knowledge base, retrieval, lecture model, OCR, and study UX** phases.

# OpenNotebookLM

## Strongest reusable ideas

- SQLite as the local knowledge store;
- FTS5/BM25 sparse retrieval;
- sqlite-vec dense retrieval;
- hybrid retrieval with reciprocal-rank fusion;
- heading-aware document chunking;
- local embeddings;
- source-grounded citations;
- CJK-friendly retrieval/tokenization techniques.

This is a good match for AcademicOS because it avoids a separate vector database and keeps the future knowledge layer inside the same local project.

Potential AcademicOS pipeline:

```text
local source file
 -> immutable original + SHA256
 -> parse to normalized Markdown/text
 -> heading-aware chunks
 -> FTS5 index
 -> local embeddings / sqlite-vec
 -> hybrid retrieval
 -> source-grounded local/cloud-explicit tutor
```

## What not to import

OpenNotebookLM also supports multiple cloud LLM providers and broader importers. AcademicOS should not inherit cloud provider auto-selection, web importers, or a whole Docker/FastAPI/Next stack just to get retrieval.

Use only the local retrieval/citation concepts and selectively adapted compatible code.

License observed during research: MIT. Re-verify before copying.

# Cortex

Cortex is useful more as a **product/data-model reference** than a dependency.

Interesting concepts:

- Subjects -> Topics -> Sources hierarchy;
- local-first desktop study environment;
- PDF/PPTX/DOCX/text/web/audio/image ingestion;
- vision OCR for handwriting/images;
- lecture recording, transcription, and summary workflow;
- flashcards/FSRS;
- quizzes/exams;
- weak-topic and mastery views;
- calendar/deadline integration.

AcademicOS should borrow these product concepts later without importing its entire Rust/Tauri/Svelte architecture.

## AcademicOS-specific lecture entity

The future target is a unified lecture object:

```text
Lecture 5 — CPU Datapath
  professor slides
  Zoom transcript
  personal note photos
  related announcement
  related lab/assignment
  derived summary/concepts/emphasis
```

Source material remains immutable; generated material is derived and reproducible.

## Boundary with Calendar v0.1

None of this is required to make the calendar useful. The knowledge layer should only begin after source sync, Truth Calendar, tasks, and adaptive planning are stable.
