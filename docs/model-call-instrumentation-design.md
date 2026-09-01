# Model Call Instrumentation Design

**Date:** 2026-09-01
**Status:** Implementation note — no benchmark comparison claims

---

## Schema

All fields are optional and stored in `ModuleResult.metadata["model_metrics"]` (dict). Null values indicate the metric is unavailable.

| Field | Type | Unit | Source |
|-------|------|------|--------|
| model_name | string | — | Filename without extension |
| model_path_basename | string | — | Full filename |
| model_loaded | bool | — | Runtime load state |
| model_load_time_ms | float\|null | ms | `perf_counter` around `_load_model()` |
| fallback_used | bool | — | True if demo/placeholder returned |
| fallback_reason | string\|null | — | Description of why fallback was used |
| input_tokens | int | tokens | `usage.prompt_tokens` from llama-cpp-python |
| evidence_tokens | int\|null | tokens | char_count/4 estimate; null if not isolated |
| output_tokens | int | tokens | `usage.completion_tokens` from llama-cpp-python |
| prompt_processing_time_ms | null | — | Not available in llama-cpp-python 0.3.35 |
| generation_time_ms | null | — | Not available in llama-cpp-python 0.3.35 |
| total_model_time_ms | float | ms | `perf_counter` wall time around `create_chat_completion()` |
| time_to_first_token_ms | null | — | Not available (no streaming/first-token timing) |
| stop_reason | string | — | `choices[0].finish_reason` normalized to: stop, length, error, fallback, unknown |
| prompt_tokens_per_second | float\|null | tok/s | input_tokens / (total_model_time_ms / 1000) |
| generation_tokens_per_second | float\|null | tok/s | output_tokens / (total_model_time_ms / 1000) |
| process_rss_before_bytes | int\|null | bytes | RSS before model call |
| process_rss_after_bytes | int\|null | bytes | RSS after model call |
| process_rss_peak_bytes | int\|null | bytes | Peak RSS (same as current on Windows) |
| rss_measurement_method | string | — | Describes how RSS was collected |
| metrics_available | bool | — | False if instrumentation itself failed |
| metrics_unavailable_reason | string\|null | — | Why metrics are unavailable |

## Timing Definitions

- **total_model_time_ms**: Wall-clock time from `perf_counter()` start to end around `create_chat_completion()`. Includes prompt evaluation, generation, and any internal overhead. This is the only reliable timing metric with current llama-cpp-python.
- **prompt_processing_time_ms**: Time spent evaluating/encoding the prompt tokens. **Not available** — llama-cpp-python 0.3.35 does not expose this separately.
- **generation_time_ms**: Time spent generating output tokens. **Not available** — llama-cpp-python 0.3.35 does not expose this separately.
- **time_to_first_token_ms**: Time from request start to first output token. **Not available** — no streaming or first-token timing API exists in this version.

## RSS Collection

| OS | Method | Current RSS | Peak RSS | Limitations |
|----|--------|:-----------:|:--------:|-------------|
| Windows | `PowerShell Get-Process WorkingSet64` | ✅ | ❌ **Unavailable** | Peak RSS is not exposed by this method; only a current working-set snapshot is returned. Direct `GetProcessMemoryInfo` / `PROCESS_MEMORY_COUNTERS` fails in subprocess contexts due to access rights. |
| Linux | `/proc/self/status` VmRSS + VmHWM | ✅ | ✅ | Requires procfs |
| macOS | `sysctl hw.memsize` + `vm_stat` | ✅ | ⚠️ Approximate | Page-size parsing required |
| Unsupported | Returns null | — | — | Explicit reason returned |

**All RSS values are bytes.** Not derived from GGUF file size.

## Backward Compatibility

- `model_metrics` is an **optional** field in `StepTrace.metadata`
- Existing code that reads traces without `model_metrics` continues to work
- `trace_to_dict()` includes `metadata` dict — consumers that don't check for `model_metrics` are unaffected
- Old result JSON files without `model_metrics` load correctly in scorer scripts

## Known Limitations

1. **Prompt/generation time separation** not available — only total wall time is measured
2. **TTFT** not available — no streaming or first-token timing API
3. **Peak RSS** on Windows returns current RSS (peak not exposed by PowerShell method)
4. **evidence_tokens** is a char/4 estimate, not a true token count
5. **tokens-per-second** is derived from total wall time, not separated prompt/generation time
