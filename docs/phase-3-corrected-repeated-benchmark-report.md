# Phase 3 Corrected Repeated-Run Benchmark Report

**Date:** 2026-09-01
**Status:** Corrected measurement-semantics report following metadata reader/writer integration repair

---

## 1. Measurement Identity

| Field | Value |
|-------|-------|
| Execution commit | `f06a0c1` |
| Repetitions per mode | 5 |
| Cases per run | 30 (8 calculation, 8 retrieval, 7 extraction, 7 generation) |
| Process isolation | Fresh Python subprocess for every repetition |
| In-process model reuse | None — each run loads the model independently |
| Model (Modes B/C) | `qwen2.5-3b-instruct-q4_k_m.gguf` — 2,007 MB, Q4_K_M |
| CPU | Intel i7-11700T (8C/16T, 1.4 GHz base) |
| RAM | 15.45 GB |
| OS | Windows 10 (10.0.26200) |
| Python | 3.11.15 |
| llama-cpp-python | 0.3.35 |
| SQLite | 3.53.1 |
| FTS5 | Available |

This report corrects the measurement semantics of the repeated-run study. Previous reports used `total_wall_ms` without explicitly defining its boundaries. This report defines those boundaries precisely and separates model-load observations from request-loop timing.

Historical reports are preserved unchanged:
- `docs/first-three-mode-benchmark-report.md`
- `docs/post-routing-fix-three-mode-benchmark-report.md`
- `docs/post-retrieval-hardening-three-mode-benchmark-report.md`
- `docs/repeated-run-three-mode-benchmark-report.md`

---

## 2. Timing Definitions

### `total_wall_ms` / request-loop wall time

Sum of per-request `perf_counter` latency across the 30-case loop only.

**Included in each per-request measurement:**
- `runtime.execute()` or `runtime.execute_forced()` call
- `RequestAnalyzer` routing
- `DocumentRetriever` FTS5 query and deterministic reranking (retrieval cases)
- `SmallModel` inference or fallback response (retrieval/generation cases)
- `ResponseRenderer`
- `Verifier` (invoice extraction cases)
- Per-request cache clearing

**Excluded from `total_wall_ms`:**
- Parent runner process startup
- Child Python interpreter startup
- Module imports
- Database initialization/open
- Benchmark-case JSONL loading
- Runtime construction
- Model loading / warmup request
- JSON file writing
- Report printing and scoring output

### Model-load / warmup timing

Measured separately as the wall time from `Runtime()` construction through the first `execute()` call that triggers model loading. This is a one-time cost per subprocess and is not part of `total_wall_ms`.

### Labeling

This study is labeled a **fresh-process request-loop benchmark with separate model-load observations**. It is not a cold end-to-end latency measurement.

---

## 3. Corrected Model Classifications

| | Mode A (Fallback) | Mode B (Modular 3B) | Mode C (Forced 3B) |
|---|:---:|:---:|:---:|
| Real model calls per run | 0 | 15 | 30 |
| Fallback responses per run | 15 | 0 | 0 |
| Model-load failures per run | 0 | 0 | 0 |
| Cases per run | 30 | 30 | 30 |

All `small_model` traces across all 15 artifacts use nested `trace.metadata["model_metrics"]`. All 22 required metric fields are present in every trace. No legacy top-level metadata was found in any artifact.

---

## 4. Main Results

### Request-Loop Timing (per run, 30 cases)

| Metric | Mode A | Mode B | Mode C |
|--------|--------|--------|--------|
| Mean | 10,450 ms | 97,457 ms | 135,863 ms |
| Stdev | 2,298 ms | 22,192 ms | 18,951 ms |
| Min | 8,215 ms | 81,002 ms | 117,850 ms |
| Max | 13,784 ms | 134,647 ms | 161,725 ms |
| Median (p50) | ~10,371 ms | ~87,379 ms | ~128,153 ms |
| p95 (exploratory) | ~13,784 ms | ~134,647 ms | ~161,725 ms |

### Model-Load Observations (one-time per subprocess)

| | Mode B | Mode C |
|---|:---:|:---:|
| Model load time | ~12,082 ms | ~5,274 ms |

Model-load time varies between subprocesses due to OS scheduling and disk cache state. It is reported separately and not included in request-loop totals.

### Comparative

- Mode B is approximately **28.3% faster** than Mode C based on mean request-loop total: `(135,863 − 97,457) / 135,863 = 0.283`.
- Mode B reduces real model calls by **50%** relative to Mode C (15 vs 30 per run).
- Mode A performs no real model calls; its latency is fallback-path request-loop work.

### Score Interpretation

- 15 strongly scored cases (8 calculation + 7 extraction) pass identically in all three modes.
- The remaining 15 cases (8 retrieval + 7 generation) are scored N/A under the current scorer, which uses non-empty-output gating for generation and substring matching for retrieval.
- Do not claim 30/30 quality success from this data. Quality conclusions require human evaluation or a stronger scorer.

---

## 5. Mode A Explanation

Mode A's 8–14 second request-loop total is **actual fallback-path work**, not startup overhead.

### Diagnostic Category Means

| Category | Cases | Avg per case |
|----------|:-----:|:-----------:|
| Calculation | 8 | 0.3 ms |
| Extraction | 7 | 0.1 ms |
| **Retrieval** | **8** | **623.8 ms** |
| **Generation** | **7** | **462.2 ms** |

The fallback path currently:
1. Constructs a messages array for the SmallModel
2. For retrieval cases: executes `DocumentRetriever` FTS5 query and reranking before returning the fallback response
3. Returns a demo string without invoking the LLM

The retrieval and generation fallback cases dominate Mode A latency. Optimization of this fallback/retrieval path is a future question, not a conclusion from this report.

---

## 6. Limitations

- **Sample size:** Five samples per mode. Mean/min/max and median are descriptive statistics. The displayed p95 effectively tracks the highest observed run and is not sufficient evidence for production tail SLO claims.
- **No TTFT or prefill/decode split:** llama-cpp-python 0.3.35 does not expose time-to-first-token, prompt-processing time, or generation time separately. All timing is total wall time per request.
- **Windows RSS:** Uses current `WorkingSet64` via PowerShell `Get-Process`. Peak RSS is not available through this method. Direct `GetProcessMemoryInfo` fails in subprocess contexts.
- **Sequential execution:** All requests are processed sequentially. No concurrency, batching, or parallel inference.
- **Fixed suite:** 30 cases on a single machine with a 3B Q4_K_M configuration. Results may not generalize to other models, quantizations, or hardware.
- **Category labels:** Some raw result entries have `category: null`. This is a pre-existing artifact-labeling issue in the benchmark cases JSONL, not caused by this study.
- **Shell environment:** Original commands ran under Git Bash/MSYS on Windows. See Appendix for portable equivalents.

---

## 7. Historical Preservation

This is a corrected measurement-semantics report following metadata reader/writer integration repair (commits `b4f3f9c` and `f06a0c1`). It does not replace or overwrite any previous report. The previous repeated-run report (`docs/repeated-run-three-mode-benchmark-report.md`) used the same raw data but without explicit timing-boundary definitions and nested model_metrics verification.

---

## Appendix: Reproducibility

### Execution Commit

```
f06a0c1acc63e7e086783307f2906cb486608a51
```

### Benchmark Corpus

- Path: `data/benchmark_cases.jsonl`
- Cases: 30 (8 calculation, 8 retrieval, 7 extraction, 7 generation)

### Model

| Field | Value |
|-------|-------|
| Filename | `qwen2.5-3b-instruct-q4_k_m.gguf` |
| Size | 2,007 MB |
| Quantization | Q4_K_M |
| Source | HuggingFace Qwen |

### System

| Field | Value |
|-------|-------|
| CPU | Intel i7-11700T (8C/16T) |
| RAM | 15.45 GB |
| OS | Windows 10 (10.0.26200) |
| Python | 3.11.15 |
| llama-cpp-python | 0.3.35 |
| SQLite | 3.53.1 |

### Fresh-Process Condition

Each benchmark repetition runs in a separate Python subprocess. No in-process model reuse between runs. The model is loaded fresh in each subprocess via the warmup request.

### Commands

**Git Bash / Linux / macOS:**

```bash
# Mode A: Fallback (no model)
env -u CPU_INFERENCE_MODEL_PATH python3 scripts/benchmark_all_modes.py --mode fallback

# Mode B: Modular (3B model)
CPU_INFERENCE_MODEL_PATH=models/qwen2.5-3b-instruct-q4_k_m.gguf python3 scripts/benchmark_all_modes.py --mode modular

# Mode C: Forced (3B model)
CPU_INFERENCE_MODEL_PATH=models/qwen2.5-3b-instruct-q4_k_m.gguf python3 scripts/benchmark_all_modes.py --mode forced
```

**Windows PowerShell:**

```powershell
# Mode A: Fallback (no model)
Remove-Item Env:CPU_INFERENCE_MODEL_PATH -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe scripts\benchmark_all_modes.py --mode fallback

# Mode B: Modular (3B model)
$env:CPU_INFERENCE_MODEL_PATH = "models\qwen2.5-3b-instruct-q4_k_m.gguf"
.\.venv\Scripts\python.exe scripts\benchmark_all_modes.py --mode modular

# Mode C: Forced (3B model)
$env:CPU_INFERENCE_MODEL_PATH = "models\qwen2.5-3b-instruct-q4_k_m.gguf"
.\.venv\Scripts\python.exe scripts\benchmark_all_modes.py --mode forced
```

**Windows cmd.exe:**

```cmd
:: Mode A: Fallback (no model)
set CPU_INFERENCE_MODEL_PATH=
.venv\Scripts\python.exe scripts\benchmark_all_modes.py --mode fallback

:: Mode B: Modular (3B model)
set CPU_INFERENCE_MODEL_PATH=models\qwen2.5-3b-instruct-q4_k_m.gguf
.venv\Scripts\python.exe scripts\benchmark_all_modes.py --mode modular

:: Mode C: Forced (3B model)
set CPU_INFERENCE_MODEL_PATH=models\qwen2.5-3b-instruct-q4_k_m.gguf
.venv\Scripts\python.exe scripts\benchmark_all_modes.py --mode forced
```
