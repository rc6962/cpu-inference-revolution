# CPU-Native Cognitive Serving: A Detailed Starting Blueprint

**Author:** Manus AI  
**Purpose:** Define a concrete starting architecture, implementation sequence, experiments, and decision gates for building an AI serving platform around CPU, DRAM, and NVMe strengths rather than around GPU-style dense Transformer inference.

## Executive position

The most promising starting point is not to train a new general-purpose language model immediately. It is to build a **CPU-native cognitive execution engine** that treats neural models as schedulable components within a larger system.

The system should combine:

```text
CPU orchestration
+ large inexpensive memory
+ NVMe-backed model and knowledge storage
+ compact neural specialists
+ structured working memory
+ retrieval
+ deterministic tools
+ adaptive execution plans
+ selective verification
```

The initial goal is not to prove that CPUs can replace GPUs for every workload. The goal is to prove a narrower and more valuable proposition:

> For selected real-world tasks, a CPU-centered system can deliver comparable verified task success at lower total cost, lower memory cost, and better privacy or deployment flexibility than a conventional single-model GPU-oriented server.

This distinction is important. A CPU-native architecture should win because it **does less unnecessary neural computation**, not because it performs the same dense computation at the same speed as a GPU.

---

## 1. Start with the right mental model

A conventional LLM server generally exposes this abstraction:

```text
prompt → model → generated tokens
```

A CPU-native cognitive server should expose a different abstraction:

```text
request + session state + constraints
    ↓
execution planner
    ↓
memory, retrieval, tools, and neural modules
    ↓
verified result
```

The result may be text, JSON, a classification, a database update proposal, a tool action, or a request for clarification. Text generation is one possible output, not the universal internal representation.

### The proposed system layers

```text
┌────────────────────────────────────────────────────────┐
│ Client API and session interface                        │
├────────────────────────────────────────────────────────┤
│ Request analyzer and risk/quality classifier             │
├────────────────────────────────────────────────────────┤
│ Execution planner and CPU-budget scheduler               │
├────────────────────────────────────────────────────────┤
│ Working memory and session-state manager                 │
├────────────────────────────────────────────────────────┤
│ Retrieval, indexing, cache, and NVMe object store        │
├────────────────────────────────────────────────────────┤
│ Compact neural modules and specialist models             │
├────────────────────────────────────────────────────────┤
│ Deterministic tools, databases, and external systems     │
├────────────────────────────────────────────────────────┤
│ Verification, telemetry, and evaluation                  │
└────────────────────────────────────────────────────────┘
```

This is closer to a database engine, operating system, and workflow runtime than to a simple model server.

---

## 2. Choose the first workload as a laboratory

Do not begin with general chat. Choose a workflow where:

- Inputs can be collected or simulated.
- Correctness can be checked.
- Retrieval or structured state is useful.
- Some work can be handled deterministically.
- The user benefits from privacy or local deployment.
- A CPU-only deployment is commercially plausible.

The recommended first target is **document-to-structured-result processing**, such as invoice extraction, purchase-order processing, support-ticket routing, or internal policy lookup.

### Preferred first target: invoice or form extraction

This target exposes nearly every important system capability:

```text
file input
→ parsing/OCR if needed
→ field detection
→ compact structured state
→ arithmetic validation
→ schema validation
→ confidence scoring
→ selective escalation
```

It avoids the ambiguity of open-ended chat while still requiring language understanding, document retrieval, memory, structured output, and verification.

### Example product statement

> A local CPU appliance that extracts, validates, and routes business documents without sending their contents to a cloud service.

### First success criteria

Set hard targets before implementation. For example:

| Category | Initial target |
|---|---:|
| Field-level accuracy | At least 97% on common fields |
| Valid output format | At least 99% valid structured outputs |
| Arithmetic consistency | At least 99.5% on checkable totals |
| Warm request latency | Under 3 seconds per document |
| Peak RAM | Under 8 GB for the selected workload |
| GPU requirement | None |
| Escalation rate | Under 20% after tuning |
| Verified successful task cost | Better than the single-model baseline |

The exact values can change. What matters is that the target is measurable and fixed before optimization.

---

## 3. Define the hardware hierarchy explicitly

The architecture should use each storage and memory tier for a different purpose. Do not treat RAM and NVMe as interchangeable, and do not use NVMe as if it were fast RAM.

### Proposed hierarchy

| Tier | Contents | Access pattern | Design purpose |
|---|---|---|---|
| CPU registers and cache | Hot routing state, small tensors, counters | Very frequent, sequential | Minimize latency |
| DRAM | Active models, working memory, indexes, session state | Frequent, bounded | Main serving workspace |
| Memory-mapped NVMe | Cold model modules, document corpus, large indexes | Selective, prefetched | Increase capacity without large RAM |
| Local object store | Original files, historical traces, model versions | Infrequent | Durable storage |

### Important constraint

NVMe can increase capacity and simplify model swapping, but it cannot fully compensate for insufficient DRAM during token-by-token computation. The system should therefore avoid paging active computation unpredictably. NVMe should hold **cold modules and data**, while active working sets should be promoted into memory deliberately.

### Model residency policy

Each module should have a residency class:

```text
HOT:      always resident in DRAM
WARM:     resident when recent demand justifies it
COLD:     stored on NVMe and loaded on demand
REMOTE:   optional external fallback
```

For example:

```text
HOT:  request analyzer, tokenizer, verifier, common small model
WARM: retrieval reranker, extraction specialist
COLD: rare language model, deep fallback, domain-specific expert
REMOTE: optional high-capability escalation endpoint
```

The scheduler should use recent demand and predicted request type to prefetch WARM modules before they are needed.

---

## 4. Build the first architecture as a modular runtime

The first implementation should contain six core subsystems.

### 4.1 Request analyzer

The analyzer converts raw input into a structured request description:

```json
{
  "task_type": "structured_extraction",
  "domain": "invoice",
  "risk_level": "low",
  "difficulty_band": "moderate",
  "requires_retrieval": false,
  "requires_tools": true,
  "output_format": "strict_json",
  "latency_budget_ms": 3000,
  "memory_budget_mb": 4096,
  "recommended_route": "extraction_specialist",
  "confidence": 0.93
}
```

Initially, implement this with deterministic features and simple scoring. Do not place a large model in front of every request.

### 4.2 Execution planner

The planner converts the analysis into an execution graph:

```json
{
  "steps": [
    {"id": "parse", "module": "document_parser"},
    {"id": "extract", "module": "invoice_extractor", "depends_on": ["parse"]},
    {"id": "check", "module": "arithmetic_validator", "depends_on": ["extract"]},
    {"id": "verify", "module": "schema_verifier", "depends_on": ["check"]}
  ],
  "estimated_cpu_ms": 840,
  "estimated_ram_mb": 2400,
  "fallback": "deep_extractor"
}
```

The planner should support conditional edges:

```text
if extraction_confidence < 0.80 → invoke specialist retry
if arithmetic check fails → re-extract numeric fields
if source ambiguity remains → escalate or request clarification
```

### 4.3 Working-memory manager

The working-memory manager stores the small amount of state needed for the current task. It should distinguish:

```text
session state       → persistent conversation/task information
working memory      → facts needed for the current operation
retrieval evidence  → source-backed information
execution state     → completed steps and tool outputs
```

Use structured records wherever possible. A conversation summary should not be the only representation of a session.

### 4.4 Module scheduler

The scheduler decides which modules run, where they run, and whether they should be loaded or prefetched.

It should consider:

- CPU budget
- RAM budget
- Module residency
- Estimated execution time
- NUMA locality if applicable
- Dependencies between steps
- Request priority
- Historical route performance

The scheduler should be able to run independent operations concurrently, such as document retrieval and metadata lookup, while keeping the critical path small.

### 4.5 Tool and data adapters

Tools should expose typed interfaces rather than natural-language-only interfaces:

```python
class Calculator:
    def evaluate(self, expression: str) -> Decimal: ...

class DocumentIndex:
    def search(self, query: str, limit: int = 10) -> list[Evidence]: ...

class Database:
    def lookup(self, entity_type: str, entity_id: str, fields: list[str]) -> dict: ...
```

Typed interfaces reduce token use, simplify validation, and make execution observable.

### 4.6 Verification and telemetry

Every output should pass through the cheapest applicable checks. The verifier should return structured findings:

```json
{
  "passed": false,
  "errors": [
    {"type": "arithmetic_mismatch", "field": "total", "expected": 119.80, "actual": 129.80}
  ],
  "confidence": 0.61,
  "recommended_action": "retry_numeric_extraction"
}
```

---

## 5. Implement in this exact order

### Phase 0: freeze the research question

Write down the target workload, hardware, model, benchmark, and metrics. Create a short design document containing:

- The task definition.
- What counts as a successful result.
- What the baseline system is.
- What CPU machine is being used.
- What data may be cached.
- What privacy assumptions apply.
- What failure modes are unacceptable.

**Exit criterion:** another person can reproduce the intended experiment from the document.

### Phase 1: build a single-model baseline

Use one existing quantized model through a replaceable backend. Send every case through the same prompt and model. Build the replay harness before adding optimization.

**Required output:** a table showing quality, CPU time, RAM, latency, and failure types for every benchmark case.

**Exit criterion:** baseline metrics are repeatable across multiple runs.

### Phase 2: add the analyzer without changing execution

Implement the analyzer, but initially log its proposed route while still sending requests through the baseline model. This is called shadow mode.

Shadow mode is essential because it lets you measure routing accuracy before allowing routing errors to affect users.

The analyzer should emit:

```text
predicted task
predicted difficulty
retrieval requirement
tool requirement
risk level
route recommendation
confidence
reason codes
```

**Exit criterion:** the analyzer reaches an agreed classification accuracy on a held-out labeled set and produces useful reason codes for errors.

### Phase 3: add deterministic execution

Activate only low-risk, high-confidence deterministic handlers:

- Arithmetic and unit conversion.
- Known identifier lookups.
- Strict parsers.
- Field and schema validation.
- Sorting, filtering, and deduplication.

Keep an override flag that forces a request through the baseline model for comparison.

**Exit criterion:** deterministic handlers are exact on supported cases, and false captures are rare enough not to damage normal requests.

### Phase 4: add cache and session state

Implement verified response caching, prompt-prefix reuse, document-version tracking, and structured session state. Use versioned cache keys:

```text
hash(normalized_request,
     user_permissions,
     document_versions,
     system_policy_version,
     model_version)
```

**Exit criterion:** measurable latency reduction with no stale-data or permission leakage in cache tests.

### Phase 5: add retrieval and evidence compression

Build a local index over the selected document set. Start with keyword search because it is easy to inspect, then add vector retrieval or embeddings if the benchmark demonstrates a need.

Compress retrieved material into source-linked evidence objects rather than passing entire documents into the prompt.

**Exit criterion:** retrieval improves or preserves answer quality while reducing model context and maintaining source traceability.

### Phase 6: add a model cascade

Introduce a small model and one specialist model. The initial cascade should be simple:

```text
rules/cache/tools
    ↓ if not resolved
small general model
    ↓ if difficult, uncertain, or task-specific
specialist model
    ↓ if still failed
fallback model or clarification
```

Keep routing thresholds in configuration. Every escalation must record its reason.

**Exit criterion:** the cascade reduces CPU milliseconds per verified task without reducing the target success rate.

### Phase 7: add verification and selective retry

Use field-level or step-level retry. If only one field is invalid, do not regenerate the whole answer. If a total fails arithmetic validation, reprocess numeric fields rather than rerunning unrelated text extraction.

**Exit criterion:** verification catches the majority of cheap-route failures and selective retries cost less than full regeneration.

### Phase 8: add residency and NVMe-aware scheduling

Only after route behavior is stable should you add model residency policies and NVMe-backed module loading.

Implement:

- Hot/warm/cold module classes.
- Memory-mapped model files where appropriate.
- Explicit prefetching.
- Load-time telemetry.
- Eviction based on demand.
- Separate model loading from request analysis.

**Exit criterion:** cold-module loading does not create unacceptable tail latency, and memory usage remains within the target envelope.

### Phase 9: run architecture experiments

Now replace one subsystem at a time with a more radical design: recurrent state, compact memory, sparse experts, structured internal messages, or conditional depth.

**Exit criterion:** each new architecture is compared against the stable serving baseline on the same benchmark and hardware.

---

## 6. The first execution policy

Use a conservative initial policy:

```python
def plan(request):
    analysis = analyze(request)

    if analysis.security_restricted:
        return clarify_or_reject("restricted_request")

    if verified_cache_hit(request):
        return ["exact_cache"]

    if analysis.deterministic_operation and analysis.confidence >= 0.95:
        return [analysis.deterministic_handler]

    if analysis.entity_lookup and analysis.confidence >= 0.90:
        return ["local_lookup", "response_renderer"]

    if analysis.task_type in {"rewrite", "translation", "short_classification"} \
       and analysis.difficulty_band == "easy":
        return ["small_direct", "light_verifier"]

    if analysis.requires_retrieval and analysis.difficulty_band != "hard":
        return ["retrieve", "compress_evidence", "small_rag", "evidence_verifier"]

    if analysis.task_type in {"extraction", "coding", "comparison"} \
       or analysis.difficulty_band == "hard":
        return ["specialist", "task_verifier"]

    return ["small_direct", "quality_check", "fallback_if_needed"]
```

Keep this policy intentionally boring. The first objective is to create a reliable experimental platform, not to produce a clever but opaque router.

---

## 7. Design the internal data contracts early

The system will be difficult to evolve if modules communicate only through strings. Define typed contracts from the beginning.

### Request contract

```json
{
  "request_id": "req-001",
  "session_id": "sess-001",
  "input": {"text": "...", "attachments": []},
  "constraints": {
    "latency_budget_ms": 1500,
    "memory_budget_mb": 4096,
    "quality_target": 0.95
  },
  "permissions": ["documents:read"]
}
```

### Evidence contract

```json
{
  "evidence_id": "ev-001",
  "source_id": "policy.pdf",
  "location": "section 4.2",
  "text": "...",
  "facts": [{"key": "notice_days", "value": 90}],
  "retrieval_score": 0.91
}
```

### Module result contract

```json
{
  "module": "invoice_extractor",
  "status": "success",
  "output": {"vendor": "Example Co", "total": 119.80},
  "confidence": 0.88,
  "cpu_ms": 412,
  "ram_mb_peak": 1280,
  "warnings": []
}
```

### Failure contract

```json
{
  "status": "needs_escalation",
  "reason": "schema_validation_failed",
  "retry_scope": ["total", "tax"],
  "fallback_module": "deep_extractor"
}
```

These contracts allow you to replace the model backend without replacing the entire serving system.

---

## 8. How to use DRAM and NVMe intelligently

The storage strategy should be a first-class part of the design, but it should serve the execution plan rather than become a gimmick.

### DRAM should hold

- The analyzer.
- Tokenizers and small common modules.
- Active working memory.
- Frequently used indexes.
- Hot model weights.
- Session state for active requests.
- Verification code and intermediate structured results.

### NVMe should hold

- Cold specialist models.
- Original document collections.
- Large embedding and keyword indexes.
- Historical session summaries.
- Model versions and experiment artifacts.
- Prefetched evidence blocks.
- Checkpoints and replay data.

### Useful NVMe experiments

1. Compare loading an entire specialist model into DRAM with memory-mapped access.
2. Measure cold-start latency separately from warm-request latency.
3. Test whether prefetching based on analyzer predictions reduces tail latency.
4. Evaluate storing model modules separately so only selected experts are loaded.
5. Measure the effect of local NVMe retrieval versus remote object storage.

### What not to do

Do not claim that NVMe makes arbitrary large-model inference equivalent to RAM-resident inference. The useful opportunity is to use NVMe for **capacity, persistence, model modularity, and data locality**, while protecting the active working set in DRAM.

---

## 9. The core experiments that could justify a new architecture

Each experiment should answer one specific question.

### Experiment 1: How much work can be avoided?

Compare:

```text
single model for all requests
versus
rules + cache + tools + small model + fallback
```

Measure the percentage of requests resolved without the specialist or fallback model.

### Experiment 2: Does structured working memory beat long prompts?

Compare full conversation/document context with:

```text
recent window + structured state + source-linked evidence
```

Measure accuracy, context tokens, CPU time, and memory.

### Experiment 3: Does persistence beat repeated prefill?

Use multi-turn sessions. Compare reprocessing the full history with updating a persistent task state.

Measure cumulative CPU cost across 10, 25, and 100 turns.

### Experiment 4: Does conditional depth improve the quality-cost curve?

Use a shallow path for easy cases and deeper computation for uncertain cases. Plot task success against CPU time.

### Experiment 5: Does structured internal communication reduce generation?

Replace verbose natural-language plans with typed intent, evidence, and tool objects. Measure generated tokens, errors, and total latency.

### Experiment 6: Do CPU-friendly sparse modules outperform dense small models?

Compare dense and block-structured specialist modules at equal parameter count and equal quality target. Measure actual wall-clock time, not theoretical FLOPs.

### Experiment 7: Can NVMe-backed modularity improve total cost?

Compare a large always-resident model with several cold/warm specialist modules. Include load latency, memory savings, request distribution, and tail latency.

### Experiment 8: Can a recurrent core replace repeated attention?

After the serving contracts are stable, test a recurrent or state-space component for session state. Do not evaluate it only on perplexity. Evaluate it on multi-turn task success and resource use.

---

## 10. Testing strategy

Testing must cover both software correctness and AI behavior.

### Unit tests

Test:

- Feature extraction.
- Rule priority.
- Cache key construction.
- Permission-sensitive cache behavior.
- Numeric calculations.
- Schema validation.
- Evidence object creation.
- Route selection.
- Fallback selection.
- Module residency transitions.

### Analyzer test set

Create labeled examples for every task class, including ambiguous and adversarial examples. The test set should include cases where the cheapest route is wrong.

### Route replay tests

Replay a fixed benchmark and record:

```text
selected route
alternative routes
route confidence
CPU time
RAM
latency
output correctness
verification outcome
escalation reason
```

### Fault-injection tests

Deliberately simulate:

- Missing model module.
- Corrupt cache entry.
- Stale document index.
- Retrieval failure.
- Malformed JSON.
- Arithmetic mismatch.
- Tool timeout.
- Insufficient memory.
- NVMe load delay.

The system should fail into a known state rather than silently returning an unverified result.

### Load tests

Test both single-request latency and mixed workloads. CPUs may perform well for individual requests but poorly under uncontrolled concurrency.

Use workload mixes such as:

```text
60% easy direct tasks
20% retrieval tasks
10% structured extraction
5% coding or comparison
5% fallback cases
```

Vary concurrency, model residency, and memory pressure.

### Quality tests

Use task-specific evaluators whenever possible:

- Exact match for fields and labels.
- Arithmetic checks for numeric outputs.
- Unit tests for generated code.
- Evidence support checks for grounded answers.
- Human review only for cases that cannot be evaluated deterministically.

---

## 11. Metrics and decision gates

The project needs explicit gates to prevent attractive demos from masking poor economics.

### Gate A: baseline reproducibility

Pass when repeated runs have stable performance within an agreed tolerance and output quality is measured on a fixed dataset.

### Gate B: routing value

Pass when routing reduces average CPU milliseconds per successful task without reducing the target success rate.

### Gate C: state and retrieval value

Pass when structured state or evidence compression reduces context processing while preserving grounded correctness.

### Gate D: modular memory value

Pass when hot/warm/cold residency reduces DRAM requirements without unacceptable tail latency.

### Gate E: architecture value

Pass when a new recurrent, sparse, or hybrid component beats the stable baseline on the target workload under the same hardware and quality constraints.

### Required dashboard

| Metric | Required interpretation |
|---|---|
| Verified task success | Primary quality outcome |
| CPU ms per successful task | Primary efficiency outcome |
| Peak DRAM | Active working-set requirement |
| NVMe read bytes | Cost of cold or remote state |
| p50/p95/p99 latency | Tail behavior under realistic load |
| Route distribution | Whether cheap paths are used |
| Escalation rate | How often confidence is insufficient |
| False cheap-route rate | Risk of underpowered routing |
| Model residency hit rate | Effectiveness of hot/warm/cold policy |
| Generated tokens | Amount of avoidable language work |
| Tool and retrieval latency | Non-model bottlenecks |

The main business metric remains:

> **Cost and energy per verified successful task.**

---

## 12. What the first team should build

A small team should divide work into four tracks.

### Track 1: runtime and APIs

Build the request contract, planner, scheduler, module interface, session store, and telemetry.

### Track 2: routing and evaluation

Build the analyzer, benchmark dataset, shadow mode, replay harness, and route reports.

### Track 3: memory and data

Build the document index, structured working memory, cache, evidence objects, and NVMe residency layer.

### Track 4: model experiments

Integrate quantized baseline models, small specialists, verification models, and eventually recurrent or sparse alternatives.

Do not let model research proceed without the benchmark and runtime instrumentation. Otherwise, you will not know whether a model improvement came from the model, the prompt, retrieval, or a hidden infrastructure difference.

---

## 13. What not to build first

Avoid these until the core experiment is working:

- A general-purpose 100-billion-parameter CPU model.
- A custom compiler before the execution graph is understood.
- A distributed cluster scheduler.
- An elaborate agent framework.
- A new tokenizer without a target workload.
- A fully unstructured sparse architecture.
- A giant vector database.
- A broad public chatbot product.
- A custom operating system or storage stack.

The first product should be a **narrow, measurable CPU appliance or local service**, not a universal replacement for every GPU host.

---

## 14. The first 90 days

### Days 1–14: baseline and benchmark

Select the workload, acquire representative data, define correctness, choose the CPU machine, integrate one quantized model, and create the replay harness.

Deliverable: baseline report with quality, latency, CPU, RAM, and failure categories.

### Days 15–30: analyzer and deterministic paths

Implement normalization, rules, task labels, difficulty bands, calculator/parser handlers, and shadow-mode route logging.

Deliverable: analyzer confusion matrix and deterministic-handler accuracy report.

### Days 31–45: state, cache, and retrieval

Implement session state, verified cache keys, document versions, local indexing, retrieval, reranking, and compact evidence objects.

Deliverable: comparison of full-context versus compact-evidence processing.

### Days 46–60: model cascade and verification

Add a small model, specialist model, route thresholds, schema validation, evidence checks, selective retry, and fallback behavior.

Deliverable: cost-quality comparison of single-model and cascaded serving.

### Days 61–75: memory hierarchy and NVMe

Add hot/warm/cold model residency, module prefetching, memory pressure tests, and cold-start measurement.

Deliverable: DRAM-versus-NVMe residency report with p95 and p99 latency.

### Days 76–90: architecture research decision

Use the measured bottlenecks to choose one deeper experiment:

- recurrent session state,
- structured internal messages,
- conditional depth,
- block-sparse specialists,
- compact evidence model, or
- CPU-specific quantization and kernels.

Deliverable: a go/no-go decision backed by benchmark data.

---

## 15. The first radical model to investigate

If the serving prototype demonstrates that repeated context processing is a major cost, the first new model experiment should be a **stateful hybrid model**, not a complete replacement for every component.

A practical design would be:

```text
input encoder
    ↓
fast recurrent state update
    ↓
small recent-window attention
    ↓
structured working-memory read/write
    ↓
conditional specialist invocation
    ↓
compact output state or final renderer
```

The model should maintain separate state for:

- Local linguistic continuity.
- Current task and plan.
- Retrieved facts and evidence references.
- User/session information.
- Confidence and unresolved questions.

Attention would be used locally or selectively, while distant information would be accessed through structured memory and retrieval.

The first model need not be a general chat model. It could be trained for a constrained interface:

```text
request → intent/state update → evidence query → structured decision
```

That is easier to train, easier to verify, and more aligned with CPU-native serving.

---

## 16. The commercial wedge

The business should initially sell a measurable deployment outcome, not an abstract architecture.

Potential positioning:

> Private, CPU-native AI for document and workflow automation that runs on existing enterprise hardware and keeps sensitive data local.

The strongest early customers are likely to value:

- Data residency.
- Air-gapped operation.
- Predictable infrastructure cost.
- Use of existing CPU fleets.
- Low or no GPU dependency.
- Integration with internal documents and systems.
- Auditable decisions and evidence.

The product moat could eventually include:

1. A CPU-native execution runtime.
2. A library of compact specialist modules.
3. Hardware-aware model residency and scheduling.
4. Structured memory and evidence protocols.
5. Task-specific benchmarks proving lower total cost.
6. A growing workload and telemetry dataset for routing improvement.

The most defensible claim is not “we are faster than GPUs.” It is:

> For these workloads, we complete more verified business tasks per dollar and per watt while preserving privacy and using ordinary CPU infrastructure.

---

## Final recommendation

Start with a narrow document workflow and build the runtime around it. The order should be:

```text
benchmark
→ single-model baseline
→ request analyzer
→ deterministic handlers
→ cache and session state
→ retrieval and evidence compression
→ model cascade
→ verification and selective retry
→ hot/warm/cold model residency
→ recurrent or sparse architecture experiment
```

This sequence protects the project from its largest risk: spending years inventing a new model without knowing which computation the application actually needs.

The deeper opportunity is real. CPUs offer large memory capacity, branching, low-latency control, storage integration, and flexible scheduling. NVMe adds durable local capacity and enables modular model and knowledge storage. But those strengths become commercially meaningful only when the serving architecture is redesigned to use them deliberately.

The first objective is therefore not to create a faster Llama server. It is to prove a new execution model:

> **AI requests should be planned, routed, remembered, retrieved, computed, verified, and rendered—not simply pushed through one dense model until it emits text.**

## References

[1]: https://github.com/ggerganov/llama.cpp "llama.cpp repository"

[2]: https://onnxruntime.ai/docs/execution-providers/ "ONNX Runtime execution providers documentation"

[3]: https://sqlite.org/fts5.html "SQLite FTS5 full-text search documentation"

[4]: https://www.sbert.net/ "Sentence Transformers documentation"


---

# Addendum: Starting Models and Host Software

## 17. Model strategy: use a ladder, not a single candidate

The project should use three different model categories:

1. **Baseline models** to establish a fair comparison with conventional serving.
2. **Architectural candidates** whose internal computation is more compatible with persistent state or sequential CPU execution.
3. **Purpose-built modules** trained for the new serving runtime rather than for unrestricted chat.

Do not select a model merely because it has fewer parameters. The relevant measurements are active memory, bytes moved per successful task, cold-start cost, warm latency, quality at the target workload, and how easily the model can expose or consume structured state.

## 18. Recommended model starting points

### 18.1 Baseline: a small quantized Transformer

Begin with one strong, widely supported small instruction model in the approximate 1–4 billion parameter range. The exact model should be selected based on licensing, language needs, quality, and CPU runtime support at the time of implementation.

Use it only as a **control group**. Its purpose is to answer:

> How much better is the proposed serving architecture than ordinary CPU inference with a conventional small model?

The baseline should have:

- A permissive commercial license suitable for the intended product.
- A reliable quantized format.
- CPU support through at least one mature runtime.
- Adequate structured-output behavior.
- A tokenizer that handles the target workload well.
- A model size that fits comfortably in the selected DRAM budget.

A practical baseline family could include a current small Llama-, Qwen-, Gemma-, or Phi-class model, but the model name should be pinned by benchmark results rather than brand preference. Re-evaluate available releases when the project begins because small-model quality and licensing change quickly.

### 18.2 Sequential architecture candidate: Mamba-family models

Mamba-style state-space models are worth testing because they provide a persistent sequential state and do not require ordinary full attention over the entire history. They are a natural candidate for long-running sessions and streaming workloads.

Use them first for:

- Session-state experiments.
- Long sequential document processing.
- Streaming classification.
- Compact memory updates.
- Comparisons against repeated Transformer prefill.

Do not assume that lower asymptotic complexity automatically means faster CPU execution. Measure actual wall-clock time, memory traffic, and quality. The implementation must be CPU-optimized; otherwise the theoretical advantage may be hidden by poor kernels or conversion overhead.

### 18.3 Sequential architecture candidate: RWKV-family models

RWKV-style models are worth evaluating because they combine recurrent-style inference with language-model behavior and can be viewed as a bridge between recurrent networks and Transformer-like training.

They are especially relevant for testing:

- Constant-size or bounded-size recurrent state.
- Stateful multi-turn sessions.
- Streaming generation.
- Reduced repeated-context processing.

The most important experiment is not a generic language benchmark. It is whether a persistent RWKV-style state can preserve task-relevant information across 10, 25, or 100 turns while reducing cumulative CPU work.

### 18.4 Sequential architecture candidate: RetNet-family models

RetNet-style retention mechanisms are useful as a candidate for a hybrid model because they offer recurrent and parallel interpretations of sequence processing. They may support efficient training while allowing a recurrent-style serving path.

Test them for:

- Persistent document-state accumulation.
- Streaming summarization.
- Recent-context plus retained-state serving.
- Hybrid parallel-prefill and recurrent-decode execution.

Treat RetNet as an architectural experiment rather than a production dependency at the outset. The project should not depend on one research implementation remaining maintained.

### 18.5 Sequential architecture candidate: xLSTM-family models

xLSTM-style architectures are worth investigating for compact persistent memory. Their relevance is not simply that they are recurrent; it is that they explicitly revisit memory mechanisms and gating for long sequences.

They may be useful for:

- Task-state tracking.
- Multi-turn workflow control.
- Compact summaries with controlled memory writes.
- Small planning or routing modules.

A promising role is not necessarily the final language generator. An xLSTM-like module could become the **task-state controller** sitting beside a separate language model.

### 18.6 Hybrid architecture candidate: local attention plus recurrent state

This is the model family I would prioritize for a ground-up prototype. It combines:

```text
persistent recurrent state
+ small recent-token attention window
+ structured memory read/write
+ optional specialist calls
```

The recurrent state handles continuity and long-range task state. Local attention handles exact recent references and syntax. Retrieval handles distant factual information. This avoids forcing one mechanism to perform every function.

A conceptual block is:

```text
new input
   ↓
small encoder
   ↓
recurrent task state update
   ↓
local attention over recent window
   ↓
structured memory read/write
   ↓
router decides whether to invoke a specialist
   ↓
compact action/state output or language renderer
```

This is a better starting point than attempting to replace every Transformer layer immediately because each part can be measured independently.

### 18.7 Small specialist models

The runtime should contain task-specific models rather than relying on one universal model. Start with compact specialists for:

| Specialist | Output |
|---|---|
| Intent classifier | Task type, domain, difficulty, risk features |
| Evidence selector | Relevant spans or source IDs |
| Structured extractor | Typed fields and confidence scores |
| Planner | Typed execution graph |
| Verifier | Validation findings and escalation decision |
| Response renderer | Short natural-language answer |
| Code classifier | Language, operation, risk, required tools |

These modules can initially be conventional small models. Over time, some can become recurrent or state-space models. The most valuable new model may be the **state and routing model**, not the final text generator.

## 19. What to train first

Do not begin by pretraining a general language model from raw internet data. The initial training sequence should be:

### Step 1: train or fine-tune a request analyzer

Inputs are user requests and session metadata. Outputs are:

```text
task type
retrieval requirement
tool requirement
difficulty band
risk flags
output format
```

Training data can be labeled examples from the target workload, with synthetic variations reviewed by humans.

### Step 2: train an evidence compressor

Input: retrieved document spans.  
Output: source-linked facts, entities, dates, numbers, and uncertainty.

This reduces context and gives the serving system a structured memory interface.

### Step 3: train a structured specialist

Input: a document or task object.  
Output: typed JSON with confidence and evidence references.

Use deterministic validators during training and evaluation. For example, invoice totals should reconcile, dates should parse, and required fields should be present.

### Step 4: distill a response renderer

The final response renderer only needs to turn verified internal results into clear language. It should not be responsible for retrieving facts or performing calculations.

### Step 5: train a persistent task-state model

Only after the runtime has accumulated real session traces should you train the recurrent or state-space controller. Its training target should be useful state transitions, not merely next-token prediction.

A training record might look like:

```json
{
  "previous_state": {
    "task": "invoice_review",
    "known_fields": ["vendor", "subtotal"]
  },
  "new_input": "The tax is shown on page two.",
  "evidence": ["page_2_span_14"],
  "next_state": {
    "task": "invoice_review",
    "known_fields": ["vendor", "subtotal", "tax"]
  },
  "required_action": "recompute_total"
}
```

This is much more aligned with the intended serving architecture than training a model to emit a long chain of hidden prose.

## 20. Suggested host software stack

The host should be designed as a modular local runtime. Avoid tying the architecture to a single existing LLM server.

### 20.1 Core implementation language

Use **Rust** for the long-term host runtime if the team has the capability. Rust is suitable for:

- Explicit memory ownership.
- Low-overhead concurrency.
- Typed module contracts.
- Safe FFI to native inference kernels.
- Predictable background loading and eviction.
- High-performance I/O.

Use Python for:

- Benchmarking.
- Dataset preparation.
- Model experiments.
- Evaluation notebooks.
- Rapid analyzer prototyping.

A pragmatic sequence is Python first for the control plane, then Rust for the hot runtime and scheduler once profiling identifies the bottlenecks.

### 20.2 API layer

Expose a local HTTP and streaming API, but make the internal interface a typed job protocol.

```text
HTTP/JSON or gRPC client
        ↓
request gateway
        ↓
typed internal request
        ↓
execution graph
```

The external API can resemble common chat APIs for compatibility, but internally the request should include:

```json
{
  "request_id": "req-001",
  "session_id": "sess-001",
  "input": {"text": "...", "attachments": []},
  "constraints": {
    "latency_budget_ms": 1500,
    "memory_budget_mb": 4096,
    "quality_target": 0.95
  },
  "permissions": ["documents:read"]
}
```

### 20.3 Execution engine

Implement a small directed-acyclic-graph executor with conditional edges. Each node should declare:

```text
inputs
outputs
estimated CPU time
estimated memory
required modules
failure behavior
retry scope
```

The executor should support:

- Sequential dependencies.
- Parallel independent steps.
- Conditional branching.
- Deadlines.
- Cancellation.
- Per-step telemetry.
- Selective retry.
- Resource budgets.

This execution engine is the most important software component because it is the part that ordinary single-model serving does not provide.

### 20.4 Model adapter layer

Create one adapter interface for every neural module:

```rust
trait NeuralModule {
    fn metadata(&self) -> ModuleMetadata;
    fn estimate(&self, input: &ModuleInput) -> ResourceEstimate;
    fn load(&mut self, residency: ResidencyClass) -> Result<()>;
    fn run(&self, input: ModuleInput) -> Result<ModuleOutput>;
    fn unload(&mut self) -> Result<()>;
}
```

The adapter should hide whether the underlying module uses:

- A conventional Transformer runtime.
- ONNX Runtime.
- A custom C/C++ kernel.
- A Rust implementation.
- A recurrent model.
- A deterministic algorithm.

This allows the serving architecture to remain stable while model implementations change.

### 20.5 Initial inference backends

Use existing mature backends as controls and compatibility layers, not as the definition of the new architecture.

Recommended roles:

| Backend category | Use |
|---|---|
| llama.cpp-compatible backend | Conventional quantized baseline and fallback |
| ONNX Runtime or similar | Portable specialist modules and classifiers |
| Custom native kernels | Experiments where profiling shows a real bottleneck |
| Direct framework runtime | Research and training validation |

The initial system can wrap a conventional backend, but the planner, memory manager, session state, and execution graph should be independent of it.

### 20.6 Local retrieval and structured data

Use a two-stage local retrieval design:

```text
keyword index → candidate evidence
vector or learned reranker → final evidence
```

A practical initial stack is:

- SQLite with FTS5 for simple local full-text search and metadata.
- A vector index only when keyword retrieval is insufficient.
- Memory-mapped files for large read-mostly indexes.
- A typed evidence store containing source IDs, spans, timestamps, and version hashes.

Do not begin with a distributed vector database. The first target is a single CPU host, and inspectability matters more than scale.

### 20.7 State and cache storage

Use separate stores for separate semantics:

| Store | Contents |
|---|---|
| In-memory cache | Hot route results and active state |
| Embedded key-value store | Session state and durable metadata |
| SQLite | Relational metadata, permissions, benchmark records |
| NVMe object directory | Documents, model modules, traces, checkpoints |
| Append-only event log | Execution steps and telemetry |

Keep cache keys tied to permissions, model versions, policy versions, and document versions. This prevents a fast cache from becoming a correctness or security problem.

### 20.8 Telemetry

Use a lightweight metrics format first. Every execution should produce a trace like:

```json
{
  "request_id": "req-001",
  "route": "invoice_extraction",
  "steps": [
    {"module": "parser", "cpu_ms": 18, "ram_mb": 40},
    {"module": "extractor", "cpu_ms": 412, "ram_mb": 1280},
    {"module": "validator", "cpu_ms": 3, "ram_mb": 12}
  ],
  "nvme_read_bytes": 0,
  "output_valid": true,
  "escalated": false
}
```

Track p50, p95, and p99 latency. Average latency alone will hide cold-module and memory-pressure failures.

## 21. Proposed repository structure for the host

```text
cpu-cognitive-runtime/
├── crates/
│   ├── api/                 # HTTP and streaming interface
│   ├── protocol/            # Typed request, evidence, and result contracts
│   ├── analyzer/            # Rules and lightweight classifiers
│   ├── planner/             # Execution graph construction
│   ├── scheduler/           # CPU, memory, and module scheduling
│   ├── residency/           # DRAM/NVMe hot-warm-cold policy
│   ├── session/             # Persistent session and task state
│   ├── retrieval/           # Search, reranking, evidence compression
│   ├── tools/               # Calculator, database, parsers, sandbox
│   ├── modules/             # Model adapter interfaces
│   ├── verifier/            # Schema, evidence, and task checks
│   └── telemetry/           # Traces and resource metrics
├── models/
│   ├── manifests/
│   ├── hot/
│   ├── warm/
│   └── cold/
├── python/
│   ├── benchmarks/
│   ├── training/
│   └── evaluation/
├── data/
├── configs/
├── tests/
└── reports/
```

## 22. Module manifest design

Every model or algorithmic module should have a manifest:

```yaml
name: invoice_extractor_v1
kind: neural
backend: onnx
artifact: models/invoice_extractor_v1.onnx
residency: warm
input_schema: invoice_text_v2
output_schema: invoice_fields_v1
estimated:
  ram_mb: 1400
  cold_load_ms: 850
  warm_cpu_ms: 420
capabilities:
  - structured_extraction
  - confidence_scores
license: specified-in-project-record
fallback: invoice_extractor_deep_v1
```

The planner should select modules through manifests rather than hard-coded model names. This is how the platform can evolve from conventional models to recurrent, sparse, or custom CPU-native modules.

## 23. Where NVMe creates a genuine advantage

The best NVMe use cases are modularity and locality, not pretending that storage is equivalent to VRAM.

### Model library on NVMe

Store many domain specialists on local NVMe and keep only popular modules in DRAM. The analyzer can predict which module is needed and prefetch it before execution.

### Evidence and document locality

Keep the document corpus, indexes, and source spans on the same host. This avoids network retrieval latency and supports private deployments.

### Persistent execution state

Store session checkpoints and resumable task graphs on NVMe so long-running workflows survive process restarts.

### Training and experiment traces

Keep detailed route traces and benchmark artifacts locally. These traces become the data used to improve routing and train future state models.

### Cold-start-aware routing

The planner should include load cost in route selection. A specialist that is more accurate but requires a 2-second cold load may be inferior to a warm small model for a low-latency request.

## 24. First software milestone

The first working milestone should not contain a new neural architecture. It should demonstrate the new host abstraction:

```text
request
  ↓
analyzer
  ↓
execution graph
  ├── cache
  ├── calculator/parser
  ├── local retrieval
  ├── small conventional model
  ├── specialist model
  └── verifier
```

Use a conventional quantized model behind the adapter interface. The innovation at this stage is that the runtime decides whether the model should be used at all, which model should be used, what evidence it receives, what state is reused, and how the result is verified.

## 25. First model-research milestone

After the host reaches stable benchmark performance, implement a research module with this narrow interface:

```text
Input:
  previous_task_state
  new_user_input
  retrieved_evidence
  execution_constraints

Output:
  updated_task_state
  requested_memory_reads
  requested_tools
  confidence
  response_plan
```

Compare three implementations:

1. A small Transformer classifier/planner.
2. A recurrent or state-space model.
3. A hybrid recurrent-plus-local-attention model.

The winning model is the one that reduces cumulative CPU work and preserves task success across multi-turn workflows. Perplexity alone is not a sufficient decision criterion.

## 26. Suggested go/no-go criteria for the larger vision

Pursue a ground-up model family only if the serving prototype demonstrates all of the following:

- At least one target workflow can be completed reliably on CPU.
- Routing avoids expensive generation for a meaningful share of requests.
- Structured state reduces repeated context processing.
- Retrieval and tools improve correctness rather than merely adding latency.
- Hot/warm/cold residency provides useful memory savings.
- A persistent state experiment shows lower cumulative cost on multi-turn tasks.
- The remaining bottleneck is genuinely model computation rather than poor orchestration.

If these conditions are met, the project has evidence that a new model architecture could create value. If they are not met, improving the runtime and workflow design is likely to produce more benefit than inventing a new neural network.

## 27. Bottom-line recommendation

Use a conventional small quantized model as the baseline, test Mamba-, RWKV-, RetNet-, and xLSTM-like ideas as architectural candidates, and prioritize a **hybrid recurrent-plus-local-attention model with structured memory** as the first serious ground-up design.

Host it in a modular CPU-native runtime with:

```text
Rust execution engine
+ typed module contracts
+ Python research layer
+ SQLite/FTS retrieval
+ local vector reranking when justified
+ DRAM working set
+ NVMe cold-module store
+ conditional execution graph
+ verification and telemetry
```

The key strategic rule is:

> Do not let the existing inference backend define the product. Let the execution model define the backend interface.

That is how the project can begin with existing models, learn from real measurements, and gradually replace individual components with models and kernels designed specifically for CPU-centered inference.
