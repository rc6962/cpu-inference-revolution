# CPU-First LLM Serving: An Ordered Starting Guide

**Author:** Manus AI  
**Purpose:** Provide a practical sequence for building, measuring, and improving a CPU-first LLM serving system before attempting a ground-up model redesign.

## Executive recommendation

Start by redesigning **how inference is selected and coordinated**, not by immediately training a new neural architecture. Build a measurable serving layer around existing small, quantized models. This will show which requests truly require expensive computation and which can be completed through caching, retrieval, deterministic tools, or a small specialist model.

The central hypothesis is:

> A CPU-first AI system can achieve a better cost-and-latency-to-task-success ratio by routing each request to the cheapest reliable computation path.

The project should therefore proceed in stages:

1. Establish a reproducible CPU baseline.
2. Build a request analyzer with explicit rules.
3. Add deterministic handlers and caching.
4. Add retrieval and compact working memory.
5. Add a multi-model cascade.
6. Add verification and selective escalation.
7. Run controlled experiments.
8. Only then redesign model internals or train a new architecture.

Do not begin with open-ended chatbot quality as the primary objective. Select one narrow workload, such as invoice extraction, internal policy question answering, ticket triage, or local coding assistance. A narrow workload gives you a benchmark that can distinguish genuine efficiency from an impressive but unmeasurable demo.

---

## 1. Define the first target

Choose one task family with clear inputs and objectively checkable outputs. The first target should have enough volume to benefit from routing and enough structure to measure correctness.

| Candidate | Why it is suitable | Initial success measure |
|---|---|---|
| Invoice extraction | Structured fields and arithmetic checks are available | Field accuracy and valid JSON |
| Internal policy Q&A | Retrieval and evidence grounding are measurable | Answer accuracy and citation support |
| Support-ticket triage | Labels and escalation decisions are easy to score | Classification F1 and CPU time |
| Local coding assistant | Useful but more difficult to evaluate | Tests passed and latency |
| Contract comparison | Valuable but high-risk and context-heavy | Section-level recall and evidence support |

For a first implementation, **invoice extraction or support-ticket triage** is usually easier than general document chat. If you already have access to a private document collection, internal policy Q&A is also a strong choice.

Write a one-sentence target specification:

> On a specified CPU machine, the system will complete **[task]** with at least **[quality target]**, within **[latency target]**, using no more than **[memory limit]**, while escalating fewer than **[escalation target]** of requests.

For example:

> On an 8-core office CPU with 16 GB RAM, the system will extract invoice fields with at least 97% field accuracy, produce valid JSON for 99% of documents, and complete each document in under 3 seconds without a GPU.

---

## 2. Establish the baseline before optimizing

The baseline must be a simple, single-route system. Use one small quantized model and send every request through it. This is intentionally inefficient; it gives you a comparison point.

Record the following for every test case:

| Measurement | Description |
|---|---|
| Input tokens | Number of tokens supplied to the model |
| Output tokens | Number of generated tokens |
| Time to first token | Delay before generation begins |
| Total latency | End-to-end request time |
| CPU time | Process CPU time, not just wall-clock time |
| Peak RAM | Maximum resident memory |
| Task correctness | Whether the output satisfies the benchmark |
| Format validity | Whether JSON, labels, or required structure is valid |
| Failure category | Hallucination, omission, timeout, malformed output, or other |

Run each case more than once. Separate the first run, which may include model loading, from warm-cache runs. Keep the hardware, operating system, thread count, model file, quantization, prompt, and sampling settings fixed.

The baseline question is:

> How much CPU and latency does the current approach spend per successful task?

That number is more useful than tokens per second alone.

---

## 3. Build the smallest useful system

Create a local service with five components:

```text
Client
  ↓
API gateway
  ↓
Request analyzer
  ↓
Route executor
  ↓
Verifier and metrics logger
```

The initial implementation can be a single process. Avoid microservices until measurements show that a component needs independent scaling.

### Suggested project layout

```text
cpu-first-serving/
├── README.md
├── pyproject.toml
├── config.yaml
├── app/
│   ├── main.py
│   ├── analyzer.py
│   ├── routes.py
│   ├── cache.py
│   ├── retrieval.py
│   ├── models.py
│   ├── verifier.py
│   └── metrics.py
├── data/
│   ├── benchmark.jsonl
│   └── documents/
├── tests/
│   ├── test_analyzer.py
│   ├── test_routes.py
│   └── test_verifier.py
└── reports/
```

Use a local inference runtime that supports quantized models and CPU execution. Keep the runtime replaceable behind a small interface:

```python
class ModelBackend:
    def generate(self, prompt, max_tokens, temperature=0.0):
        raise NotImplementedError
```

This abstraction allows you to compare runtimes and models without rewriting routing logic.

---

## 4. Implement the request analyzer in stages

The analyzer should return a structured decision rather than merely a model name.

```json
{
  "task_type": "structured_extraction",
  "risk_level": "low",
  "difficulty_band": "easy",
  "requires_retrieval": false,
  "requires_tools": false,
  "output_format": "strict_json",
  "recommended_route": "specialist",
  "confidence": 0.91,
  "fallback_route": "deep_fallback"
}
```

### Stage 4.1: Normalize input

Extract:

- Text and quoted text
- Attachments and document identifiers
- Estimated token count
- Language
- Code blocks
- Numbers, dates, URLs, and identifiers
- Requested output format
- Conversation and session identifiers

Preserve numbers, file paths, code, and quoted text. Do not aggressively clean the input before analysis because those features often identify the correct route.

### Stage 4.2: Apply hard-priority rules

Use this order:

1. Permission and security constraints.
2. High-risk or restricted handling.
3. Verified exact-cache lookup.
4. Deterministic operation detection.
5. Recognized database or entity lookup.
6. Retrieval requirement.
7. Task classification.
8. Difficulty estimation.
9. Route selection.
10. Fallback assignment.

The priority order prevents a cheap keyword match from overriding a security or accuracy requirement.

### Stage 4.3: Use multi-label task classification

Allow more than one task label because requests often combine tasks. Use these initial labels:

```text
rewrite
summarization
classification
structured_extraction
retrieval_qa
comparison
calculation
coding
debugging
planning
translation
data_analysis
creative_generation
multi_step_reasoning
unknown
```

Start with rules and a small classifier only after you have enough labeled examples. The classifier should predict task scores, not directly choose a model.

### Stage 4.4: Estimate difficulty in bands

Use three bands at first:

| Band | Approximate score | Meaning |
|---|---:|---|
| Easy | 0.00–0.35 | Direct rewrite, lookup, extraction, or simple classification |
| Moderate | 0.35–0.70 | Retrieval, comparison, explanation, or modest reasoning |
| Hard | 0.70–1.00 | Multi-document synthesis, complex coding, diagnosis, or ambiguous planning |

A transparent score can combine ambiguity, context size, reasoning depth, domain specificity, output complexity, tool dependence, and precision requirements. Do not tune the weights prematurely. Log the features first, then adjust them using benchmark results.

---

## 5. Add deterministic routes before adding more model capacity

The first major optimization should be to avoid neural generation where code is more reliable and cheaper.

Implement these handlers:

| Handler | Examples |
|---|---|
| Calculator | Percentages, margins, conversions, arithmetic |
| Parser | Dates, IDs, email addresses, URLs, known fields |
| Database lookup | Order status, ticket owner, account metadata |
| Schema validator | JSON shape, required fields, type checks |
| Text operations | Word counts, deduplication, sorting, filtering |

A calculation route should return both the expression and result internally:

```json
{
  "operation": "(850000 - 612000) / 850000",
  "result": 0.28,
  "formatted_result": "28.0%"
}
```

If an explanation is requested, send the verified result to a small model only for wording. This separates correctness from language generation.

### Test gate

Do not proceed until you can demonstrate, on the benchmark, that deterministic handlers:

- Correctly identify their supported operations.
- Produce exact results.
- Do not incorrectly capture ordinary language requests.
- Reduce model calls without reducing task success.

Track both **true savings** and **false deterministic matches**.

---

## 6. Add exact caching and session reuse

Implement two forms of reuse.

### Exact response cache

Cache only when:

- The normalized request matches.
- The user has the same permissions.
- Referenced documents have not changed.
- The answer is not time-sensitive.
- The previous answer passed verification.

Exclude requests containing terms such as “latest,” “current,” “today,” or “now,” unless a freshness-aware cache policy exists.

### Session-state reuse

Persist:

- Conversation summary
- Recent task state
- Retrieved evidence
- Tool results
- Stable prompt prefixes
- Document version identifiers

Do not treat the complete conversation as the only memory format. Store compact structured state as well.

### Test gate

Measure:

- Cache hit rate
- Cache correctness
- Average latency reduction
- Invalidations caused by document changes
- Memory consumed by cached state

A cache that is fast but returns stale or unauthorized information is a failure, not an optimization.

---

## 7. Add retrieval as a compact working-memory pipeline

Avoid the simplest form of retrieval-augmented generation, in which entire document chunks are pasted into a long prompt. Use this sequence:

```text
Document collection
  ↓
Keyword/vector retrieval
  ↓
Reranking
  ↓
Relevant-span extraction
  ↓
Compact evidence object
  ↓
Small model
```

The evidence object should retain source identity and location:

```json
{
  "facts": [
    {
      "claim": "Renewal notice must be provided 90 days in advance.",
      "source": "vacation-policy.pdf",
      "section": "4.2",
      "confidence": 0.94
    }
  ]
}
```

The model should answer from the evidence object, not from unsupported memory.

### Retrieval rules

Use `retrieval_lookup` when the request contains a recognized entity, identifier, or direct lookup pattern. Use `small_rag` when the request requires a short answer grounded in local documents. Use a specialist route when multiple documents, conflicting evidence, or complex comparison is involved.

### Test gate

Create questions with known answers and source sections. Measure:

- Recall of the correct evidence
- Precision of retrieved evidence
- Answer accuracy
- Citation or source support
- Prompt tokens before and after compression
- CPU time for retrieval and reranking

The aim is not merely to retrieve fewer tokens. It is to retrieve **the right evidence with less model work**.

---

## 8. Introduce a model cascade

Once the analyzer and deterministic paths are measurable, add two or three model tiers:

```text
Tier 0: rules, cache, database, calculator
Tier 1: tiny or small general model
Tier 2: task-specific specialist model
Tier 3: deep fallback model
```

Use the smallest model that meets the task’s quality requirement.

| Condition | Initial route |
|---|---|
| Verified cache hit | `exact_cache` |
| Exact arithmetic or parser task | `deterministic` |
| Known entity lookup | `retrieval_lookup` |
| Rewrite, translation, short classification | `small_direct` |
| Simple grounded question | `small_rag` |
| Complex extraction, coding, comparison | `specialist` |
| Hard, ambiguous, or failed verification | `deep_fallback` |

Do not route solely from topic. A difficult question about a familiar topic may still need a deeper route, while a long but simple extraction may be handled by a specialist model.

### Cascade test

Compare three systems on the same benchmark:

1. One model for everything.
2. Rules plus one small model.
3. Rules plus cache, retrieval, and model cascade.

Report quality, latency, CPU time, RAM, model calls, and escalation rate. The cascade is successful only if it lowers resource use while preserving the agreed quality target.

---

## 9. Add verification and selective escalation

Generation should not be the final step for structured or grounded tasks. Add cheap checks first and reserve expensive verification for uncertain outputs.

### Verification layers

| Layer | Check |
|---|---|
| Syntax | Valid JSON, valid label, required fields |
| Type | Numbers, dates, IDs, and field types |
| Arithmetic | Totals, percentages, sums, date differences |
| Evidence | Claims supported by retrieved source spans |
| Consistency | No contradiction with known session state |
| Task-specific | Unit tests for code or field-level extraction checks |

### Escalate when

- Required output fails schema validation.
- Evidence is missing or contradictory.
- Important numbers do not reconcile.
- The model expresses low confidence on a high-precision task.
- The request is high-risk and the route is uncertain.
- A tool call fails.
- The answer is incomplete or cut off.

Escalate the smallest possible unit. For example, re-run a failed field extraction instead of regenerating an entire document response.

### Test gate

Measure the **false cheap-route rate**: the percentage of requests that were sent to an inexpensive route but should have been escalated. This is one of the most important metrics in the project.

---

## 10. Build the evaluation dataset and replay harness

Create a versioned JSONL benchmark. Each record should contain:

```json
{
  "id": "invoice-001",
  "input": "...",
  "task_type": "structured_extraction",
  "expected_route_family": "specialist",
  "expected_output": {
    "invoice_number": "A-1938"
  },
  "source_documents": ["invoice-001.pdf"],
  "risk_level": "low",
  "difficulty_band": "moderate"
}
```

Include normal, easy, hard, ambiguous, adversarial, and malformed examples. Do not evaluate only on cases that the rules were written from; hold out a test set.

The replay harness should:

1. Load a fixed benchmark.
2. Run the analyzer.
3. Execute the selected route.
4. Run verification.
5. Record all routing and resource metrics.
6. Compare output against expected results.
7. Produce a summary report by route and task type.

Keep benchmark versions immutable. When a rule changes, compare the new run with the previous version.

---

## 11. Implement the routing policy as data, not scattered code

Store thresholds and rule groups in configuration so that experiments are reversible.

```yaml
thresholds:
  cache_max_age_seconds: 3600
  easy_max_score: 0.35
  moderate_max_score: 0.70
  minimum_normal_confidence: 0.85
  minimum_escalation_confidence: 0.55

routes:
  small_direct:
    max_input_tokens: 4000
    max_output_tokens: 700
  small_rag:
    max_evidence_tokens: 2500
  specialist:
    max_input_tokens: 12000

features:
  retrieval_keywords:
    - according to
    - policy
    - contract
    - document
    - find
    - lookup
  coding_keywords:
    - code
    - function
    - api
    - sql
    - error
```

Every route decision should include a reason code, such as:

```text
RULE_DETERMINISTIC_CALCULATION
RULE_RETRIEVAL_ENTITY_LOOKUP
TASK_REWRITE_EASY
TASK_COMPARISON_MODERATE
ESCALATE_SCHEMA_FAILURE
ESCALATE_LOW_CONFIDENCE
```

Reason codes make errors debuggable and enable route-level analysis.

---

## 12. Suggested implementation order and exit criteria

| Phase | Build | Exit criterion |
|---|---|---|
| 0 | Choose workload and hardware | Written target and benchmark plan |
| 1 | Single-model baseline | Reproducible quality and resource numbers |
| 2 | Analyzer skeleton | Correct structured decisions on labeled cases |
| 3 | Deterministic handlers | Exact operations bypass the model safely |
| 4 | Cache and session state | Verified reuse with no stale-data failures |
| 5 | Retrieval pipeline | Grounded answers with measured evidence quality |
| 6 | Model cascade | Lower CPU cost at equal target quality |
| 7 | Verification and escalation | Cheap failures are caught reliably |
| 8 | Replay dashboard | Every experiment is comparable and auditable |
| 9 | Architecture experiments | New model ideas are tested against a real serving baseline |

Do not advance because the demo looks good. Advance because the exit criterion is met on a fixed benchmark.

---

## 13. Experiments to run after the prototype works

Only after the serving system is stable should you compare deeper architectural ideas.

### Experiment A: context compression

Compare full conversation context against a structured summary plus recent window. Measure answer quality, token count, latency, and memory.

### Experiment B: local attention window

Compare full attention against a recent-window strategy combined with retrieval for older context. Measure long-context accuracy and CPU time.

### Experiment C: recurrent state

Prototype a persistent task state that is updated between turns. Compare repeated full-prompt processing with stateful processing on multi-turn tasks.

### Experiment D: structured internal messages

Replace verbose internal text with compact intent, evidence, plan, and tool objects. Measure generated tokens and task success.

### Experiment E: conditional depth

Use a shallow path for easy examples and a deeper path for uncertain examples. Measure the quality-cost curve rather than average latency only.

### Experiment F: specialist distillation

Use outputs from a stronger teacher system to train or fine-tune a small task-specific model. Compare it with a general small model at the same CPU budget.

These experiments answer a more important question than “which architecture is newest?” They reveal which source of computation is actually unnecessary for your target workload.

---

## 14. Metrics that determine whether the idea is working

Use a dashboard with at least these metrics:

| Metric | Interpretation |
|---|---|
| Task success rate | Whether the system actually completed the task |
| CPU milliseconds per successful task | Primary efficiency measure |
| Peak RAM | Whether deployment is practical |
| Time to first result | User-perceived responsiveness |
| Average output tokens | Amount of language generation required |
| Retrieval tokens | Context compression effectiveness |
| Route distribution | Whether the analyzer is using cheap paths |
| Escalation rate | How often initial routing is insufficient |
| False cheap-route rate | Safety of aggressive optimization |
| Verification failure rate | Reliability of outputs |
| Cache hit rate | Value of reuse |
| Cost-quality frontier | Tradeoff between resources and success |

The most important composite metric is:

> **CPU milliseconds per successful, verified task.**

A system that generates quickly but often produces wrong answers is not efficient. It is merely failing cheaply.

---

## 15. Common mistakes to avoid

### Starting with a new foundation model

Training a new model before measuring serving waste makes it difficult to know whether an architectural change solved the real bottleneck. First establish where CPU time is going.

### Optimizing tokens per second alone

A fast model that requires long prompts, retries, and manual correction may be worse than a slower model with retrieval and deterministic validation.

### Using an LLM as the router for every request

A router that consumes a substantial fraction of the main model’s cost defeats the purpose. Begin with rules and a small classifier.

### Treating all sparsity as useful sparsity

Irregular sparse access can be slow on CPUs. Prefer block-structured, cache-friendly computation and measure actual wall-clock performance.

### Passing entire documents into prompts

Retrieve, rerank, extract relevant spans, and preserve source identifiers. More context is not automatically more intelligence.

### Adding too many routes too early

Start with a small route catalog. A complex router is hard to debug and may produce unmeasured overhead.

### Hiding route failures

Log every decision, reason code, fallback, and verification result. A routing system improves through error analysis, not intuition alone.

---

## 16. The first 30-day plan

### Week 1: measurement foundation

Choose the workload, machine, model, quantization, and benchmark. Build the single-model baseline and record repeatable measurements.

### Week 2: analyzer and deterministic paths

Implement normalization, hard-priority rules, task labels, difficulty bands, calculator/parser/database handlers, and unit tests for routing decisions.

### Week 3: reuse and retrieval

Add exact caching, session state, local document indexing, evidence extraction, and source-aware prompts. Compare full-context and compact-evidence approaches.

### Week 4: cascade and verification

Add a small model, specialist model, route thresholds, schema validation, evidence checks, fallback behavior, and a replay report comparing every version.

At the end of 30 days, you should have evidence for three decisions:

1. Which tasks are worth targeting commercially.
2. Which requests can be completed without a large model.
3. Which remaining bottleneck justifies new model architecture research.

---

## 17. The longer-term redesign target

If the prototype demonstrates meaningful savings, use its measurements to guide a CPU-native architecture. The likely target is not merely a smaller Transformer, but a stateful serving runtime with:

```text
compact recurrent task state
+ local recent-context processing
+ structured external memory
+ cache-friendly specialist modules
+ deterministic tools
+ adaptive compute budgets
+ verification and selective escalation
```

The prototype should become the laboratory in which each component can be replaced independently. You might replace the general small model with a recurrent model, the retriever with a structured memory system, or the cascade with conditional-depth execution. Because the serving contract remains stable, each experiment can be compared against the same benchmark.

## Final starting point

If you begin tomorrow, implement these five items in order:

1. **One benchmark and one baseline model.**
2. **A rule-based analyzer returning structured decisions.**
3. **A deterministic calculator/parser route.**
4. **A small-model route plus a specialist fallback.**
5. **A replay harness measuring verified task success per CPU millisecond.**

That sequence produces a working system quickly while preserving the ability to pursue the more radical idea: an LLM serving architecture in which tokens are only one interface, models are specialized compute modules, memory is managed explicitly, and computation expands only when the request requires it.

## References

[1]: https://github.com/ggerganov/llama.cpp "llama.cpp repository"

[2]: https://onnxruntime.ai/docs/execution-providers/ "ONNX Runtime execution providers documentation"

[3]: https://sqlite.org/fts5.html "SQLite FTS5 full-text search documentation"

[4]: https://www.sbert.net/ "Sentence Transformers documentation"
