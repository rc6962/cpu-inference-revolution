# First Three-Mode Benchmark Report

**Date:** 2026-08-31
**Status:** Exploratory single-machine baseline — not a production benchmark

---

## Test environment

| Field | Value |
|-------|-------|
| Repository commit | `7cab084` |
| OS | Microsoft Windows 11 Pro (10.0.26200) |
| Architecture | 64-bit |
| CPU | 11th Gen Intel Core i7-11700T @ 1.40GHz |
| Physical cores | 8 |
| Logical processors | 16 |
| Total RAM | 15.45 GB |
| Python version | 3.11.15 |
| SQLite version | 3.x (FTS5 available and verified) |
| Model filename | `qwen2.5-3b-instruct-q4_k_m.gguf` |
| Model quantization | Q4_K_M (4-bit, ~2.0 GB) |

| Mode | Database | Model |
|------|:--------:|:-----:|
| A (Fallback) | Present | Not loaded |
| B (Modular) | Present | Loaded |
| C (Forced) | Present | Loaded |

| Field | Value |
|-------|-------|
| Dataset file | `data/benchmark_cases.jsonl` |
| Total cases | 30 |
| Categories | calculation (8), retrieval (8), extraction (7), generation (7) |

**This is a single-machine exploratory benchmark.** Results reflect one hardware configuration under controlled conditions. They do not generalize to other CPUs, RAM configurations, model quantizations, or workloads.

---

## Per-request results

| Request ID | Task type | Expected route | Mode A route | Mode B route | Mode C route | B model called? | C model called? | B correct? | C correct? | Strength | B wall ms | C wall ms | B escalated? | Notes |
|------------|-----------|---------------|-------------|-------------|-------------|:---------------:|:---------------:|:----------:|:----------:|:--------:|----------:|----------:|:------------:|-------|
| calc-001 | calculation | deterministic_calculation | deterministic_calculation | deterministic_calculation | forced_single_model | ❌ | ✅ | ✅ | ❌ | STRONG | 1 | 8,270 | ❌ | |
| calc-002 | calculation | deterministic_calculation | deterministic_calculation | deterministic_calculation | forced_single_model | ❌ | ✅ | ✅ | ❌ | STRONG | 0 | 957 | ❌ | |
| calc-003 | calculation | deterministic_calculation | deterministic_calculation | deterministic_calculation | forced_single_model | ❌ | ✅ | ✅ | ❌ | STRONG | 0 | 681 | ❌ | |
| calc-004 | calculation | deterministic_calculation | deterministic_calculation | deterministic_calculation | forced_single_model | ❌ | ✅ | ✅ | ❌ | STRONG | 0 | 558 | ❌ | |
| calc-005 | calculation | deterministic_calculation | deterministic_calculation | deterministic_calculation | forced_single_model | ❌ | ✅ | ✅ | ✅ | STRONG | 0 | 693 | ❌ | |
| calc-006 | calculation | deterministic_calculation | deterministic_calculation | deterministic_calculation | forced_single_model | ❌ | ✅ | ✅ | ❌ | STRONG | 0 | 1,036 | ❌ | |
| calc-007 | calculation | deterministic_calculation | deterministic_calculation | deterministic_calculation | forced_single_model | ❌ | ✅ | ✅ | ❌ | STRONG | 0 | 842 | ❌ | |
| calc-008 | calculation | deterministic_calculation | deterministic_calculation | deterministic_calculation | forced_single_model | ❌ | ✅ | ✅ | ✅ | STRONG | 0 | 928 | ❌ | |
| ret-001 | retrieval | small_rag | small_rag | small_rag | forced_single_model | ✅ | ✅ | ✅ | ❌ | MODERATE | 11,404 | 6,097 | ❌ | source and key fact present |
| ret-002 | retrieval | small_rag | small_rag | small_rag | forced_single_model | ✅ | ✅ | ❌ | ❌ | MODERATE | 4,608 | 4,300 | ❌ | source_id not in output |
| ret-003 | retrieval | small_rag | small_direct | small_direct | forced_single_model | ✅ | ✅ | ❌ | ❌ | MODERATE | 20,414 | 5,007 | ❌ | misrouted to small_direct |
| ret-004 | retrieval | small_rag | small_rag | small_rag | forced_single_model | ✅ | ✅ | ✅ | ❌ | MODERATE | 4,168 | 4,089 | ❌ | source and key fact present |
| ret-005 | retrieval | small_rag | small_direct | small_direct | forced_single_model | ✅ | ✅ | ❌ | ❌ | MODERATE | 30,856 | 13,060 | ❌ | source_id not in output |
| ret-006 | retrieval | small_rag | small_direct | small_direct | forced_single_model | ✅ | ✅ | ❌ | ❌ | MODERATE | 31,046 | 8,954 | ❌ | source_id not in output |
| ret-007 | retrieval | small_rag | small_direct | small_direct | forced_single_model | ✅ | ✅ | ❌ | ❌ | MODERATE | 28,406 | 5,168 | ❌ | source_id not in output |
| ret-008 | retrieval | small_rag | small_direct | small_direct | forced_single_model | ✅ | ✅ | ❌ | ❌ | MODERATE | 30,793 | 4,930 | ❌ | source_id not in output |
| ext-001 | extraction | invoice_extraction | invoice_extraction | invoice_extraction | forced_single_model | ❌ | ✅ | ✅ | ✅ | STRONG | 1 | 3,428 | ❌ | |
| ext-002 | extraction | invoice_extraction | invoice_extraction | invoice_extraction | forced_single_model | ❌ | ✅ | ✅ | ✅ | STRONG | 0 | 3,038 | ❌ | |
| ext-003 | extraction | invoice_extraction | invoice_extraction | invoice_extraction | forced_single_model | ❌ | ✅ | ✅ | ✅ | STRONG | 0 | 2,603 | ❌ | |
| ext-004 | extraction | invoice_extraction | invoice_extraction | invoice_extraction | forced_single_model | ❌ | ✅ | ✅ | ✅ | STRONG | 0 | 3,299 | ❌ | |
| ext-005 | extraction | invoice_extraction | invoice_extraction | invoice_extraction | forced_single_model | ❌ | ✅ | ✅ | ✅ | STRONG | 0 | 3,061 | ❌ | |
| ext-006 | extraction | invoice_extraction | invoice_extraction | invoice_extraction | forced_single_model | ❌ | ✅ | ✅ | ✅ | STRONG | 0 | 2,887 | ❌ | |
| ext-007 | extraction | invoice_extraction | invoice_extraction | invoice_extraction | forced_single_model | ❌ | ✅ | ✅ | ✅ | STRONG | 0 | 2,772 | ❌ | |
| gen-001 | generation | small_direct | small_direct | small_direct | forced_single_model | ✅ | ✅ | ✅ | ✅ | WEAK | 963 | 1,334 | ❌ | |
| gen-002 | generation | small_direct | small_direct | small_direct | forced_single_model | ✅ | ✅ | ✅ | ✅ | WEAK | 1,187 | 1,078 | ❌ | |
| gen-003 | generation | small_direct | small_direct | small_direct | forced_single_model | ✅ | ✅ | ✅ | ✅ | WEAK | 1,345 | 946 | ❌ | |
| gen-004 | generation | small_direct | small_direct | small_direct | forced_single_model | ✅ | ✅ | ✅ | ✅ | WEAK | 1,183 | 982 | ❌ | |
| gen-005 | generation | small_direct | small_direct | small_direct | forced_single_model | ✅ | ✅ | ✅ | ✅ | WEAK | 1,791 | 1,216 | ❌ | |
| gen-006 | generation | small_direct | small_direct | small_direct | forced_single_model | ✅ | ✅ | ✅ | ✅ | WEAK | 966 | 1,415 | ❌ | |
| gen-007 | generation | small_direct | small_direct | small_direct | forced_single_model | ✅ | ✅ | ✅ | ✅ | WEAK | 1,204 | 1,237 | ❌ | |

**False-cheap routes:** None. Every case that was not routed to a real model in Mode B either passed with a strongly-scored deterministic module (calculation, extraction) or was a retrieval/generation case where the model was called.

**False-expensive routes (13):** Cases where Mode B invoked the model but scored identically to Mode C, providing no measurable score advantage:
- `ret-002, ret-003, ret-005, ret-006, ret-007, ret-008` — retrieval cases where both modes failed scoring
- `gen-001, gen-002, gen-003, gen-004, gen-005, gen-006, gen-007` — generation cases where both modes passed the weak gate, so no quality differentiation is possible

---

## Aggregate metrics

| Metric | Mode A | Mode B | Mode C |
|--------|:------:|:------:|:------:|
| Total requests | 30 | 30 | 30 |
| Correct requests | 23 | 24 | 16 |
| Correct — STRONG scoring | 15 | 15 | 9 |
| Correct — MODERATE scoring | 1 | 2 | 0 |
| Correct — WEAK scoring | 7 | 7 | 7 |
| Completed without model inference | 30 | 15 | 0 |
| Completed with real model inference | 0 | 15 | 30 |
| Model-call count | 0 | 15 | 30 |
| Model-call rate | 0% | 50% | 100% |
| Total wall time | 7 ms | 170,339 ms | 94,867 ms |
| Avg latency/case | 0.2 ms | 5,678 ms | 3,162 ms |
| Median latency/case | 0.0 ms | 482 ms | 2,688 ms |
| P95 latency/case | 0.6 ms | 30,857 ms | 8,954 ms |
| Total model-step time | 0 ms | 170,321 ms | 94,864 ms |
| Total FTS5 retrieval-step time | 6 ms | 12 ms | 0 ms |
| Verification failures | 0 | 0 | 0 |

**False-cheap count:** 0
**False-expensive count:** 13 (6 retrieval + 7 generation)

---

## Core research question

**"How many strongly scored useful requests can the modular system complete without invoking the 3B model?"**

### 1. Strict count (strongly scored cases that passed without real model inference)

- **Count:** 15
- **Denominator:** 15 strongly-scored cases in the dataset (8 calculation + 7 extraction)
- **Percentage:** 100%
- All 8 calculation cases and all 7 extraction cases passed with deterministic modules in Mode B, with zero model calls and zero wall time.

### 2. Broader operational count (all cases completed without real model inference)

- **Count:** 15
- **Denominator:** 30 total cases
- **Percentage:** 50%
- Mode B routed 15 of 30 cases through deterministic modules (calculation, extraction) without model inference. The remaining 15 cases (8 retrieval + 7 generation) required the model.

**Note:** The broader measure is not equivalent to quality-proven completion. The 15 no-model cases include 8 retrieval cases that were misrouted to `small_direct` (wrong route) and failed scoring, plus 7 generation cases that correctly required the model. Only the 15 deterministic cases (calculation + extraction) represent genuinely model-free, quality-proven completion.

---

## Findings and limitations

Modular routing halved the model-call count relative to forced mode (15 vs 30) but consumed more aggregate model time (170,321 ms vs 94,864 ms) because retrieval cases invoked the model with evidence-augmented prompts; the instrumentation does not yet separate prompt-processing time from output-generation time, so the precise cause of the higher model-step latency is unestablished. SQLite FTS5 retrieval itself is negligible (0–8 ms per case), confirming the bottleneck is model inference, not routing or retrieval. Under strong numeric scoring, modular deterministic calculation materially outperformed the forced-model baseline: Mode B scored 8/8 (100%) while Mode C scored 2/8 (25%), proving the router correctly avoids model error on deterministic tasks. Extraction results are strong (7/7 for both modes) but narrow — only 3-field invoices were tested. Retrieval and generation conclusions remain provisional because their scoring is moderate/weak and cannot distinguish quality differences between modes. The next experiment should instrument prompt token count, retrieved-evidence length, generated tokens, and stop reason for each model call to decompose the model-step bottleneck.

---

## Accuracy constraints

- This report does not claim Mode B saved aggregate model time.
- This report does not claim longer output caused retrieval latency.
- This report does not call Mode A an AI-quality benchmark.
- This report does not claim model replacement, GPU replacement, or general CPU-native superiority.
- All quality claims are bounded by the stated scoring strengths and limitations.
