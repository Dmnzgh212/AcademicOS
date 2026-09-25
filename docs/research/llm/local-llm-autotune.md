# local-llm-autotune — Ollama optimization research

Upstream: `tanavc1/local-llm-autotune`

Role in AcademicOS: reference for a **local Ollama optimization layer**, not a replacement inference engine.

## Valuable ideas

- hardware profiling;
- per-model optimization profiles;
- dynamic context sizing;
- stable context buckets;
- memory-pressure handling;
- keep-alive/session behavior;
- TTFT and throughput benchmarking;
- avoiding repeated expensive reconfiguration.

A useful AcademicOS shape is:

```text
hardware + Ollama version + model digest
        -> benchmark/search
        -> saved profile
        -> fast / balanced / long-context presets
```

## Stable context buckets

Do not resize `num_ctx` to arbitrary values on every request. Prefer buckets such as:

```text
4096
6144
8192
12288
16384
32768
```

Then choose the smallest bucket that safely fits retrieved context + answer budget + margin. Stable buckets improve runner/cache reuse and reduce unnecessary reload/reallocation behavior.

## Privacy issue discovered during audit

The upstream project contains optional remote telemetry/Supabase paths and remote metadata behavior. AcademicOS's optimizer must **not copy those modules**.

Do not import:

- telemetry client/consent code;
- Supabase usage mirror;
- remote behavioral/performance upload;
- remote model-metadata fetching during normal runtime.

Model metadata should come from local Ollama inspection where possible.

## Compatibility warning

Ollama evolves quickly. Some parameters used by older optimizer code may become deprecated or change semantics.

Rule:

> Validate every tuning parameter against the currently installed Ollama version before applying it.

Prefer Ollama's automatic behavior unless benchmarking proves an explicit override is better.

## Reuse strategy

Borrow optimization/search algorithms and profile design selectively. Do not install the whole project as a permanent middleware service unless a future audit shows that doing so is simpler and equally private.

License observed during research: MIT. Re-verify upstream before copying source.
