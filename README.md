# CPU Inference Revolution

A research project exploring CPU-native cognitive serving: redesigning model architecture and inference hosting around CPU control flow, large DRAM, local NVMe, persistent state, retrieval, deterministic tools, modular specialists, and adaptive execution.

## Contents

- `docs/cpu-native-ai-conversation-reference.md` — organized reference of the complete design conversation.
- `docs/cpu-first-llm-starting-guide.md` — ordered implementation and testing guide.
- `docs/cpu-native-cognitive-serving-blueprint.md` — detailed architecture, model candidates, runtime design, and 90-day plan.
- `docs/cpu-native-tonight-lab-plan.md` — short preliminary research and experimentation plan.
- `runtime/cpu-cognitive-runtime-python/` — dependency-light Python research skeleton with typed module contracts, execution graphs, routing, verification, traces, caching, example code, and tests.

## Current thesis

> AI requests should be planned, routed, remembered, retrieved, computed, verified, and rendered—not simply pushed through one dense model until it emits text.

The near-term objective is not to replace GPUs for every large-model workload. It is to determine whether a CPU-centered system can complete selected private, stateful, retrieval-heavy, or structured business tasks with lower total cost per verified successful task.

## Quick start

```bash
cd runtime/cpu-cognitive-runtime-python
python3 example.py
python3 -m pytest -q
```

The initial Python modules are deterministic placeholders. The next research step is to replace one module at a time with a real local model or retrieval backend while preserving the execution-graph contracts and telemetry.

## Research discipline

Keep a fixed benchmark, record CPU/RAM/storage details, separate cold-start from warm inference, run routing in shadow mode before activating it, and measure CPU milliseconds per verified successful task rather than tokens per second alone.

## Status

Early research prototype. Not production software.
