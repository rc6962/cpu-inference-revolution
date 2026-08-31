# Implementation Note: cpu-cognitive-runtime-python

**Date:** 2026-08-31  
**Files changed:** `runtime.py` (+86/-10), `pyproject.toml` (+3)  
**Branch:** main (uncommitted)

---

## 1. What Changed

### SmallModel GGUF lazy loading
- Added `__init__(model_path)` and `_load_model()` to `SmallModel`
- Model loaded on first `run()` call, not at import or `Runtime()` construction
- Reads `CPU_INFERENCE_MODEL_PATH` env var; falls back to hardcoded demo output if unset or file missing
- Uses `llama-cpp-python` Llama class with `n_ctx=512, n_threads=8`

### Chat completion migration
- Replaced `self._llm(prompt)` (raw text completion) with `self._llm.create_chat_completion(messages=...)`
- Non-retrieval: single `{"role": "user"}` message
- Retrieval: `system` + `user` messages with evidence context
- Response access changed from `["text"]` to `["message"]["content"]`
- Trusts GGUF embedded `tokenizer.chat_template` — no explicit `chat_format` set

### Retrieval source_id preservation
- Post-processing unchanged: if `source_id not in text`, prepends `"Based on {source_id}: "`
- System message in retrieval mode instructs model to include source name
- Ensures original test assertion `"demo-policy.txt" in result.output` passes in both demo and model modes

### RequestAnalyzer text-only invoice routing
- Changed condition from `self._invoice.search(text) and context.request.attachments` to include text-only prompts with strong field signals
- Added compound check: `(context.request.attachments or _invoice_fields.search(text))` where `_invoice_fields` matches `vendor|subtotal|total`
- Fixes misrouting of `"Extract invoice: Vendor Acme, Tax 45, Total 245"` to `small_direct`

### InvoiceExtractor regex improvements
- **total/tax:** `([\d,.]+)` → `(\d[\d,.]*\d|\d)` — digit-bounded, rejects trailing periods (`245.00.`)
- **vendor:** `vendor\s*[:]\s*([^,\n]+)` → `\bvendor\b\s*(?::|\s)\s*([^,\n]+?)\s*(?=,\s*(?:tax|total)\b|$)` — colon OR space separator, lookahead stops at next field
- Fixes `ValueError: could not convert string to float: '183.00.'` crash
- Enables space-separated format: `"Vendor Acme, Tax 45, Total 245"`

### pyproject.toml
- Added `[project.optional-dependencies] llm = ["llama-cpp-python>=0.3.0"]`

---

## 2. Why Each Change Was Made

| Change | Reason |
|--------|--------|
| GGUF lazy loading | Avoid 10s load time at startup; load only when SmallModel route is selected |
| Chat completion | Cleaner output, less repetition, proper system/user role separation, template-aware formatting |
| source_id post-processing | Original test asserts `demo-policy.txt in output`; raw model output omits source reference |
| InvoiceAnalyzer fix | Text-only invoice prompts were misclassified as `small_direct`, causing 25s unnecessary SmallModel inference |
| Vendor regex | `"Vendor Acme"` (no colon) returned `vendor: null`; space-separated is common in natural language |
| Number regex | `"Total: 245.00."` crashed with `ValueError` due to trailing period in capture group |

---

## 3. Verified Behavior

| Test | Fallback | Model-loaded |
|------|:--------:|:------------:|
| `test_calculation_uses_deterministic_route` | ✅ | ✅ |
| `test_retrieval_route_contains_source_evidence` | ✅ | ✅ |
| `test_invoice_route_extracts_and_verifies` | ✅ | ✅ |
| `test_successful_result_is_cached` | ✅ | ✅ |

| Manual check | Result |
|--------------|--------|
| small_direct output quality | Clean, professional rewrites via chat completion |
| small_rag source_id presence | `demo-policy.txt` in output via post-processing |
| Text-only invoice routing | `route=invoice_extraction`, `SmallModel=False` |
| Colon-separated invoice | `vendor=Example Co, tax=19.8, total=119.8` |
| Space-separated invoice | `vendor=Acme Corp, tax=45.0, total=245.0` |
| Trailing period | No crash; `total=62.5` extracted cleanly |
| Cache hit | 0.03ms, `exact_cache` route |
| Fallback regression | Identical demo strings when `CPU_INFERENCE_MODEL_PATH` unset |

---

## 4. Known Limitations

- **Vendor parsing:** `"Vendor: A, B, C, Tax: 10"` captures `A` only (stops at first comma). Comma-separated multi-word vendor names require a different delimiter or NLP parsing.
- **Retrieval answer quality:** Model sometimes echoes evidence text verbatim or produces meta-commentary ("The document does not specify...") instead of a direct answer. Grounding depends on evidence text quality and prompt wording.
- **Latency:** ~13s per SmallModel inference on i7-11700T @ 1.4GHz (9.6 TPS). This is a hardware ceiling; `n_threads` and `n_ctx` tuning showed <2% variance.
- **RAM:** 3.1 GB used by 3B Q4 model. Leaves 2.2 GB free on 15.45 GB machine — tight for concurrent workloads.
- **No streaming:** `create_chat_completion` blocks until full response is generated. No token-by-token streaming.
- **InvoiceExtractor scope:** Only extracts `vendor`, `tax`, `total`. Does not handle `invoice_number`, `date`, `line_items`, `subtotal`, or `due_date`.
- **No persistent cache:** Exact-response cache is in-memory only (`dict`). Resets on process restart.
- **Verifier is minimal:** Checks `total is not None` and evidence score. No schema validation, no arithmetic cross-check (e.g., tax + subtotal = total).

---

## 5. Recommended Next Steps (Priority Order)

1. **Replace `DocumentRetriever` with SQLite FTS5** — current retriever returns synthetic evidence; real retrieval with source-linked records would make `small_rag` answers grounded and useful
2. **Add streaming to SmallModel** — enable token-by-token output for better UX in interactive use
3. **Expand `InvoiceExtractor`** — add `invoice_number`, `date`, `line_items` regex patterns; consider JSON schema validation in Verifier
4. **Add persistent cache** — SQLite-backed with TTL and size limits; survives restarts
5. **Improve Verifier** — arithmetic cross-check (tax + subtotal ≈ total), schema validation for invoice JSON, evidence confidence thresholding
6. **Benchmark with a 1.5B model** — compare quality/latency tradeoff for cost-sensitive deployments
7. **Add shadow-mode analyzer** — log proposed routes without activating, collect classification accuracy data
8. **Build benchmark JSONL harness** — standardized replay for regression testing across model swaps
