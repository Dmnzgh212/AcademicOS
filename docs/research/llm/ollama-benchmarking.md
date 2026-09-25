# Ollama benchmarking — optimal-ollama + local-llm-gpu-bench

Upstreams:
- `ArthurusDent/optimal-ollama`
- `xbrxr03/local-llm-gpu-bench`

Role in AcademicOS: reference for finding the **real hardware/model sweet spot** instead of trusting generic tuning advice.

# optimal-ollama

## Core idea

Sweep context sizes upward and stop when one of the important signals collapses:

- VRAM spillover / CPU offload;
- generation throughput drops below threshold;
- prompt processing becomes too slow;
- RAM/VRAM use exceeds budget.

This turns context selection into an empirical search problem.

AcademicOS should search a bounded set of buckets rather than every integer size:

```text
4K -> 6K -> 8K -> 12K -> 16K -> 24K -> 32K -> ...
```

For each point record:

- load time;
- TTFT;
- prompt/prefill tok/s;
- generation/decode tok/s;
- VRAM;
- system RAM;
- GPU/CPU placement if observable.

Save the best safe bucket per model/hardware profile.

## Windows caution

The upstream project was not treated as a drop-in Windows solution during research. AcademicOS should reimplement the search strategy around Windows/Ollama APIs rather than assume Linux process/GPU behavior.

# local-llm-gpu-bench

This project is valuable as a **measurement methodology**.

Metrics worth preserving:

- cold model load;
- TTFT;
- prefill throughput;
- decode throughput;
- context scaling;
- VRAM utilization;
- GPU utilization;
- RAM usage;
- temperature/power/clock when practical;
- thermal throttling awareness.

## Benchmark integrity

Benchmarking must distinguish three different things:

```text
load latency
prompt/prefill speed
decode generation speed
```

An optimizer can dramatically improve load/prefill latency while decode tok/s remains almost unchanged. Report them separately.

Avoid benchmarking with accidentally warm prefix/KV caches unless the benchmark is intentionally measuring cache reuse.

## AcademicOS AutoTune plan

Re-run tuning when one of these fingerprints changes:

- Ollama version;
- model digest/quantization;
- GPU/VRAM;
- GPU driver;
- major hardware change.

Otherwise load the saved profile immediately.

Potential profiles:

```text
fast          -> smaller safe context, low TTFT
balanced      -> normal study/RAG workload
long_context  -> larger context, more aggressive memory trade-offs
```

## Key principle

Optimization must be **measured on the user's machine**. Generic claims like "set batch to X" or "more context is better" are not accepted without local evidence.
