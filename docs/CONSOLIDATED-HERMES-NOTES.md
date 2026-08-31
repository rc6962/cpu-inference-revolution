# CPU Inference Revolution — Consolidated Hermes Notes

**Project:** `cpu-inference-revolution`  
**Runtime:** `runtime/cpu-cognitive-runtime-python`  
**Date:** August 31, 2026  
**Current status:** Working research prototype with CPU-local GGUF inference, chat completion, deterministic routing, improved invoice extraction, passing tests, and an approved plan for SQLite FTS5 retrieval.

---

## 01 — Repository Inventory

| File | Lines | Dependencies | Purpose | Status |
|---|---:|---|---|---|
| `cognitive_runtime/runtime.py` | 415 originally | Python stdlib initially | Core runtime: seven modules, execution graph, cache, analyzer, traces | Functional placeholder; now enhanced |
| `example.py` | 135 | `runtime.py` | Demo of four request types plus cache hit | Functional |
| `tests/test_runtime.py` | 46 | `runtime.py`, `pytest` | Tests calculation, retrieval, invoice, and cache | 4/4 passing |
| `pyproject.toml` | 8 originally | None | Package metadata, Python >= 3.10 | Updated with optional LLM dependency |
| `README.md` | 59 | None | Runtime docs, execution/replacement guidance | Correct |
| `docs/cpu-native-ai-conversation-reference.md` | 1085 | None | Design conversation reference, 11 sections | Documentation |
| `docs/cpu-first-llm-starting-guide.md` | 690 | None | 17-section implementation guide | Documentation |
| `docs/cpu-native-cognitive-serving-blueprint.md` | 1474 | None | Architecture blueprint, 27 sections and 90-day plan | Documentation |
| `docs/cpu-native-tonight-lab-plan.md` | 503 | None | 4–6 hour lab plan | Documentation |
| `.gitignore` | 3 originally | None | Ignores Python and pytest cache artifacts | Updated later in planned FTS work |

---

## 02 — Original Runtime Modules

| Module | Class | Input Contract | Output Contract | Original Behavior | Status |
|---|---|---|---|---|---|
| Request Analyzer | `RequestAnalyzer` | Request text, permissions, attachments | `Analysis` | Regex-based route classification | Functional; later improved |
| Calculator | `Calculator` | `context["request"].text` | Expression, result, formatted result | Regex two-number calculation | Functional/deterministic |
| Document Retriever | `DocumentRetriever` | Input text, evidence | `ModuleResult` with source, location, text | Synthetic `demo-policy.txt` evidence | Placeholder; next target |
| Small Model | `SmallModel` | Prompt | `ModuleResult(output=str)` | Hardcoded demo response | Replaced with local GGUF model |
| Invoice Extractor | `InvoiceExtractor` | Text, attachments | Vendor, tax, total fields | Regex extraction/validation | Improved |
| Response Renderer | `ResponseRenderer` | Text | `ModuleResult(output=text)` | Pass-through | Functional/deterministic |
| Verifier | `Verifier` | Output, route | Verification result | Schema/arithmetic-style checks | Functional but minimal |

---

## 03 — Baseline Validation

### Commands run

```bash
python3 example.py
python3 -m pytest -q
```

### Results

| Check | Result |
|---|---|
| Runtime example | Functional |
| Test suite | 4/4 tests passing |
| Calculator route | Working |
| Retrieval route | Working with synthetic evidence |
| Invoice route | Working for original attached-file demo |
| Exact-response cache | Working |

### Baseline conclusion

The stock runtime worked before modifications. It was a deterministic placeholder prototype designed to support gradual replacement of modules while preserving execution-graph contracts, tests, and telemetry.

---

## 04 — SmallModel Replacement Decision

### Replacement candidates ranked by Hermes

| Rank | Module | Proposed Replacement | Risk | Rationale |
|---:|---|---|---|---|
| 1 | `SmallModel` | Local GGUF via `llama-cpp-python` | Low | End-of-pipeline, simple contract, limited routes, verifier available |
| 2 | `DocumentRetriever` | SQLite FTS5 local index | Medium | Simple contract, needs index/data setup |
| 3 | `InvoiceExtractor` | Small extraction model | Medium | Regex already useful; model adds complexity |
| 4 | `RequestAnalyzer` | Classifier or small LLM | High | Controls all routing; classification errors cascade |
| 5 | `Calculator` | LLM/code execution | High | Deterministic regex is faster and more reliable |
| 6 | `Verifier` | LLM judge | High | Safety-critical; LLM could weaken verification |
| 7 | `ResponseRenderer` | LLM paraphraser | High | Current pass-through behavior is correct and cheap |

### Decision

`SmallModel` was selected as the first real replacement.

---

## 05 — GGUF SmallModel Integration

### Files changed

| File | Change |
|---|---|
| `cognitive_runtime/runtime.py` | Added local model path handling, lazy GGUF loading, real local inference, safe fallback |
| `pyproject.toml` | Added optional LLM dependency group |

### Dependency added

```toml
[project.optional-dependencies]
llm = ["llama-cpp-python>=0.3.0"]
```

### Installed runtime dependency

| Package | Version | Installation method |
|---|---|---|
| `llama-cpp-python` | 0.3.35 | Prebuilt CPU wheel |
| `diskcache` | 5.6.3 | Installed as dependency |

### Model selected

| Item | Value |
|---|---|
| Model | Qwen2.5-3B-Instruct |
| Format | GGUF |
| Quantization | Q4_K_M |
| File size | Approximately 2.0 GB |
| Local path | `E:/cpu-inference-revolution/models/qwen2.5-3b-instruct-q4_k_m.gguf` |
| Environment variable | `CPU_INFERENCE_MODEL_PATH` |

### Runtime configuration

```python
Llama(
    model_path=self._model_path,
    n_ctx=512,
    n_threads=8,
    verbose=False,
)
```

### Safety/fallback behavior

- If `CPU_INFERENCE_MODEL_PATH` is unset, the runtime keeps original demo-style output.
- If the model file does not exist, the runtime falls back safely.
- If `llama_cpp` is unavailable or model loading fails, the runtime falls back safely.
- If an inference call fails, it returns a demo-style response with a warning rather than crashing.

---

## 06 — GGUF Integration Test Results

| Condition | Result |
|---|---|
| Tests, no model path set | 4/4 passing |
| `example.py`, no model path set | Original fallback/demo strings returned |
| Model download | Completed successfully |
| Model file verification | Approximately 2.0 GB file present |
| `example.py`, model path set | Real inference worked on `small_direct` and `small_rag` |
| Tests, model path set | Initially 3/4 due to retrieval-source assertion |
| Fallback regression after unsetting model path | 4/4 passing |

### Initial performance observations

| Metric | Result |
|---|---:|
| First model-related request | Approximately 27.8 seconds in one early test |
| Subsequent direct request in early test | Approximately 3.6 seconds |
| Deterministic calculation/invoice routes | Under 1 ms when correctly routed |
| Cache hit | Instant |

---

## 07 — Retrieval Source-ID Compatibility Fix

### Problem

The original retrieval test expected the output to contain:

```
demo-policy.txt
```

With real model generation enabled, the LLM answered the question but did not necessarily include the source file name.

### Failure

```
AssertionError:
assert 'demo-policy.txt' in result.output
```

### Root cause

The old synthetic SmallModel output always embedded the source in this style:

```
Based on demo-policy.txt: ...
```

The real model generated a natural-language answer without guaranteed source citation.

### Fix applied

Inside `SmallModel.run()`:

1. Retrieval prompt tells the model to use only the supplied evidence.
2. Retrieval prompt tells the model to include the source name.
3. Post-processing checks whether `source_id` appears in output.
4. If not, it prepends:

```
Based on {source_id}:
```

### Validation results

| Condition | Result |
|---|---|
| Tests with model path unset | 4/4 passing |
| Tests with model path set | 4/4 passing |
| Retrieval response | Included `demo-policy.txt` |
| Test file changes | None |
| Files changed for this fix | `runtime.py` only |

---

## 08 — Invoice Routing Investigation

### Problem found

A text-only invoice request was being sent to `small_direct` and the local LLM instead of `invoice_extraction`.

### Example failing input

```
Extract invoice: Vendor Acme Corp, Tax 45, Total 245
```

### Trace result before fix

| Step | Module | CPU time | Correct? |
|---|---|---:|---|
| Generate | `small_model` | 24,936 ms | No |
| Render | `response_renderer` | 0.0 ms | N/A |

### Root cause

The original analyzer condition required both:
- invoice-related keywords, and
- at least one attachment.

Original condition:

```python
if self._invoice.search(text) and context.request.attachments:
```

Without attachments, a text invoice request fell through to `small_direct`.

### Routing fix applied

```python
_invoice_fields = re.compile(r"\b(?:vendor|subtotal|total)\b", re.I)
if self._invoice.search(text) and (
    context.request.attachments or _invoice_fields.search(text)
):
```

### Validation after routing fix

| Check | Result |
|---|---|
| Tests, fallback mode | 4/4 passing |
| Tests, model-loaded mode | 4/4 passing |
| Text-only invoice route | `invoice_extraction` |
| Modules invoked | `invoice_extractor` → `verifier` → `response_renderer` |
| `SmallModel` invoked | No |
| Invoice route latency | About 0.2 ms extractor, near-zero verifier/render |
| Result before regex improvement | Tax/total extracted; vendor initially `null` for space-separated wording |

---

## 09 — SmallModel Chat-Completion Migration

### Change made

The real-model call was migrated from raw completion:

```python
self._llm(prompt, max_tokens=256, temperature=0.0)
```

to chat completion:

```python
self._llm.create_chat_completion(
    messages=messages,
    max_tokens=256,
    temperature=0.0,
)
```

### Message design

| Route | Messages |
|---|---|
| `small_direct` | One user message |
| `small_rag` | System instruction plus user message containing evidence and question |

### Retrieval system instruction

The system message directs the model to:
- answer only from supplied evidence,
- include the source name in its response.

### Chat-template decision

- The GGUF model included embedded chat-template metadata.
- Hermes verified the metadata/handler was available.
- No explicit `chat_format` was set.
- The embedded Qwen template was trusted.

### Validation results

| Check | Result |
|---|---|
| Tests, fallback mode | 4/4 passing in 1.54 seconds |
| Tests, model mode | 4/4 passing in 25.28 seconds |
| `small_direct` sample | "The meeting proceeded as expected." |
| `small_rag` source ID present | Yes |
| Text-only invoice route | Correctly stayed on `invoice_extraction` |
| `SmallModel` used for invoice | No |

---

## 10 — InvoiceExtractor Regex Improvements

### Problems fixed

1. Vendor was missing for space-separated wording:
   ```
   Vendor Acme Corp
   ```
2. Trailing sentence punctuation caused float parsing errors:
   ```
   Total: 245.00.
   ```

### Exact regex changes

```diff
- total_match = re.search(r"total\s*[:$]?\s*([\d,.]+)", text, re.I)
- tax_match = re.search(r"tax\s*[:$]?\s*([\d,.]+)", text, re.I)
- vendor_match = re.search(r"vendor\s*[:]\s*([^,\n]+)", text, re.I)

+ total_match = re.search(r"total\s*[:$]?\s*(\d[\d,.]*\d|\d)", text, re.I)
+ tax_match = re.search(r"tax\s*[:$]?\s*(\d[\d,.]*\d|\d)", text, re.I)
+ vendor_match = re.search(
+     r"\bvendor\b\s*(?::|\s)\s*([^,\n]+?)\s*(?=,\s*(?:tax|total)\b|$)",
+     text,
+     re.I,
+ )
```

### Validation results

| Input | Vendor | Tax | Total | Result |
|---|---|---:|---:|---|
| `Vendor: Example Co, Tax: 19.80, Total: 119.80` | Example Co | 19.8 | 119.8 | Pass |
| `Vendor Acme Corp, Tax 45, Total 245` | Acme Corp | 45.0 | 245.0 | Pass |
| `Vendor Beta Inc, Tax 12.50, Total: 62.50.` | Beta Inc | 12.5 | 62.5 | Pass |
| Full test suite | N/A | N/A | N/A | 4/4 passing |

### Remaining invoice limitation

This still does not fully support a vendor value with commas, such as:

```
Vendor: A, B, C, Tax: 10, Total: 20
```

The current extraction will stop at the first comma. That is a future parsing improvement, not a regression.

---

## 11 — Benchmark Results, Initial

### Hardware

| Item | Value |
|---|---|
| CPU | Intel Core i7-11700T |
| Cores/threads | 8 cores / 16 threads |
| Base clock | 1.4 GHz |
| RAM | 15.45 GB |
| OS | Windows 11 Pro |

### Fallback mode

| Metric | Result |
|---|---:|
| Cold load | 0.1–0.2 ms |
| `small_direct` | About 0.1 ms |
| `small_rag` | About 0.1 ms |
| Deterministic calculation | About 0.1 ms |
| Invoice extraction | About 0.1 ms |
| Cache hit | 0.0 ms |
| RAM impact | No measurable change |

### Initial model-loaded measurements

| Metric | Result |
|---|---:|
| Cold model load plus first inference | Approximately 10 seconds |
| Free RAM before model load | Approximately 5.18 GB |
| Free RAM after model load | Approximately 2.08 GB |
| Approximate model RAM usage | Approximately 3.1 GB |
| Cache hit | Approximately 0.03 ms |
| Deterministic calculation | About 0.2 ms |

### Important benchmark correction

The early benchmark mixed cache hits, cold load, and fresh runtime instances. Hermes then created a cleaner benchmark using:
- unique prompts,
- a single persistent `Runtime()` instance for warm tests,
- three runs per route,
- separately tracked cold behavior.

---

## 12 — Benchmark Results, Clean Version

### Model-loaded mode

| Metric | Min | Average | Max | Notes |
|---|---:|---:|---:|---|
| Cold load plus first inference | N/A | 13,004 ms | N/A | First model request |
| `small_direct`, warm unique prompts | 26,734 ms | 27,165 ms | 28,003 ms | Real uncached model calls |
| `small_rag`, reported average | 0.1 ms | 12,836 ms | 27,433 ms | First run was cached; true uncached calls near 27 seconds |
| Deterministic calculation | 0.1 ms | 0.2 ms | 0.3 ms | No model involvement |
| Invoice route, before routing fix | 20,955 ms | 24,172 ms | 25,946 ms | Misclassified to `small_direct` |
| Exact cache hit | 0.0 ms | 0.03 ms | 0.1 ms | Instant |
| RAM used by model | N/A | 3.11 GB | N/A | Free memory about 5.34 GB to 2.23 GB |

### Important conclusions

- The model integration works.
- Cache hits are extremely valuable.
- Thread and context tuning did not materially improve results.
- The slow invoice timing was caused by request misclassification, which was later fixed.
- A fresh unique prompt is much slower than a cache hit.
- Retrieval measurements must avoid previously cached output when evaluating model latency.

---

## 13 — SmallModel Tuning Matrix

**Test settings:** Same prompt, `max_tokens=128`, `temperature=0.0`.

| Configuration | Load time | Cold time | Warm time | Throughput |
|---|---:|---:|---:|---:|
| 6 threads / 256 context | 1,941 ms | 14,649 ms | 13,188 ms | 9.7 TPS |
| 6 threads / 512 context | 2,003 ms | 14,793 ms | 13,304 ms | 9.6 TPS |
| 8 threads / 256 context | 1,920 ms | 14,982 ms | 13,280 ms | 9.6 TPS |
| 8 threads / 512 context | 1,930 ms | 14,982 ms | 13,249 ms | 9.7 TPS |
| 10 threads / 256 context | 1,940 ms | 15,065 ms | 13,404 ms | 9.5 TPS |
| 10 threads / 512 context | Not measured in same run | 15,006 ms | 13,345 ms | 9.6 TPS |

### Tuning conclusion

| Finding | Conclusion |
|---|---|
| 6 vs. 8 vs. 10 threads | Less than 2% difference |
| 256 vs. 512 context | Less than 1% difference for short prompts |
| Warm generation | Roughly 13.2–13.4 seconds in this standardized test |
| Throughput | About 9.5–9.7 tokens/sec |
| Memory | Roughly 3.1 GB |
| Recommended current config | Keep `n_threads=8`, `n_ctx=512` |

No further thread/context tuning is currently justified. The larger performance improvements will come from caching, smaller model comparisons, higher sustained CPU frequency, or using hardware better suited to local inference.

---

## 14 — Current Known Limitations

| Area | Limitation |
|---|---|
| Retrieval | Still synthetic; no real local document index yet |
| Retrieval answers | May echo evidence or provide meta-commentary instead of a direct answer |
| Model latency | Approximately 13 seconds or more for real uncached SmallModel inference |
| Memory | 3B Q4 model consumes about 3.1 GB RAM; available headroom is limited |
| Streaming | No token-by-token output; chat completion blocks until response completes |
| Persistent cache | Cache is in-memory only and resets on restart |
| Invoice extraction | Extracts vendor, tax, total only |
| Invoice vendor names | Comma-containing vendor names remain a parsing edge case |
| Invoice data | No invoice number, date, line items, subtotal, or due date extraction |
| Verifier | Minimal; lacks schema validation and arithmetic cross-checks |
| Analyzer | Still regex-based; no shadow mode or route-accuracy dataset yet |
| Benchmark harness | No persistent JSONL regression/replay harness yet |

---

## 15 — Approved SQLite FTS5 Retriever Plan

### Next replacement target

Replace the synthetic `DocumentRetriever` with local SQLite FTS5 search.

### Intended files

| File | Planned change |
|---|---|
| `cognitive_runtime/runtime.py` | Add FTS5-backed `DocumentRetriever` with safe fallback |
| `data/seed.jsonl` | New seed dataset with documents/chunks |
| `data/init_db.py` | New script to create and populate local DB |
| `.gitignore` | Ignore generated `data/knowledge.db` |
| `data/knowledge.db` | Generated locally; not committed |
| `pyproject.toml` | No change; `sqlite3` is standard library |

### Core design

| Component | Plan |
|---|---|
| Database | SQLite |
| Search | FTS5 virtual table |
| Indexing | Source ID, location, and text |
| Ranking | FTS5 BM25 for ordering |
| External services | None |
| Vector embeddings | None |
| Data source | Local `seed.jsonl` initially |
| Fallback if DB missing | Preserve current synthetic evidence behavior |
| Fallback if no match | Synthetic evidence with lower compatibility score |

### Important implementation constraints

- `knowledge.db` must be generated locally from source data.
- Do not check the database file into Git.
- Populate the FTS index explicitly during initial database creation; do not rely only on triggers for initial content.
- Use BM25 to order results.
- Do not convert raw BM25 into a fake calibrated 0–1 confidence score.
- For compatibility, use simple retrieval scores initially:
  - `0.84` when a real result exists
  - `0.50` for fallback/no match
- Preserve the existing `DocumentRetriever` evidence contract.

### Expected evidence output

```python
{
    "source_id": "demo-policy.txt",
    "location": "local",
    "text": "The policy requires a 30 day notice period...",
    "retrieval_score": 0.84,
}
```

---

## 16 — Current Recommended Next Steps

| Priority | Task | Purpose |
|---:|---|---|
| 1 | Complete SQLite FTS5 retriever implementation | Replace synthetic retrieval with real local documents |
| 2 | Validate FTS DB creation, direct queries, retriever output, full test suite | Ensure real retrieval preserves contract and fallback |
| 3 | Improve retrieval prompt/evidence formatting | Reduce weak or meta-commentary model answers |
| 4 | Add persistent cache with SQLite, TTL, and size limits | Preserve useful cache behavior across restarts |
| 5 | Improve verifier | Add invoice schema checks and subtotal/tax/total validation |
| 6 | Add streaming to SmallModel | Improve interactive UX |
| 7 | Benchmark Qwen 1.5B GGUF | Measure latency/RAM/quality trade-off |
| 8 | Add shadow-mode analyzer | Collect route predictions without affecting real routing |
| 9 | Build JSONL benchmark/replay harness | Prevent regression during future module replacements |

---

## 17 — Current Milestone Summary

```
[Baseline runtime + tests]
          COMPLETE
               ↓
[SmallModel GGUF local inference]
          COMPLETE
               ↓
[Fallback behavior and test compatibility]
          COMPLETE
               ↓
[Retrieval source citation preservation]
          COMPLETE
               ↓
[Invoice routing correction]
          COMPLETE
               ↓
[Invoice regex hardening]
          COMPLETE
               ↓
[Chat-completion migration]
          COMPLETE
               ↓
[CPU benchmark and tuning matrix]
          COMPLETE
               ↓
[SQLite FTS5 real DocumentRetriever]
          COMPLETE
               ↓
[Persistent memory, verifier, streaming, replay harness]
          FUTURE
```

The next active work item is the **SQLite FTS5 DocumentRetriever replacement**. SQLite FTS5 provides a local virtual-table full-text-search mechanism and is well suited to the repo's CPU-first, dependency-light direction.

---

## 18 — SQLite FTS5 Retriever Implementation

### Files changed

| File | Change |
|---|---|
| `.gitignore` | Added `data/knowledge.db` |
| `cognitive_runtime/runtime.py` | Rewrote `DocumentRetriever`; also contains prior SmallModel/chat/analyzer/invoice changes |
| `pyproject.toml` | Optional `llm` dependency remains present |
| `data/seed.jsonl` | New; 10 seed documents |
| `data/init_db.py` | New DB initialization/backfill script |

### Validation results

| Check | Result |
|---|---|
| DB initialization | 10 documents loaded into `data/knowledge.db` |
| Direct SQLite query | `policy OR days OR notice OR required` returned `demo-policy.txt` with rank about −1.98 |
| Retriever example | Successful `small_rag` response grounded in `demo-policy.txt` |
| Full test suite | 4/4 passing |

### Retriever behavior

| Condition | Behavior |
|---|---|
| DB exists + FTS match found | Returns real document chunk, `retrieval_score=0.84` |
| DB exists + no match | Synthetic fallback, `retrieval_score=0.50` |
| DB missing | Synthetic fallback, unchanged behavior |

### Important implementation notes

Initial FTS debugging found query mismatch due to:

- Stop words
- Punctuation
- Wrong variable passed into `_query`
- FTS default strictness causing misses on natural-language prompts

Final fix used:

- Query preprocessing
- Punctuation stripping
- OR semantics for the generated FTS query so common user wording still hits seed documents

SQLite FTS5 supports explicit boolean operators like `OR`, while whitespace-only terms imply `AND`.

---

## 19 — Current Runtime State After FTS5

| Item | Detail |
|---|---|
| Status | Working local CPU-first cognitive runtime with real local retrieval |
| Date | 2026-08-31 |

### Active capabilities

| Capability | Current implementation | Status |
|---|---|---|
| CPU local LLM | Qwen2.5-3B-Instruct Q4_K_M GGUF through llama-cpp-python | Working |
| LLM loading | Lazy load through `CPU_INFERENCE_MODEL_PATH` | Working |
| Fallback mode | Original deterministic/demo behavior when model path is absent or model fails to load | Working |
| Chat formatting | `create_chat_completion()` using the GGUF's embedded chat template | Working |
| Direct generation | `small_direct` → SmallModel | Working |
| Retrieval-augmented generation | `small_rag` → DocumentRetriever → SmallModel → Verifier → renderer | Working |
| Retrieval backend | SQLite FTS5 local full-text search | Working |
| Retrieval data | `data/seed.jsonl`, initialized into local `data/knowledge.db` | Working |
| Retrieval fallback | Synthetic evidence if database is missing or no FTS result is found | Working |
| Calculation | Deterministic regex calculator | Working |
| Invoice routing | Attachment-based and strong text-field-signal routing | Working |
| Invoice extraction | Regex extraction for vendor, tax, total | Working |
| Cache | In-memory exact-response cache | Working |
| Tests | Four original tests | 4/4 passing |
