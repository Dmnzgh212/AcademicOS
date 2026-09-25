# Local LLM request-path optimizations — cache, compression, speculative decoding

References:
- `peva3/SmarterRouter`
- `microsoft/LLMLingua`
- `FasterDecoding/Medusa`
- current Ollama prompt-cache/speculative capabilities observed during research

Role in AcademicOS: reduce **work done per tutor request** before considering invasive engine changes.

# 1. Prefix / prompt-cache friendly prompting

Ollama already benefits from repeated prompt prefixes. AcademicOS should therefore compile prompts deterministically:

```text
stable system prompt
 -> stable course/tutor profile
 -> stable retrieved source chunks in canonical order
 -> dynamic user question last
```

Avoid volatile data near the front of the prompt such as request IDs or timestamps.

For RAG, sort retrieved chunks deterministically (for example course -> lecture -> page -> chunk ID) so identical evidence produces identical prefixes.

# 2. Exact response cache

SmarterRouter is useful as a reference for caching behavior, but AcademicOS should begin conservatively with **exact cache only**.

Suggested cache key:

```text
model_digest
+ generation_parameters
+ tutor_prompt_version
+ retrieved_source_hashes
+ normalized_user_prompt
```

If any source document changes, its hash changes and the old answer automatically stops matching.

This gives a true zero-inference response for exact repeated questions while avoiding unsafe semantic-answer reuse.

# 3. Semantic cache — not default

SmarterRouter also demonstrates embedding/similarity-based cache ideas.

Academic tutoring has a high correctness cost, so semantic answer reuse should remain experimental. Similar wording does not guarantee the same mathematical/code context.

If added later, semantic cache should preferably reuse **retrieval results or intermediate artifacts**, not blindly return an old final answer.

# 4. Prompt compression with LLMLingua

LLMLingua / LongLLMLingua / LLMLingua-2 provide a local way to shorten long prompts before Ollama sees them.

Best AcademicOS use case:

```text
long natural-language transcript / verbose RAG context
 -> local selective compression
 -> smaller Ollama prefill
```

Expected benefit is primarily:

- lower prefill cost;
- lower TTFT;
- lower KV-cache pressure;
- ability to fit useful evidence inside a smaller context bucket.

Do **not** blindly compress:

- equations;
- source code;
- exact definitions;
- circuit expressions;
- tables where token deletion changes semantics.

Compression should be source-type aware and optional.

License observed for `microsoft/LLMLingua`: MIT. Re-verify before adding as a dependency or copying source.

# 5. Speculative / multi-token decoding

Medusa is a research reference showing the broader idea of predicting multiple future tokens and verifying them.

AcademicOS should not train or maintain Medusa heads in the first implementation.

Prefer capabilities already exposed by the installed Ollama/model stack, such as compatible draft models, MTP, or other supported speculative paths.

Optimizer strategy:

```text
if speculative mode is supported:
    benchmark draft depth candidates
    compare decode tok/s and memory use
    save only if measurably better
else:
    leave disabled
```

# 6. Optimization priority

For the AcademicOS workload, optimize in this order:

1. avoid RAM/CPU spillover;
2. choose the correct context bucket;
3. preserve prompt-prefix cache reuse;
4. keep the active model warm during a study session;
5. reduce RAG input size / remove irrelevant chunks;
6. exact caching;
7. optional prompt compression;
8. speculative decoding when compatible;
9. low-level parameter overrides only when benchmarked.

This order targets user-visible latency without forking or replacing Ollama.
