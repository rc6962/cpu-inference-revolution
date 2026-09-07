# Corrected Repeated 1.5B-vs-3B Model Comparison Study

**Date:** 2026-09-07
**Code revision:** `01c7d92d5b57ccaf9a0d92144321eecee95dab38`
**Status:** Corrected study following metadata reader/writer integration repair and forced-mode identity fix

---

## 1. Study Design

- **Runs:** 20 total: 4 conditions × 5 fresh-process repetitions
- **Conditions:**
  1. Modular / Qwen2.5 1.5B Q4_K_M
  2. Modular / Qwen2.5 3B Q4_K_M
  3. Forced / Qwen2.5 1.5B Q4_K_M
  4. Forced / Qwen2.5 3B Q4_K_M
- **Balanced run order:** specified to reduce thermal and time-order bias
- **Per-run scope:** 30 fixed cases, request-loop wall time only
- **Fresh-process isolation:** each run is a separate Python subprocess; no in-process model reuse
- **Timing boundary:** `total_wall_ms` = sum of per-request `perf_counter` latency across the 30-case loop only; excludes interpreter startup, imports, DB init, runtime construction, model load/warmup, JSON writing, and report/scoring work

## 2. Environment

| Field | Value |
|-------|-------|
| OS | Windows 10 build 10.0.26200 |
| CPU | Intel i7-11700T (8C/16T) |
| RAM | 15.45 GB |
| Python | 3.11.15 |
| llama-cpp-python | 0.3.35 |
| SQLite | 3.53.1 |
| Shell | Git Bash / MSYS |
| n_ctx | 512 |
| n_threads | 8 |
| max_tokens | 256 |
| temperature | 0.0 |

## 3. Models

| Model | Filename | Size (bytes) | SHA-256 | Quantization |
|-------|----------|-------------:|---------|:------------:|
| 1.5B | `qwen2.5-1.5b-instruct-q4_k_m.gguf` | 1,117,320,736 | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` | Q4_K_M |
| 3B | `qwen2.5-3b-instruct-q4_k_m.gguf` | 2,104,932,768 | `626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d` | Q4_K_M |

## 4. Benchmark Corpus

- File: `data/benchmark_cases.jsonl`
- SHA-256: `1865772f1929068681ca2300d6fdd34c1379b75c9e47190e633d37d21836a626`
- 30 cases: 8 calculation, 8 retrieval, 7 extraction, 7 generation
- DB reinitialized from `data/seed.jsonl` before each model study (via benchmark runner)

## 5. Execution Ledger

| Ord | Timestamp | Condition | Rep | RAM (MB) | Wall (ms) | Status |
|:---:|-----------|-----------|:---:|---------:|----------:|:------:|
| 01 | 2026-09-07 11:43:15 | modular_1p5b | 01 | 2,652 | 50,241 | OK |
| 02 | 2026-09-07 11:44:12 | forced_3b | 01 | 2,999 | 144,967 | OK |
| 03 | 2026-09-07 11:46:47 | modular_3b | 01 | 3,550 | 84,266 | OK |
| 04 | 2026-09-07 11:48:23 | forced_1p5b | 01 | 3,925 | 73,321 | OK |
| 05 | 2026-09-07 11:49:40 | forced_1p5b | 02 | 3,378 | 78,768 | OK |
| 06 | 2026-09-07 11:51:04 | modular_3b | 02 | 3,138 | 86,467 | OK |
| 07 | 2026-09-07 11:52:41 | forced_3b | 02 | 3,601 | 125,541 | OK |
| 08 | 2026-09-07 11:54:53 | modular_1p5b | 02 | 4,039 | 40,415 | OK |
| 09 | 2026-09-07 11:55:39 | modular_3b | 03 | 3,819 | 94,670 | OK |
| 10 | 2026-09-07 11:57:27 | forced_1p5b | 03 | 4,697 | 72,091 | OK |
| 11 | 2026-09-07 11:58:44 | modular_1p5b | 03 | 3,899 | 39,094 | OK |
| 12 | 2026-09-07 11:59:28 | forced_3b | 03 | 3,346 | 146,241 | OK |
| 13 | 2026-09-07 12:02:03 | forced_3b | 04 | 4,601 | 139,026 | OK |
| 14 | 2026-09-07 12:04:28 | modular_1p5b | 04 | 4,952 | 46,360 | OK |
| 15 | 2026-09-07 12:05:20 | forced_1p5b | 04 | 3,817 | 71,597 | OK |
| 16 | 2026-09-07 12:06:37 | modular_3b | 04 | 3,938 | 83,041 | OK |
| 17 | 2026-09-07 12:08:13 | forced_1p5b | 05 | 4,804 | 61,565 | OK |
| 18 | 2026-09-07 12:09:18 | modular_3b | 05 | 5,031 | 70,803 | OK |
| 19 | 2026-09-07 12:10:38 | forced_3b | 05 | 5,041 | 114,739 | OK |
| 20 | 2026-09-07 12:12:38 | modular_1p5b | 05 | 5,047 | 32,256 | OK |

## 6. Acceptance Evidence

Re-validated directly from raw JSON artifacts (not relying on console summary alone):

| Criterion | Modular 1.5B | Modular 3B | Forced 1.5B | Forced 3B |
|-----------|:------------:|:----------:|:-----------:|:---------:|
| Real successful calls | 75/75 | 75/75 | 150/150 | 150/150 |
| Fallback calls | 0 | 0 | 0 | 0 |
| Load failures | 0 | 0 | 0 | 0 |
| model_name correct | ✅ | ✅ | ✅ | ✅ |
| model_path_basename correct | ✅ | ✅ | ✅ | ✅ |
| Nested model_metrics | 75/75 | 75/75 | 150/150 | 150/150 |
| All 22 schema fields | 75/75 | 75/75 | 150/150 | 150/150 |
| Stop reason = stop | 75/75 | 75/75 | 150/150 | 150/150 |

Total small_model traces across all 20 runs: 450 (75+75+150+150). All contain nested `trace.metadata["model_metrics"]` with complete 22-field schema.

## 7. Four-Condition Aggregate Table

| Condition | n | Real Calls | Fallbacks | Load Failures | Score Pass | Score N/A |
|-----------|:-:|:----------:|:---------:|:-------------:|:----------:|:---------:|
| Modular 1.5B | 5 | 75 | 0 | 0 | 75 | 75 |
| Modular 3B | 5 | 75 | 0 | 0 | 75 | 75 |
| Forced 1.5B | 5 | 150 | 0 | 0 | 150 | 150 |
| Forced 3B | 5 | 150 | 0 | 0 | 150 | 150 |

*Score pass = deterministic/extraction cases; N/A = retrieval/generation cases under current scorer.*

| Condition | Wall Mean | Wall Median | Wall Min | Wall Max | Per-Call Model ms (mean) | Input tokens min/mean/max | Output tokens min/mean/max |
|-----------|----------:|-----------:|---------:|---------:|-------------------------:|:-------------------------:|:--------------------------:|
| Modular 1.5B | 41,673 | 40,415 | 32,256 | 50,241 | 2,159 | 38/68.3/104 | 4/19.6/52 |
| Modular 3B | 83,850 | 84,266 | 70,803 | 94,670 | 5,039 | 38/68.3/104 | 5/27.3/82 |
| Forced 1.5B | 71,468 | 72,091 | 61,565 | 78,768 | 1,780 | 31/49.4/73 | 2/18.5/137 |
| Forced 3B | 134,103 | 139,026 | 114,739 | 146,241 | 3,871 | 31/49.4/73 | 2/22.5/119 |

| Condition | Stop reasons | RSS before (MB) | RSS after (MB) | RSS method |
|-----------|:-------------|:---------------:|:--------------:|:----------:|
| Modular 1.5B | stop:75 | 1,650–1,676 | 1,659–1,676 | Windows/PowerShell/WorkingSet64 |
| Modular 3B | stop:75 | 3,222–3,254 | 3,235–3,254 | Windows/PowerShell/WorkingSet64 |
| Forced 1.5B | stop:150 | 1,650–1,698 | 1,653–1,698 | Windows/PowerShell/WorkingSet64 |
| Forced 3B | stop:150 | 3,226–3,275 | 3,229–3,275 | Windows/PowerShell/WorkingSet64 |

## 8. Observed Speed Ratios

Recomputed from raw condition means:

| Comparison | Mean A (ms) | Mean B (ms) | Ratio B/A | Rounded |
|------------|------------:|------------:|:---------:|:-------:|
| Modular 1.5B vs 3B | 41,673 | 83,850 | 2.012 | **2.01×** |
| Forced 1.5B vs 3B | 71,468 | 134,103 | 1.876 | **1.88×** |
| Modular vs Forced at 1.5B | 41,673 | 71,468 | 1.715 | **1.72×** |
| Modular vs Forced at 3B | 83,850 | 134,103 | 1.599 | **1.60×** |

Interpretation (descriptive, not causal):
- 1.5B is approximately 2× faster than 3B in both modular and forced modes.
- Modular routing is approximately 1.6–1.7× faster than forced routing because it skips the model for deterministic cases.

## 9. Quality Note

All conditions produce identical outputs for the15 deterministic/extraction cases (scored as pass under the current scorer). The remaining15 retrieval/generation cases are scored as N/A under the current scorer. This study does **not** claim semantic equivalence or equal answer quality between 1.5B and 3B — the current scorer cannot evaluate retrieval answer correctness or generation quality beyond non-emptiness.

## 10. Variability

No data were excluded, retried, or hidden. The observed wall-time ranges within each condition are:

| Condition | Min (ms) | Max (ms) | Spread |
|-----------|----------:|----------:|-------:|
| Modular 1.5B | 32,256 | 50,241 | 17,985 |
| Modular 3B | 70,803 | 94,670 | 23,867 |
| Forced 1.5B | 61,565 | 78,768 | 17,203 |
| Forced 3B | 114,739 | 146,241 | 31,502 |

The forced 3B condition shows the widest spread (31.5s). All five runs within each condition were accepted; no outliers were excluded.

⚠️ **Five-run p95 and max figures are descriptive only and are not valid production tail-latency, capacity, or SLO evidence.** Five samples is insufficient for tail-latency estimation.

## 11. What This Study Is Not

- **Not a cold-start deployment metric.** Model load time is excluded from wall time.
- **Not a concurrent-serving throughput test.** All runs are sequential, single-request.
- **Not a production SLO baseline.** Five samples, one machine, one quantization per size.
- **Not a semantic quality evaluation.** The current scorer cannot assess retrieval answer correctness or generation quality.

## 12. Limitations

1. **One machine:** Intel i7-11700T, 15.45 GB RAM, Windows 10. Results are specific to this hardware.
2. **One quantization per size:** Q4_K_M only. Other quantizations may show different speed/quality tradeoffs.
3. **Five samples per condition:** Descriptive statistics only; insufficient for SLO or capacity claims.
4. **Fixed benchmark:** 30 cases from a static corpus. Does not represent production workload distribution.
5. **No concurrency test:** Sequential execution only. Concurrent serving may show different characteristics.
6. **No energy measurement:** Power consumption not measured.
7. **No formal semantic-quality evaluator:** Retrieval and generation quality beyond non-emptiness is not assessed.
8. **RSS limitation:** Windows peak RSS is unavailable; only current WorkingSet64 snapshots are recorded.

## 13. Artifacts and Reproduction

**Artifacts:**
```
results/model-comparison-repeated/01c7d92/
  modular_1p5b_run_01.json .. modular_1p5b_run_05.json
  modular_3b_run_01.json   .. modular_3b_run_05.json
  forced_1p5b_run_01.json  .. forced_1p5b_run_05.json
  forced_3b_run_01.json    .. forced_3b_run_05.json
  execution_ledger.json
  manifest.json
```

**Manifest:** `results/model-comparison-repeated/01c7d92/manifest.json`

**To reproduce:**
```bash
# Modular 1.5B (Git Bash)
CPU_INFERENCE_MODEL_PATH=models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  .venv/Scripts/python scripts/benchmark_all_modes.py --mode modular

# Modular 3B
CPU_INFERENCE_MODEL_PATH=models/qwen2.5-3b-instruct-q4_k_m.gguf \
  .venv/Scripts/python scripts/benchmark_all_modes.py --mode modular

# Forced 1.5B
CPU_INFERENCE_MODEL_PATH=models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  .venv/Scripts/python scripts/benchmark_all_modes.py --mode forced

# Forced 3B
CPU_INFERENCE_MODEL_PATH=models/qwen2.5-3b-instruct-q4_k_m.gguf \
  .venv/Scripts/python scripts/benchmark_all_modes.py --mode forced
```

**PowerShell equivalents:**
```powershell
$env:CPU_INFERENCE_MODEL_PATH = "models\qwen2.5-1.5b-instruct-q4_k_m.gguf"
.\.venv\Scripts\python.exe scripts\benchmark_all_modes.py --mode modular
```

**cmd.exe equivalents:**
```cmd
set CPU_INFERENCE_MODEL_PATH=models\qwen2.5-1.5b-instruct-q4_k_m.gguf
.venv\Scripts\python.exe scripts\benchmark_all_modes.py --mode modular
```
