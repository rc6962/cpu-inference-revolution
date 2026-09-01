# Qwen 1.5B vs 3B CPU Benchmark Report

**Date:** 2026-09-01
**Status:** Exploratory single-machine model comparison — not a production benchmark

---

## Benchmark execution

| Field | Value |
|-------|-------|
| Execution commit SHA | `dc51d19` |
| OS | Windows 11 Pro (10.0.26200) |
| CPU | Intel i7-11700T (8C/16T @ 1.40GHz) |
| RAM | 15.45 GB total |
| Python | 3.11.15 |
| llama-cpp-python | 0.3.35 (pre-built CPU wheel) |
| Benchmark cases | 30 (8 calculation, 8 retrieval, 7 extraction, 7 generation) |
| Measured runs per model/mode | 5 |
| Warmup passes per model | 2 (discarded) |

---

## Model details

| Field | Qwen2.5-1.5B-Instruct | Qwen2.5-3B-Instruct |
|-------|----------------------|---------------------|
| Quantization | Q4_K_M | Q4_K_M |
| File size | 1.04 GB | 2.0 GB |
| SHA-256 | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` | (not computed this run) |
| Source | HuggingFace Qwen/Qwen2.5-1.5B-Instruct-GGUF | HuggingFace Qwen/Qwen2.5-3B-Instruct-GGUF |
| n_ctx | 512 | 512 |
| n_threads | 8 | 8 |
| max_tokens | 256 | 256 |
| temperature | 0.0 | 0.0 |

---

## Fixed comparison settings

All runs used identical:
- 30-case benchmark file (`data/benchmark_cases.jsonl`)
- Database regenerated from current `data/seed.jsonl` (13 documents)
- Same routing/retrieval implementation (no code changes)
- Same model settings (n_ctx=512, n_threads=8, max_tokens=256, temperature=0.0)
- Same warmup procedure (2 passes per model, discarded)
- Same machine, same power profile

**Unavoidable difference:** Model file size (1.04 GB vs 2.0 GB) and parameter count (1.5B vs 3B) are inherent to the models being compared.

---

## Artifact directory

```
results/model-comparison/dc51d19/
  qwen2.5-1.5b-q4_k_m/
    mode_b_run_01.json through mode_b_run_05.json
    mode_c_run_01.json through mode_c_run_05.json
  qwen2.5-3b-q4_k_m/
    mode_b_run_01.json through mode_b_run_05.json
    mode_c_run_01.json through mode_c_run_05.json
```

---

## Product comparison: Mode B (modular)

| Metric | 1.5B | 3B | Delta |
|--------|------|-----|-------|
| Total wall (5 runs) | 166,721 ms | 336,509 ms | **-50%** |
| Mean wall per run | 33,344 ms | 67,302 ms | **-50%** |
| CV | 13.3% | 5.4% | Higher variance |
| Score | 145/150 (97%) | 148/150 (99%) | -2 |
| Correct-task cost | 1,150 ms/task | 2,277 ms/task | **-49%** |
| Real-model-call cost | 2,223 ms/call | 4,610 ms/call | **-52%** |

### Mode B per-category quality

| Category | 1.5B | 3B |
|----------|:----:|:--:|
| calculation (STRONG) | 40/40 (100%) | 40/40 (100%) |
| retrieval (MODERATE) | 35/40 (88%) | 38/40 (95%) |
| extraction (STRONG) | 35/35 (100%) | 35/35 (100%) |
| generation (WEAK) | 35/35 (100%) | 35/35 (100%) |

**1.5B loses 3 retrieval cases that 3B gets right.** These are the edge cases where the smaller model's answer doesn't contain the expected key fact substring.

---

## Product comparison: Mode C (forced)

| Metric | 1.5B | 3B | Delta |
|--------|------|-----|-------|
| Total wall (5 runs) | 254,669 ms | 495,489 ms | **-49%** |
| Mean wall per run | 50,934 ms | 99,098 ms | **-49%** |
| CV | 4.8% | 0.7% | Higher variance |
| Score | 90/150 (60%) | 80/150 (53%) | +10 |
| Correct-task cost | 2,830 ms/task | 6,194 ms/task | **-54%** |
| Real-model-call cost | 1,698 ms/call | 3,303 ms/call | **-49%** |

### Mode C per-category quality

| Category | 1.5B | 3B |
|----------|:----:|:--:|
| calculation (STRONG) | 20/40 (50%) | 10/40 (25%) |
| retrieval (MODERATE) | 0/40 (0%) | 0/40 (0%) |
| extraction (STRONG) | 35/35 (100%) | 35/35 (100%) |
| generation (WEAK) | 35/35 (100%) | 35/35 (100%) |

**1.5B actually scores higher than 3B on forced calculation (50% vs 25%).** The smaller model produces simpler numeric outputs that happen to match the expected format more often.

---

## Pooled per-request latency (150 samples per model/mode)

| Metric | 1.5B Modular | 3B Modular | 1.5B Forced | 3B Forced |
|--------|-------------|-----------|-------------|-----------|
| Mean | 1,111 ms | 2,243 ms | 1,698 ms | 3,303 ms |
| p50 | 450 ms | 933 ms | 974 ms | 2,811 ms |
| p95 | 4,666 ms | 9,176 ms | 4,957 ms | 9,714 ms |
| p99 | 7,062 ms | 12,553 ms | 9,837 ms | 14,655 ms |

---

## Cost summary

| Metric | 1.5B Modular | 3B Modular | 1.5B Forced | 3B Forced |
|--------|-------------|-----------|-------------|-----------|
| Correct tasks | 145/150 | 148/150 | 90/150 | 80/150 |
| Correct-task cost | 1,150 ms | 2,277 ms | 2,830 ms | 6,194 ms |
| Real LLM calls | 75 | 73 | 150 | 150 |
| Real-model-call cost | 2,223 ms | 4,610 ms | 1,698 ms | 3,303 ms |

---

## RAM observation

RAM was not directly measured during model loading in this run. Based on file sizes:
- 1.5B Q4: ~1.04 GB file, estimated ~1.5–2 GB loaded
- 3B Q4: ~2.0 GB file, estimated ~2.5–3.5 GB loaded

The 1.5B model uses approximately **half the RAM** of the 3B model, consistent with the parameter count ratio.

---

## Recommendation

**Retain 1.5B for escalation testing, but do not adopt as default yet.**

| Criterion | Assessment |
|-----------|------------|
| Latency reduction | ✅ **Consistent ~50% faster** across both modes |
| Quality on strong categories (calc, extraction) | ✅ **Identical** — 100% in modular mode |
| Quality on moderate category (retrieval) | ⚠️ **1.5B loses 3/40 cases** vs 3B's 2/40 — small but real gap |
| Quality on weak category (generation) | ✅ **Identical** — 100% in both |
| Forced-mode calculation | ✅ **1.5B actually better** (50% vs 25%) |
| RAM reduction | ✅ **~50% less RAM** expected |
| Variance | ⚠️ 1.5B shows higher CV (13.3% vs 5.4% in modular) |

**The evidence supports a future experiment: use 1.5B as the default for deterministic routes (no model) and retrieval/generation, with 3B escalation for retrieval cases where 1.5B fails.** However, the 3-case retrieval quality gap means 1.5B cannot be a drop-in replacement without an escalation mechanism.

---

## Known limits

- Fixed 30-case suite on one machine. Results may not generalize.
- 150 measured samples per model/mode. p99 is exploratory.
- No prompt-processing/decode time separation — cannot attribute latency differences to specific model stages.
- RAM observation is estimated from file size, not measured at runtime.
- 1.5B CV is higher (13.3%), suggesting less consistent performance — more runs needed to confirm stability.
