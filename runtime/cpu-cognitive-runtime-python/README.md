# CPU Cognitive Runtime — Python Skeleton

This is a dependency-light research skeleton for the modular CPU-native cognitive serving architecture. It demonstrates:

- Typed request, analysis, module-result, graph-step, and execution-result contracts.
- A rule-based request analyzer.
- Deterministic calculation routing.
- Retrieval, small-model, extraction, rendering, and verification modules.
- Conditional execution-graph structure.
- Verified exact-response caching.
- Per-step CPU timing and trace output.

The model modules are deterministic demo adapters. They intentionally do not call an external model. Replace them one at a time with real backends while preserving the module interfaces.

## Run

```bash
cd /home/ubuntu/cpu-cognitive-runtime-python
python3 example.py
python3 -m pytest -q
```

The test suite requires `pytest`. The example itself uses only the Python standard library.

## Replace a demo module

Implement the same interface:

```python
class MyModel:
    name = "my_model"
    residency = Residency.WARM

    def run(self, context, inputs):
        return ModuleResult(
            module=self.name,
            status="success",
            output={"answer": "..."},
            confidence=0.9,
        )
```

Register it in `Runtime.__init__`, then select it from `Runtime.choose_graph`. The graph and telemetry code should not need to know whether the module uses a conventional Transformer, ONNX Runtime, a recurrent model, or a deterministic algorithm.

## Recommended next increments

1. Move route definitions into YAML or JSON configuration.
2. Add a real benchmark JSONL replay harness.
3. Replace the demo retriever with SQLite FTS5 and source-linked evidence records.
4. Add a real small quantized model behind a `ModelBackend` adapter.
5. Add a model manifest with hot/warm/cold residency metadata.
6. Add resource budgets, deadlines, cancellation, and selective retries.
7. Add a shadow-mode analyzer that logs proposed routes without activating them.
8. Add a persistent session-state store.
9. Add cold-module loading and NVMe prefetch experiments.

## Deliberate limitations

This is a research starting point, not a production server. It does not yet include authentication, network serving, model loading, concurrency controls, persistent storage, sandboxed tool execution, or production-grade safety policy. Those should be added after the graph contracts and benchmark behavior are stable.
