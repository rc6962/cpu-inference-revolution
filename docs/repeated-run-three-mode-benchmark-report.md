# Repeated-Run Three-Mode Benchmark Report

**Date:** 2026-09-01
**Status:** Exploratory single-machine variance study — not a production benchmark

---

## Benchmark execution

| Field | Value |
|-------|-------|
| Execution commit SHA | `9a8c5d7` |
| OS | Windows 11 Pro (10.0.26200) |
| CPU | Intel i7-11700T (8C/16T @ 1.40GHz) |
| RAM | 15.45 GB total |
| Python | 3.11.15 |
| SQLite | 3.53.1 with FTS5 |
| llama-cpp-python | 0.3.35 |
| Model | Qwen2.5-3B-Instruct Q4_K_M (2.0 GB GGUF) |
| Settings | n_ctx=512, n_threads=8, max_tokens=256, temperature=0.0 |
| Seed documents | 13 |
| Benchmark cases | 30 |
| Measured runs per mode | 5 |
| Total measured requests per mode | 150 |
| Warmup | 1 complete pass per mode, discarded |

---

## Raw result artifacts

All raw results stored in `results/repeated-runs/9a8c5d7/`:

| Filename | Mode | Run |
|----------|------|-----|
| `mode_a_run_01.json` through `mode_a_run_05.json` | Fallback | 1–5 |
| `mode_b_run_01.json` through `mode_b_run_05.json` | Modular | 1–5 |
| `mode_c_run_01.json` through `mode_c_run_05.json` | Forced | 1–5 |

---

## Mode A: Fallback — 5-Run Table

| Run | Wall (ms) | Score |
|-----|-----------|:-----:|
| 1 | 12 | 30/30 |
| 2 | 12 | 30/30 |
| 3 | 10 | 30/30 |
| 4 | 12 | 30/30 |
| 5 | 10 | 30/30 |

**Run wall time:** min=10, max=12, mean=11, stdev=1, CV=9.0%

---

## Mode B: Modular — 5-Run Table

| Run | Wall (ms) | Score |
|-----|-----------|:-----:|
| 1 | 75,264 | 30/30 |
| 2 | 82,794 | 30/30 |
| 3 | 74,367 | 30/30 |
| 4 | 71,746 | 30/30 |
| 5 | 66,251 | 30/30 |

**Run wall time:** min=66,251, max=82,794, mean=74,084, stdev=6,003, CV=8.1%

---

## Mode C: Forced — 5-Run Table

| Run | Wall (ms) | Score |
|-----|-----------|:-----:|
| 1 | 104,104 | 16/30 |
| 2 | 116,977 | 16/30 |
| 3 | 118,574 | 16/30 |
| 4 | 118,193 | 16/30 |
| 5 | 116,420 | 16/30 |

**Run wall time:** min=104,104, max=118,574, mean=114,854, stdev=6,073, CV=5.3%

---

## Pooled per-request latency (150 samples per mode)

| Metric | Mode A | Mode B | Mode C |
|--------|--------|--------|--------|
| Mean | 0.4 ms | 2,469.5 ms | 3,828.4 ms |
| Stdev | 0.8 ms | 3,837.4 ms | 3,487.8 ms |
| p50 | 0.0 ms | 955.8 ms | 3,325.8 ms |
| p95 | 1.0 ms | 10,471.6 ms | 11,552.2 ms |
| p99 | 4.3 ms | 13,942.6 ms | 17,197.9 ms |
| min | 0.0 ms | 0.1 ms | 625.7 ms |
| max | 5.5 ms | 16,528.1 ms | 17,838.6 ms |

**Note:** p99 from 150 samples is exploratory. p50 and p95 are more reliable.

---

## Latency by task category (pooled)

| Category | Mode A mean | Mode B mean | Mode C mean |
|----------|-------------|-------------|-------------|
| calculation | 0.1 ms | 0.2 ms | 1,763.0 ms |
| extraction | 0.1 ms | 0.2 ms | 3,885.7 ms |
| retrieval | 1.2 ms | 8,058.3 ms | 7,956.7 ms |
| generation | 0.0 ms | 1,373.5 ms | 1,413.8 ms |

---

## Quality consistency across runs

| Mode | Runs scoring 30/30 | Route accuracy | Source retrieval |
|------|:------------------:|:--------------:|:---------------:|
| A (Fallback) | **5/5** | 150/150 | 40/40 |
| B (Modular) | **5/5** | 150/150 | 40/40 |
| C (Forced) | **0/5** (all 16/30) | 0/150 | 0/40 |

**Quality is perfectly deterministic across all 5 runs for all modes.** The scoring results are identical run-to-run.

---

## Costs

| Metric | Mode A | Mode B | Mode C |
|--------|--------|--------|--------|
| Total wall (5 runs) | 57 ms | 370,422 ms | 574,268 ms |
| Total model-step (5 runs) | 0 ms | 370,280 ms | 574,248 ms |
| Correct tasks | 150/150 | 150/150 | 80/150 |
| **Correct-task cost** | **0.4 ms/task** | **2,469.5 ms/task** | **7,178.3 ms/task** |
| Real LLM calls | 0 | 75 | 150 |
| **Real-model-call cost** | — | **4,937.1 ms/call** | **3,828.3 ms/call** |

---

## Variance analysis

### Run-to-run variance

| Mode | CV (wall time) | Assessment |
|------|:--------------:|------------|
| A (Fallback) | 9.0% | Low — sub-millisecond absolute variance |
| B (Modular) | 8.1% | Moderate — ~6s spread across 74s mean |
| C (Forced) | 5.3% | Low — ~6s spread across 115s mean |

### Is the variance stable?

Mode B shows the highest absolute variance (6s stdev on 74s mean) but low CV (8.1%). The run range (66–83s) overlaps materially between runs, suggesting the variance is within normal CPU scheduling and model inference noise. No run is an outlier.

Mode C shows lower CV (5.3%) despite higher absolute times, indicating more consistent behavior when all cases go through the model.

### Quality variance

**Zero variance.** All 5 runs for Modes A and B score exactly 30/30. All 5 runs for Mode C score exactly 16/30. The scoring is fully deterministic.

---

## Correct-task cost and real-model-call cost

**Correct-task cost** = total wall milliseconds / verified successful tasks

- Mode A: 0.4 ms per correct task (no model, deterministic modules only)
- Mode B: 2,469.5 ms per correct task (model invoked for 15/30 cases)
- Mode C: 7,178.3 ms per correct task (model invoked for all 30 cases, but only 80/150 correct)

**Real-model-call cost** = total model-step time / real LLM inferences

- Mode B: 4,937.1 ms per model call (15 calls per run × 5 runs = 75 calls)
- Mode C: 3,828.3 ms per model call (30 calls per run × 5 runs = 150 calls)

Mode C has lower per-call cost because its task-aware system prompts produce shorter outputs on average. Mode B's retrieval calls include evidence context that increases prompt length.

---

## Product comparison vs controlled comparison

### Product comparison (modular vs forced)

Mode B (modular) achieves 100% correctness at 2,469 ms/task average. Mode C (forced) achieves 53% correctness at 7,178 ms/task average. The modular runtime is both more correct and faster per correct task because it avoids model calls on deterministic tasks.

### Controlled comparison (same model, same settings)

Both modes use the same Qwen2.5-3B Q4_K_M model with identical settings (n_ctx=512, n_threads=8, max_tokens=256, temperature=0.0). The difference is serving path only: Mode B routes through the execution graph, Mode C forces all cases through SmallModel. The per-call cost difference (4,937 ms vs 3,828 ms) reflects prompt composition differences, not model configuration.

---

## Known limits

- **Fixed 30-case suite:** Results apply only to this specific workload, not general tasks.
- **Single machine:** i7-11700T @ 1.40GHz. Different hardware will produce different absolute times.
- **Sequential requests:** No concurrency testing. Real deployments may show different contention patterns.
- **150 measured samples per mode:** p99 is exploratory. p50/p95 are more reliable.
- **Scoring limitations:** Calculation (STRONG), retrieval (MODERATE), extraction (STRONG), generation (WEAK). Mixed-strength aggregate scores are not universal AI-quality metrics.
- **No prompt-processing/decode separation:** Cannot draw causal conclusions about model latency breakdown.
