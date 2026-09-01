# Post-Retrieval-Hardening Three-Mode Benchmark Report

**Date:** 2026-09-01
**Status:** Exploratory single-machine baseline — not a production benchmark
**Predecessors:** first-three-mode-benchmark-report.md, post-routing-fix-three-mode-benchmark-report.md

---

## Benchmark execution

| Field | Value |
|-------|-------|
| Commit SHA | `12d6972` |
| OS | Windows 11 Pro (10.0.26200) |
| CPU | Intel i7-11700T (8C/16T @ 1.40GHz) |
| RAM | 15.45 GB total |
| Python | 3.11.15 |
| SQLite | 3.53.1 with FTS5 |
| llama-cpp-python | 0.3.35 (pre-built CPU wheel) |
| Model | Qwen2.5-3B-Instruct Q4_K_M (2.0 GB GGUF) |
| Model settings | n_ctx=512, n_threads=8, max_tokens=256, temperature=0.0 |
| Seed documents | 13 (policy, handbook, contract, invoice-spec, it-policy) |
| Benchmark cases | 30 (8 calculation, 8 retrieval, 7 extraction, 7 generation) |

This benchmark follows retrieval-routing fixes, deterministic FTS5 reranking, and seed-corpus ground-truth corrections applied since v0.2-post-routing-benchmark.

---

## Mode A: Fallback (no model)

| Metric | Value |
|--------|-------|
| Total requests | 30 |
| Total wall time | 19 ms |
| Avg per request | 1 ms |
| Median | 0 ms |
| P95 | 3 ms |
| Model step total | 0 ms |
| Retrieval step total | 15.6 ms |
| SmallModel module calls | 15 |
| Real LLM inferences | 0 |
| Fallback responses | 15 |
| Verification | 15/15 |

### Category correctness

| Category | Pass | Total | Rate | Strength |
|----------|:----:|:-----:|:----:|:--------:|
| calculation | 8 | 8 | 100% | STRONG |
| retrieval | 8 | 8 | 100% | MODERATE |
| extraction | 7 | 7 | 100% | STRONG |
| generation | 7 | 7 | 100% | WEAK |
| **TOTAL** | **30** | **30** | **100%** | |

### Retrieval metrics

- Route accuracy: 30/30 (100%)
- Source retrieval: 8/8
- Retrieval answer: 8/8

---

## Mode B: Modular real-model

| Metric | Value |
|--------|-------|
| Total requests | 30 |
| Total wall time | 96,082 ms |
| Avg per request | 3,203 ms |
| Median | 720 ms |
| P95 | 13,415 ms |
| Model step total | 96,048 ms |
| Retrieval step total | 25.5 ms |
| SmallModel module calls | 15 |
| Real LLM inferences | 15 |
| Fallback responses | 0 |
| Verification | 15/15 |

### Category correctness

| Category | Pass | Total | Rate | Strength |
|----------|:----:|:-----:|:----:|:--------:|
| calculation | 8 | 8 | 100% | STRONG |
| retrieval | 8 | 8 | 100% | MODERATE |
| extraction | 7 | 7 | 100% | STRONG |
| generation | 7 | 7 | 100% | WEAK |
| **TOTAL** | **30** | **30** | **100%** | |

### Retrieval metrics

- Route accuracy: 30/30 (100%)
- Source retrieval: 8/8
- Retrieval answer: 8/8

---

## Mode C: Forced single-model

| Metric | Value |
|--------|-------|
| Total requests | 30 |
| Total wall time | 156,600 ms |
| Avg per request | 5,220 ms |
| Median | 3,273 ms |
| P95 | 16,190 ms |
| Model step total | 156,593 ms |
| Retrieval step total | 0.0 ms |
| SmallModel module calls | 30 |
| Real LLM inferences | 30 |
| Fallback responses | 0 |
| Verification | 0/0 |

### Category correctness

| Category | Pass | Total | Rate | Strength |
|----------|:----:|:-----:|:----:|:--------:|
| calculation | 2 | 8 | 25% | STRONG |
| retrieval | 0 | 8 | 0% | MODERATE |
| extraction | 7 | 7 | 100% | STRONG |
| generation | 7 | 7 | 100% | WEAK |
| **TOTAL** | **16** | **30** | **53%** | |

### Retrieval metrics

- Route accuracy: 0/30 (0%) — by design
- Source retrieval: 0/8
- Retrieval answer: 0/8

---

## Cross-mode comparison

| Metric | Mode A | Mode B | Mode C |
|--------|:------:|:------:|:------:|
| Total score | 30/30 (100%) | 30/30 (100%) | 16/30 (53%) |
| Route accuracy | 30/30 | 30/30 | 0/30 |
| Source retrieval | 8/8 | 8/8 | 0/8 |
| Retrieval answer | 8/8 | 8/8 | 0/8 |
| Real LLM calls | 0 | 15 | 30 |
| Total wall | 19 ms | 96,082 ms | 156,600 ms |
| Avg per request | 1 ms | 3,203 ms | 5,220 ms |
| Strict no-model | 15/15 (100%) | 15/15 (100%) | — |
| Broader no-model | 15/30 (50%) | 15/30 (50%) | 0/30 (0%) |

---

## Analysis

### Why Mode B matches Mode A at 100%

Mode B routes 15 of 30 cases to deterministic modules (Calculator, InvoiceExtractor) that produce identical output to Mode A's fallback. The 15 model-invoked cases (retrieval + generation) produce correct outputs under the current scoring rubric. The modular runtime achieves identical correctness to the no-model baseline while invoking the model only where needed.

### Why Mode C scores 53%

Mode C forces all 30 cases through the 3B model without specialized modules. The model fails on calculation (2/8) because it cannot reliably compute numeric margins. It fails on retrieval (0/8) because it has no access to the seed corpus. It succeeds on extraction (7/7) because the task-aware system prompt produces parseable JSON. It succeeds on generation (7/7) because the weak gate only requires non-empty output.

### Retrieval latency breakdown

FTS5 retrieval itself contributes negligible time (0.1–8 ms per case). The model step dominates at 8,000–13,000 ms per retrieval case. The deterministic reranking (phrase overlap, rare-term scoring) correctly selects the right document for all 8 cases without adding measurable latency.

### Limitations by scoring strength

| Category | Strength | Limitation |
|----------|:--------:|------------|
| calculation | STRONG | Only tests 2-number margin calculations |
| retrieval | MODERATE | Substring matching only; not semantic correctness |
| extraction | STRONG | Only tests 3-field invoices |
| generation | WEAK | Non-empty gate only; cannot claim quality |

---

## Strict and broader no-model counts

| Measure | Mode A | Mode B | Mode C |
|---------|:------:|:------:|:------:|
| Strict (strongly-scored, no model) | 15/15 (100%) | 15/15 (100%) | — |
| Broader (all cases, no model) | 15/30 (50%) | 15/30 (50%) | 0/30 (0%) |

---

## Interpretation constraints

- This is a **30-case fixed single-machine exploratory benchmark**, not a production quality claim.
- Mode C is a **practical forced-model product baseline**, not an optimized conventional CPU-serving baseline.
- Retrieval scoring tests substring presence, not semantic correctness or completeness.
- Generation scoring is a regression gate, not a quality measure.
- No causal model-latency conclusions can be drawn because prompt-processing and decode timings are not separated in the current instrumentation.
- Do not claim general CPU superiority, GPU replacement, production scalability, or broad enterprise quality from these results.
