# CPU-Native AI: Tonight Lab Plan

**Objective:** Determine whether a CPU-centered serving architecture can reduce total work for a real task before investing in a new model architecture or production runtime.

## The goal for tonight

Do not try to build a new LLM in one evening. The useful outcome is a small experiment that answers three questions:

1. **How much of the request can be handled without a large neural generation pass?**
2. **How much repeated prompt/context work can be eliminated with state, caching, and retrieval?**
3. **Where is the actual CPU bottleneck: model arithmetic, memory movement, orchestration, retrieval, or loading?**

The best initial result is a table of measurements, not a sophisticated demo.

> A plausible CPU-native system should reduce **CPU milliseconds per verified successful task**, not merely claim a high token-per-second number.

---

## Recommended time-box: four to six hours

| Time | Activity | Deliverable |
|---|---|---|
| 30 minutes | Choose one task and benchmark cases | 20–50 labeled examples |
| 45 minutes | Research model/runtime candidates | Short candidate matrix |
| 60 minutes | Run a single-model CPU baseline | Baseline measurements |
| 60 minutes | Run the existing modular skeleton | Route and trace output |
| 60 minutes | Add a context/state experiment | Full-context versus compact-state comparison |
| 30 minutes | Analyze results | Go/no-go decision for next experiment |

If you have less time, do the baseline and the modular skeleton first.

---

## Step 1: choose one narrow task

Pick a task that has a correct or mostly checkable answer. Good choices for tonight are:

- Extract fields from 10–20 invoice-like text files.
- Classify support tickets into a small set of labels.
- Answer questions from a small local policy document.
- Calculate business metrics from supplied numbers.
- Maintain state across a multi-turn workflow.

Avoid general chat as the first experiment. General chat makes it difficult to distinguish model quality from serving efficiency.

Create a small JSONL benchmark such as:

```json
{"id":"calc-001","task":"calculation","input":"Revenue is 850000 and expenses are 612000. What is the operating margin?","expected":"28.00%"}
{"id":"extract-001","task":"extraction","input":"Vendor: Example Co, Tax: 19.80, Total: 119.80","expected":{"vendor":"Example Co","tax":19.80,"total":119.80}}
{"id":"qa-001","task":"retrieval_qa","input":"According to the policy, how many days of notice are required?","expected_source":"policy.txt"}
```

Include at least:

- Five easy cases.
- Five moderate cases.
- Five ambiguous or failure cases.
- A few cases that should bypass the model entirely.

Label the expected route family, not just the expected answer:

```text
cache
rule/tool
retrieval
small model
specialist
clarification
```

---

## Step 2: inspect the machine you are testing

Record the CPU, cores, RAM, storage type, and instruction-set support. On Linux, run:

```bash
lscpu
free -h
lsblk -o NAME,SIZE,ROTA,TYPE,MOUNTPOINT
```

Record:

```text
CPU model:
Physical cores:
Logical cores:
RAM:
NVMe or SATA:
AVX/AVX2/AVX-512/AMX support:
```

Do not compare results across machines without recording these details. CPU inference is highly affected by memory bandwidth, cache, instruction support, thermal limits, and thread count.

---

## Step 3: establish a single-model baseline

Use one small quantized instruction model that can run locally through a mature CPU backend. The exact model should be selected based on:

- License appropriate for your intended use.
- CPU support.
- Model size that fits comfortably in RAM.
- Quality on your chosen task.
- Reliable structured-output behavior.

For the first experiment, use a small model rather than a large model. The baseline is meant to answer:

> What happens if every request is sent to one conventional model?

Measure each request with:

```text
model load time
warm time to first token
total wall-clock latency
CPU time
peak RAM
input tokens
output tokens
correctness
format validity
```

Run warm and cold cases separately. A model that is fast after loading may be impractical if every request requires a large cold load.

If you already have a local model runtime installed, use it. If not, do not lose the entire evening setting up an elaborate stack; continue with the deterministic and modular experiments first.

---

## Step 4: run the modular Python skeleton

The existing skeleton is at:

```text
/home/ubuntu/cpu-cognitive-runtime-python
```

Run:

```bash
cd /home/ubuntu/cpu-cognitive-runtime-python
python3 example.py
python3 -m pytest -q
```

This prototype intentionally uses deterministic demo modules. That is useful tonight because it lets you test the **serving architecture** independently of model quality.

Observe that the runtime can choose among:

```text
exact cache
→ deterministic calculation
→ retrieval plus small model
→ invoice specialist plus verifier
→ direct small model
```

The immediate experiment is not “is the demo intelligent?” It is:

> Can the runtime express different execution plans and produce step-level traces?

That is the foundation needed before comparing models.

---

## Step 5: instrument the key comparison

Create a simple comparison table with one row per request:

| Request | Single-model route CPU ms | Modular route CPU ms | Model calls | Verified? | Route |
|---|---:|---:|---:|---|---|
| Calculation | | | | | |
| Extraction | | | | | |
| Retrieval Q&A | | | | | |
| Rewrite | | | | | |

Initially, the modular demo may not beat a real model because it uses placeholder modules. That is fine. The purpose is to verify that the measurement and execution framework works.

The first meaningful improvement is usually visible when deterministic requests bypass model inference entirely.

---

## Step 6: perform the context-reduction experiment

This is the most important preliminary experiment for the broader architecture.

Create a 10-turn workflow where the user gradually supplies information. Compare two approaches:

### Approach A: repeated full history

```text
turn 1 + turn 2 + turn 3 + ... + current turn
→ model
```

### Approach B: compact state

```text
structured task state + recent turn + relevant evidence
→ model
```

Example state:

```json
{
  "task": "invoice_review",
  "vendor": "Example Co",
  "subtotal": 100.00,
  "tax": 19.80,
  "total": 119.80,
  "unresolved": [],
  "next_action": "approve"
}
```

Measure cumulative input tokens and cumulative CPU time across the whole workflow. The question is not whether a summary sounds elegant; it is whether the compact state preserves the information needed for correct decisions.

### Success condition

The compact-state approach should:

- Use materially fewer input tokens.
- Preserve or improve task accuracy.
- Avoid repeatedly processing irrelevant conversation history.
- Make the next required action explicit.

If this works, it supports the case for a persistent CPU-oriented runtime and eventually a recurrent or state-space model.

---

## Step 7: test CPU and memory behavior separately

Do not assume that CPU arithmetic is the only bottleneck. Run small controlled tests:

### Test A: thread scaling

Run the same model with 1, 2, 4, and all available physical cores. Record latency and CPU utilization. If performance stops improving early, memory bandwidth or synchronization may be limiting you.

### Test B: context scaling

Run the same request with short, medium, and long context. Record how latency and RAM change.

### Test C: model residency

Compare:

```text
model already resident in RAM
versus
model loaded from storage before execution
```

Record cold-start latency separately. Do not mix cold loading with warm inference.

### Test D: retrieval versus prompt stuffing

Compare:

```text
full document in prompt
versus
short source-linked evidence object
```

Measure total tokens, CPU time, answer accuracy, and evidence support.

### Test E: output length

Ask the model for a short structured result and then for a long explanatory answer. Measure how much cost is attributable to unnecessary language generation.

---

## Step 8: research these model families in this order

The purpose of preliminary research is to identify architectural mechanisms, not to collect model names.

### 1. Conventional small Transformer

Study it as the control group. Understand:

- Prefill versus decode.
- KV cache.
- Quantization.
- Memory bandwidth.
- Batch size.
- Prompt-length effects.

### 2. Mamba and state-space models

Study them for persistent sequential state, long-sequence processing, and alternatives to full attention. Focus on the serving path and actual CPU implementations.

### 3. RWKV

Study it for recurrent-style inference and stateful generation. Ask whether its state can represent the information needed for your chosen workflow.

### 4. RetNet

Study it for retention-based sequence processing and recurrent versus parallel execution paths.

### 5. xLSTM

Study it for learned persistent memory and task-state tracking, especially as a controller or memory module rather than necessarily as the final language generator.

### 6. Hybrid design

Your likely target architecture is:

```text
small recent-window attention
+ persistent recurrent state
+ structured external memory
+ specialist modules
+ tools and verification
```

Do not decide which research architecture wins from papers alone. Build small workload-specific tests.

---

## Step 9: sketch the first redesigned small model

Do not start with a general language model. Start with a small **task-state model**.

### Proposed input

```json
{
  "previous_state": {"task":"invoice_review","known_fields":["vendor"]},
  "new_input": "The total is 119.80.",
  "evidence": [],
  "constraints": {"quality_target":0.95}
}
```

### Proposed output

```json
{
  "updated_state": {
    "task": "invoice_review",
    "known_fields": ["vendor", "total"]
  },
  "memory_reads": [],
  "tool_calls": ["recompute_total"],
  "confidence": 0.91,
  "next_action": "validate"
}
```

### First architecture sketch

```text
text encoder
   ↓
small recurrent state update
   ↓
local recent-window attention
   ↓
structured memory read/write
   ↓
router
   ├── extraction specialist
   ├── retrieval
   ├── calculator
   └── response renderer
```

This design changes the task from “generate the next token indefinitely” to “update state and select the next operation.” It is much easier to test and aligns with CPU strengths.

### First training data

You can create initial examples from:

- Hand-authored workflow traces.
- Synthetic variations of structured tasks.
- Teacher-model outputs reviewed against deterministic checks.
- Existing application logs, after privacy review.

The first model should be evaluated on state accuracy, action selection, tool selection, and memory efficiency—not only text fluency.

---

## Step 10: implement only three software upgrades next

After tonight, the best next software steps are:

### Upgrade 1: real benchmark replay

Add `benchmark.jsonl` and a script that runs every request through:

```text
baseline route
modular route
forced specialist route
```

Output a CSV or JSON report with correctness and resource metrics.

### Upgrade 2: real routing shadow mode

Let the analyzer recommend routes while the baseline model still executes every request. Compare predicted route against the route that actually produced a verified answer.

This prevents early routing mistakes from corrupting user results.

### Upgrade 3: one real model adapter

Replace only `SmallModel` with a real local model backend. Keep the analyzer, graph, verifier, cache, and telemetry unchanged.

This isolates model performance from runtime design.

---

## What results would support the idea?

The idea becomes more plausible if you observe several of these results:

- 20–50% of benchmark requests can be handled by rules, cache, retrieval, or deterministic tools.
- Compact state preserves accuracy while reducing repeated context tokens.
- Specialist models outperform a general small model at the same CPU budget.
- Verification catches cheap-route failures before they reach the user.
- Local retrieval plus evidence compression reduces model work.
- Warm module residency matters more than raw model size.
- Mixed workloads are better served by multiple small modules than one model.
- The CPU system has better total task latency than expected on low-concurrency requests.

A particularly strong result would be:

```text
same verified task success
+ fewer model calls
+ fewer input/output tokens
+ lower CPU milliseconds
+ lower peak RAM
```

---

## What results would weaken the idea?

Be prepared for negative findings. The architecture may need to change if:

- Routing overhead costs nearly as much as the model call.
- Retrieval adds latency without improving correctness.
- Compact state loses critical information.
- Cold model loading dominates total response time.
- CPU memory bandwidth becomes the bottleneck even for small modules.
- A single quantized model is already cheaper and simpler for the target workload.
- Specialist models require too many resident modules.
- The verifier needs almost as much computation as the generator.

Negative results are useful because they identify where a new model or kernel is actually justified.

---

## Decision at the end of tonight

Write down one of these decisions:

### Continue with serving architecture

Choose this if routing, deterministic tools, retrieval, or state clearly reduce total task cost.

### Continue with model architecture research

Choose this if the serving system works but repeated neural computation remains the dominant cost, especially for persistent multi-turn state.

### Continue with systems optimization

Choose this if model computation is acceptable but model loading, memory movement, retrieval, or scheduling dominates.

### Narrow the target workload

Choose this if general chat is too difficult to measure but a structured workflow shows clear CPU advantages.

### Stop or change direction

Choose this if the system does not improve quality, latency, cost, or deployment value compared with the simplest baseline.

---

## The most important principle

Do not try to prove tonight that CPUs can beat top-end GPUs at dense token generation. Try to prove something more actionable:

> A CPU-native system can solve a useful task by combining small models, persistent state, retrieval, tools, and verification while avoiding most unnecessary dense generation.

If that is true, you have a foundation for redesigning the serving layer and eventually designing a model specifically for it.

## References

[1]: https://github.com/ggerganov/llama.cpp "llama.cpp repository"

[2]: https://arxiv.org/abs/2312.00752 "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"

[3]: https://github.com/BlinkDL/RWKV-LM "RWKV language model repository"

[4]: https://arxiv.org/abs/2307.08621 "Retentive Network: A Successor to Transformer for Large Language Models"

[5]: https://arxiv.org/abs/2405.04517 "xLSTM: Extended Long Short-Term Memory"
