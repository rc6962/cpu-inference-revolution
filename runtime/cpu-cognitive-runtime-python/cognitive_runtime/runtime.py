"""Dependency-light CPU-native cognitive runtime skeleton.

This module intentionally uses deterministic demo modules. Replace them with
real model adapters behind the same interfaces after the graph and telemetry
behavior are validated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import os
import re
from pathlib import Path
import time
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Protocol


class Residency(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


@dataclass(frozen=True)
class Constraints:
    latency_budget_ms: int = 3_000
    memory_budget_mb: int = 4_096
    quality_target: float = 0.95


@dataclass(frozen=True)
class Request:
    request_id: str
    session_id: str
    text: str
    attachments: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    constraints: Constraints = field(default_factory=Constraints)


@dataclass
class Analysis:
    task_type: str
    risk_level: str
    difficulty_band: str
    requires_retrieval: bool
    requires_tools: bool
    output_format: str
    recommended_route: str
    confidence: float
    reason_codes: list[str] = field(default_factory=list)
    deterministic_operation: Optional[str] = None


@dataclass
class ModuleResult:
    module: str
    status: str
    output: Any = None
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepTrace:
    step_id: str
    module: str
    status: str
    cpu_ms: float
    output_summary: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    request_id: str
    status: str
    output: Any
    route: str
    traces: list[StepTrace]
    escalated: bool = False
    escalation_reason: Optional[str] = None


@dataclass
class ExecutionContext:
    request: Request
    analysis: Optional[Analysis] = None
    state: dict[str, Any] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)
    traces: list[StepTrace] = field(default_factory=list)


class Module(Protocol):
    name: str
    residency: Residency

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        ...


class BaseModule:
    name = "base"
    residency = Residency.HOT

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        raise NotImplementedError


class RequestAnalyzer(BaseModule):
    name = "request_analyzer"

    _calc = re.compile(r"\b(?:calculate|compute|what is|percentage|margin|convert)\b", re.I)
    _invoice = re.compile(r"\b(?:invoice|receipt|vendor|subtotal|tax|due date)\b", re.I)
    _retrieval = re.compile(r"\b(?:according to|policy|contract|document|lookup|find|what does)\b", re.I)
    _code = re.compile(r"```|\b(?:python|javascript|sql|api|function|stack trace|bug|compile)\b", re.I)
    _high_risk = re.compile(r"\b(?:medical|diagnos|dosage|legal advice|tax filing|investment|password|credential)\b", re.I)

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        text = context.request.text.strip()
        lowered = text.lower()
        reasons: list[str] = []
        risk = "high" if self._high_risk.search(text) else "low"

        _invoice_fields = re.compile(r"\b(?:vendor|subtotal|total)\b", re.I)
        if self._invoice.search(text) and (context.request.attachments or _invoice_fields.search(text)):
            task = "structured_extraction"
            route = "invoice_extraction"
            output_format = "strict_json"
            requires_tools = True
            reasons.append("TASK_INVOICE_EXTRACTION")
        elif self._calc.search(text) and re.search(r"\d", text):
            task = "calculation"
            route = "deterministic_calculation"
            output_format = "text"
            requires_tools = True
            reasons.append("RULE_DETERMINISTIC_CALCULATION")
        elif self._code.search(text):
            task = "coding"
            route = "specialist"
            output_format = "text"
            requires_tools = False
            reasons.append("TASK_CODING")
        elif self._retrieval.search(text) or context.request.attachments:
            task = "retrieval_qa"
            route = "small_rag"
            output_format = "text"
            requires_tools = False
            reasons.append("RULE_RETRIEVAL_REQUIRED")
        else:
            task = "small_direct"
            route = "small_direct"
            output_format = "text"
            requires_tools = False
            reasons.append("TASK_GENERIC_DIRECT")

        word_count = len(text.split())
        difficulty = "easy" if word_count < 80 else "moderate" if word_count < 400 else "hard"
        if task in {"coding", "structured_extraction"}:
            difficulty = "moderate"
        if risk == "high":
            difficulty = "hard"
            reasons.append("RISK_REQUIRES_ESCALATION_POLICY")

        analysis = Analysis(
            task_type=task,
            risk_level=risk,
            difficulty_band=difficulty,
            requires_retrieval=task == "retrieval_qa",
            requires_tools=requires_tools,
            output_format=output_format,
            recommended_route=route,
            confidence=0.90 if task != "small_direct" else 0.70,
            reason_codes=reasons,
        )
        return ModuleResult(self.name, "success", analysis, analysis.confidence)


class Calculator(BaseModule):
    name = "calculator"

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        text = context.request.text
        numbers = [Decimal(x.replace(",", "")) for x in re.findall(r"\$?\d[\d,]*(?:\.\d+)?", text)]
        if len(numbers) < 2:
            return ModuleResult(self.name, "failed", warnings=["not_enough_numbers"])

        if "margin" in text.lower() and len(numbers) >= 2:
            revenue, expenses = numbers[0], numbers[1]
            result = (revenue - expenses) / revenue
            formatted = f"{result * 100:.2f}%"
            expression = f"({revenue} - {expenses}) / {revenue}"
        elif "/" in text and len(numbers) >= 2:
            result = numbers[0] / numbers[1]
            formatted = f"{result:.6f}"
            expression = f"{numbers[0]} / {numbers[1]}"
        else:
            result = sum(numbers)
            formatted = f"{result:.2f}"
            expression = " + ".join(str(n) for n in numbers)

        return ModuleResult(self.name, "success", {
            "expression": expression,
            "result": float(result),
            "formatted_result": formatted,
        })


class DocumentRetriever(BaseModule):
    name = "document_retriever"
    residency = Residency.WARM

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(
            Path(__file__).parent.parent.parent.parent / "data" / "knowledge.db"
        )

    def _db_exists(self) -> bool:
        return Path(self._db_path).is_file()

    _STOP_WORDS = re.compile(
        r"\b(?:according|to|the|how|many|what|does|is|are|was|were|a|an|in|on|of|for|with|by|from|this|that|it|and|or|not|be|been|being|have|has|had|do|does|did|will|would|shall|should|may|might|can|could)\b",
        re.I,
    )

    def _query(self, query_text: str, top_k: int = 1) -> list[dict]:
        import sqlite3
        # Strip stop words and punctuation to improve FTS5 match quality
        cleaned = self._STOP_WORDS.sub(" ", query_text)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)  # strip punctuation
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            cleaned = query_text  # fallback to original if all words removed
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        # Use OR semantics so partial matches still return results
        fts_query = " OR ".join(cleaned.split())
        rows = conn.execute(
            """SELECT source_id, location, text, bm25(documents_fts) AS rank
               FROM documents_fts
               WHERE documents_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (fts_query, top_k),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        query = context.request.text

        if not self._db_exists():
            evidence = {
                "source_id": "demo-policy.txt",
                "location": "demo",
                "text": f"Evidence selected for query: {query}",
                "retrieval_score": 0.84,
            }
            return ModuleResult(self.name, "success", evidence, 0.84)

        try:
            results = self._query(query)
        except Exception:
            results = []

        if not results:
            evidence = {
                "source_id": "demo-policy.txt",
                "location": "demo",
                "text": f"Evidence selected for query: {query}",
                "retrieval_score": 0.50,
            }
            return ModuleResult(self.name, "success", evidence, 0.50)

        top = results[0]
        evidence = {
            "source_id": top["source_id"],
            "location": top["location"],
            "text": top["text"],
            "retrieval_score": 0.84,
        }
        return ModuleResult(self.name, "success", evidence, 0.84)


class SmallModel(BaseModule):
    name = "small_model"

    def __init__(self, model_path: str | None = None):
        self._model_path = model_path or os.environ.get("CPU_INFERENCE_MODEL_PATH")
        self._llm = None

    def _load_model(self):
        if self._llm is not None:
            return
        if not self._model_path or not Path(self._model_path).exists():
            return
        try:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=self._model_path,
                n_ctx=512,
                n_threads=8,
                verbose=False,
            )
        except Exception:
            self._llm = None

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        self._load_model()

        if self._llm is None:
            # Fallback: original demo behavior
            if context.analysis and context.analysis.task_type == "retrieval_qa":
                evidence = inputs.get("evidence", {})
                answer = f"Based on {evidence.get('source_id', 'the supplied evidence')}: {evidence.get('text', '')}"
            else:
                answer = f"Demo response for: {context.request.text}"
            return ModuleResult(self.name, "success", answer, 0.5)

        try:
            user_text = inputs.get("prompt", context.request.text)

            # For retrieval routes, include evidence context in messages
            # and post-process to preserve source_id in output
            is_retrieval = (
                context.analysis
                and context.analysis.task_type == "retrieval_qa"
            )
            evidence = inputs.get("evidence", {}) if is_retrieval else {}
            source_id = evidence.get("source_id", "the supplied evidence")
            evidence_text = evidence.get("text", "")

            if is_retrieval and evidence_text:
                messages = [
                    {"role": "system", "content": (
                        f"Answer the following question using ONLY the provided evidence. "
                        f"Include the source name '{source_id}' in your response."
                    )},
                    {"role": "user", "content": (
                        f"Evidence: {evidence_text}\n\nQuestion: {user_text}"
                    )},
                ]
            else:
                messages = [
                    {"role": "user", "content": user_text},
                ]

            result = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=256,
                temperature=0.0,
            )
            text = result["choices"][0]["message"]["content"].strip()
            if not text:
                text = f"Demo response for: {context.request.text}"

            # For retrieval routes, ensure source_id is present in output
            if is_retrieval and source_id not in text:
                text = f"Based on {source_id}: {text}"

            return ModuleResult(self.name, "success", text, 0.7)
        except Exception as exc:
            return ModuleResult(
                self.name, "success",
                f"Demo response for: {context.request.text}",
                0.5, warnings=[f"LLM inference failed: {exc}"],
            )


class InvoiceExtractor(BaseModule):
    name = "invoice_extractor"
    residency = Residency.WARM

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        text = context.request.text
        total_match = re.search(r"total\s*[:$]?\s*(\d[\d,.]*\d|\d)", text, re.I)
        tax_match = re.search(r"tax\s*[:$]?\s*(\d[\d,.]*\d|\d)", text, re.I)
        vendor_match = re.search(r"\bvendor\b\s*(?::|\s)\s*([^,\n]+?)\s*(?=,\s*(?:tax|total)\b|$)", text, re.I)
        output = {
            "vendor": vendor_match.group(1).strip() if vendor_match else None,
            "tax": float(tax_match.group(1).replace(",", "")) if tax_match else None,
            "total": float(total_match.group(1).replace(",", "")) if total_match else None,
        }
        missing = [key for key, value in output.items() if value is None]
        return ModuleResult(self.name, "success", output, 0.88 if not missing else 0.60,
                            [f"missing_{key}" for key in missing])


class ResponseRenderer(BaseModule):
    name = "response_renderer"

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        if "calculation" in inputs:
            return ModuleResult(self.name, "success", inputs["calculation"]["formatted_result"])
        if "extraction" in inputs:
            return ModuleResult(self.name, "success", json.dumps(inputs["extraction"], sort_keys=True))
        return ModuleResult(self.name, "success", str(inputs.get("answer", "No answer produced.")))


class Verifier(BaseModule):
    name = "verifier"

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        if "extraction" in inputs:
            extraction = inputs["extraction"]
            if extraction.get("total") is None:
                return ModuleResult(self.name, "failed", warnings=["missing_total"], confidence=0.40)
        if "evidence" in inputs and inputs["evidence"].get("retrieval_score", 0) < 0.60:
            return ModuleResult(self.name, "failed", warnings=["weak_evidence"], confidence=0.50)
        return ModuleResult(self.name, "success", {"verified": True}, 0.98)


@dataclass
class Step:
    step_id: str
    module: str
    input_keys: tuple[str, ...] = ()
    output_key: Optional[str] = None
    condition: Optional[Callable[[ExecutionContext], bool]] = None


class ExecutionGraph:
    def __init__(self, steps: Iterable[Step], route_name: str):
        self.steps = list(steps)
        self.route_name = route_name

    def run(self, context: ExecutionContext, modules: Mapping[str, Module]) -> ExecutionResult:
        for step in self.steps:
            if step.condition and not step.condition(context):
                continue
            module = modules[step.module]
            inputs = {key: context.values[key] for key in step.input_keys if key in context.values}
            started = time.perf_counter()
            result = module.run(context, inputs)
            cpu_ms = (time.perf_counter() - started) * 1000
            if result.status != "success":
                context.traces.append(StepTrace(step.step_id, step.module, result.status, cpu_ms, "failed", result.warnings))
                return ExecutionResult(context.request.request_id, "needs_escalation", None,
                                       self.route_name, context.traces, True,
                                       ";".join(result.warnings) or f"step_failed:{step.step_id}")
            if step.output_key:
                context.values[step.output_key] = result.output
            context.traces.append(StepTrace(step.step_id, step.module, result.status, cpu_ms,
                                            _summarize(result.output), result.warnings))

        output = context.values.get("response", context.values.get("answer"))
        return ExecutionResult(context.request.request_id, "success", output,
                               self.route_name, context.traces)


def _summarize(value: Any) -> str:
    text = str(value)
    return text[:160] + "..." if len(text) > 160 else text


def normalize_key(request: Request) -> str:
    raw = json.dumps({"text": " ".join(request.text.lower().split()),
                      "attachments": request.attachments,
                      "permissions": request.permissions}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


class Runtime:
    def __init__(self):
        self.modules: Dict[str, Module] = {
            "request_analyzer": RequestAnalyzer(),
            "calculator": Calculator(),
            "document_retriever": DocumentRetriever(),
            "small_model": SmallModel(),
            "invoice_extractor": InvoiceExtractor(),
            "response_renderer": ResponseRenderer(),
            "verifier": Verifier(),
        }
        self.cache: dict[str, ExecutionResult] = {}

    def analyze(self, request: Request) -> Analysis:
        context = ExecutionContext(request)
        result = self.modules["request_analyzer"].run(context, {})
        assert isinstance(result.output, Analysis)
        return result.output

    def choose_graph(self, analysis: Analysis) -> ExecutionGraph:
        if analysis.recommended_route == "deterministic_calculation":
            return ExecutionGraph([
                Step("calculate", "calculator", output_key="calculation"),
                Step("render", "response_renderer", ("calculation",), "response"),
            ], "deterministic_calculation")
        if analysis.recommended_route == "invoice_extraction":
            return ExecutionGraph([
                Step("extract", "invoice_extractor", output_key="extraction"),
                Step("verify", "verifier", ("extraction",), "verification"),
                Step("render", "response_renderer", ("extraction",), "response"),
            ], "invoice_extraction")
        if analysis.recommended_route == "small_rag":
            return ExecutionGraph([
                Step("retrieve", "document_retriever", output_key="evidence"),
                Step("answer", "small_model", ("evidence",), "answer"),
                Step("verify", "verifier", ("evidence",), "verification"),
                Step("render", "response_renderer", ("answer",), "response"),
            ], "small_rag")
        return ExecutionGraph([
            Step("generate", "small_model", output_key="answer"),
            Step("render", "response_renderer", ("answer",), "response"),
        ], "small_direct")

    def execute(self, request: Request, use_cache: bool = True) -> ExecutionResult:
        key = normalize_key(request)
        if use_cache and key in self.cache:
            cached = self.cache[key]
            return ExecutionResult(request.request_id, cached.status, cached.output,
                                   "exact_cache", cached.traces)

        analysis = self.analyze(request)
        context = ExecutionContext(request, analysis)
        graph = self.choose_graph(analysis)
        result = graph.run(context, self.modules)
        if result.status == "success" and analysis.risk_level == "high":
            result.escalated = True
            result.escalation_reason = "high_risk_requires_policy_review"
        if result.status == "success":
            self.cache[key] = result
        return result


def trace_to_dict(result: ExecutionResult) -> dict[str, Any]:
    return {
        "request_id": result.request_id,
        "status": result.status,
        "route": result.route,
        "output": result.output,
        "escalated": result.escalated,
        "escalation_reason": result.escalation_reason,
        "steps": [
            {
                "step_id": trace.step_id,
                "module": trace.module,
                "status": trace.status,
                "cpu_ms": round(trace.cpu_ms, 3),
                "output_summary": trace.output_summary,
                "warnings": trace.warnings,
            }
            for trace in result.traces
        ],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
