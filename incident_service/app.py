import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from kubernetes import client, config as kube_config
except ImportError:  # pragma: no cover
    client = None
    kube_config = None


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("incident-service")


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


DB_URL = (
    f"postgresql://{env('INCIDENT_DB_USER', 'incident_user')}:{env('INCIDENT_DB_PASSWORD', 'incident_password')}"
    f"@{env('INCIDENT_DB_HOST', 'localhost')}:{env('INCIDENT_DB_PORT', '5433')}"
    f"/{env('INCIDENT_DB_NAME', 'incident_memory')}"
)
PROMETHEUS_URL = env("PROMETHEUS_URL", "http://localhost:9090")
JAEGER_URL = env("JAEGER_URL", "http://localhost:16686")
INCIDENT_API_URL = env("INCIDENT_API_URL", "http://localhost:8000")
DETECTION_INTERVAL = int(env("DETECTION_INTERVAL_SECONDS", "15"))
DIAGNOSIS_WINDOW_MINUTES = int(env("DIAGNOSIS_WINDOW_MINUTES", "2"))
TREND_LOOKBACK_HOURS = int(env("TREND_LOOKBACK_HOURS", "6"))
EMBEDDING_API_BASE = env("EMBEDDING_API_BASE_URL", "")
EMBEDDING_API_KEY = env("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL = env("EMBEDDING_MODEL", "")
LLM_API_BASE = env("LLM_API_BASE_URL", "")
LLM_API_KEY = env("LLM_API_KEY", "")
LLM_MODEL = env("LLM_MODEL", "")


SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    workload TEXT NOT NULL,
    rule TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    symptoms JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    trace_reference TEXT,
    diagnosis JSONB,
    resolution_outcome TEXT,
    embedding vector(64)
);
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS scenario TEXT;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS observation_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS diagnosis_window JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS canonical_fingerprint JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE TABLE IF NOT EXISTS diagnosis_reports (
    id UUID PRIMARY KEY,
    incident_id UUID REFERENCES incidents(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT 'Diagnosis report',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    fingerprint JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnosis JSONB NOT NULL DEFAULT '{}'::jsonb,
    similar_incidents JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS diagnosis_reports_incident_idx ON diagnosis_reports (incident_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS active_incident_fingerprint
    ON incidents (fingerprint) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS incidents_embedding_idx
    ON incidents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 1);
ALTER TABLE incidents ALTER COLUMN embedding DROP NOT NULL;
ALTER TABLE diagnosis_reports ALTER COLUMN incident_id DROP NOT NULL;
ALTER TABLE diagnosis_reports ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT 'Diagnosis report';
UPDATE incidents SET title = 'Unclassified incident candidate' WHERE title IS NULL;
"""


@dataclass(frozen=True)
class Rule:
    name: str
    query: str
    threshold: float
    comparison: str
    severity: str
    symptom: str


RULES = (
    Rule(
        "high_cpu",
        'sum(rate(process_cpu_seconds_total[2m]))',
        0.50,
        ">",
        "high",
        "API process CPU is above the demo threshold",
    ),
    Rule(
        "high_memory",
        'max(demo_memory_pressure_bytes / clamp_min(demo_memory_pressure_limit_bytes, 1))',
        0.80,
        ">",
        "high",
        "API memory is above 80 percent of its configured limit",
    ),
    Rule(
        "high_latency",
        'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[2m])))',
        1.0,
        ">",
        "high",
        "API p95 latency is above one second",
    ),
    Rule(
        "error_rate",
        'sum(rate(http_requests_total{status=~"5.."}[2m])) / clamp_min(sum(rate(http_requests_total[2m])), 0.001)',
        0.05,
        ">",
        "high",
        "API HTTP 5xx percentage is above the five percent threshold",
    ),
    Rule(
        "db_pool_exhaustion",
        'max(demo_db_held_connections / clamp_min(demo_db_pool_capacity, 1))',
        0.90,
        ">",
        "high",
        "Database connection pool is at least 90 percent occupied",
    ),
    Rule(
        "db_lock_contention",
        'max(demo_db_lock_contention_active)',
        0.5,
        ">",
        "high",
        "Database lock contention mode is active",
    ),
    Rule(
        "dependency_retry_storm",
        'sum(rate(demo_dependency_retries_total[2m]))',
        0.10,
        ">",
        "high",
        "Downstream dependency retries are above the demo threshold",
    ),
    Rule(
        "api_target_down",
        'sum(up{job=~".*incident.*|.*api.*"})',
        2.0,
        "<",
        "critical",
        "Fewer than two API scrape targets are available",
    ),
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def local_embedding(text: str) -> list[float]:
    values = [0.0] * 64
    tokens = text.lower().split()
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        for index in range(0, len(digest), 2):
            bucket = int.from_bytes(digest[index:index + 2], "big") % 64
            values[bucket] += 1.0 if digest[index] % 2 else -1.0
    magnitude = sum(value * value for value in values) ** 0.5 or 1.0
    return [value / magnitude for value in values]


async def embedding(text: str) -> list[float]:
    if EMBEDDING_API_BASE and EMBEDDING_API_KEY and EMBEDDING_MODEL:
        headers = {"Authorization": f"Bearer {EMBEDDING_API_KEY}"}
        async with httpx.AsyncClient(timeout=20) as http:
            response = await http.post(
                f"{EMBEDDING_API_BASE.rstrip('/')}/embeddings",
                headers=headers,
                json={"model": EMBEDDING_MODEL, "input": text},
            )
            try:
                response.raise_for_status()
                values = response.json()["data"][0]["embedding"]
                if len(values) == 64:
                    return values
            except Exception as error:
                logger.warning("external embedding failed; using local embedding: %s", error)
    return local_embedding(text)


def db_connect() -> psycopg.Connection:
    return psycopg.connect(DB_URL, connect_timeout=3)


def init_db() -> None:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA)


async def prometheus_query(query: str) -> tuple[float | None, dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            response = await http.get(f"{PROMETHEUS_URL.rstrip('/')}/api/v1/query", params={"query": query})
            response.raise_for_status()
            payload = response.json()
            result = payload.get("data", {}).get("result", [])
            if not result:
                return None, payload
            return float(result[0]["value"][1]), payload
    except Exception as error:
        logger.warning("Prometheus query failed: %s", error)
        return None, {"error": str(error), "query": query}


async def prometheus_range(query: str, start: datetime, end: datetime) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            response = await http.get(
                f"{PROMETHEUS_URL.rstrip('/')}/api/v1/query_range",
                params={"query": query, "start": start.timestamp(), "end": end.timestamp(), "step": 15},
            )
            response.raise_for_status()
            return response.json()
    except Exception as error:
        return {"error": str(error), "query": query}


def range_values(payload: dict[str, Any]) -> list[tuple[float, float]]:
    if not isinstance(payload, dict):
        return []
    values: list[tuple[float, float]] = []
    for series in payload.get("data", {}).get("result", []):
        for timestamp, value in series.get("values", []):
            try:
                values.append((float(timestamp), float(value)))
            except (TypeError, ValueError):
                continue
    return sorted(values)


def metric_summary(rule: Rule, payload: dict[str, Any]) -> dict[str, Any]:
    values = range_values(payload)
    mean = sum(value for _, value in values) / len(values) if values else None
    breached = lambda value: is_triggered(rule, value)
    first = next((timestamp for timestamp, value in values if breached(value)), None)
    return {
        "rule": rule.name,
        "mean": round(mean, 6) if mean is not None else None,
        "threshold": rule.threshold,
        "comparison": rule.comparison,
        "status": "NO_DATA" if mean is None else ("BREACHED" if breached(mean) else "NORMAL"),
        "first_breached_at": datetime.fromtimestamp(first, timezone.utc).isoformat() if first else None,
        "sample_count": len(values),
    }


def normalized_metric(summary: dict[str, Any]) -> float:
    mean = summary.get("mean")
    threshold = float(summary.get("threshold") or 1)
    if mean is None:
        return 0.0
    if summary.get("comparison") == "<":
        return round(min(10.0, threshold / max(float(mean), 0.000001)), 6)
    return round(min(10.0, max(0.0, float(mean) / threshold)), 6)


def trend_classification(values: list[tuple[float, float]], threshold: float) -> tuple[str, float | None]:
    if len(values) < 2:
        return "insufficient_data", None
    first_time, first_value = values[0]
    last_time, last_value = values[-1]
    elapsed = max(last_time - first_time, 1.0)
    slope = (last_value - first_value) / elapsed
    change = abs(last_value - first_value) / max(abs(threshold), 0.000001)
    return ("gradual" if change >= 0.25 and elapsed >= 3600 else "sudden"), round(slope, 8)


async def jaeger_traces(start: datetime, end: datetime, *, tags: dict[str, str] | None = None, min_duration: str | None = None) -> list[dict[str, Any]]:
    try:
        params: dict[str, Any] = {
            "service": "incident-demo-api",
            "start": int(start.timestamp() * 1_000_000),
            "end": int(end.timestamp() * 1_000_000),
            "limit": 20,
        }
        if tags:
            params["tags"] = json.dumps(tags)
        if min_duration:
            params["minDuration"] = min_duration
        async with httpx.AsyncClient(timeout=10) as http:
            response = await http.get(f"{JAEGER_URL.rstrip('/')}/api/traces", params=params)
            response.raise_for_status()
            return response.json().get("data", [])
    except Exception:
        return []


async def trace_reference() -> str | None:
    traces = await jaeger_traces(now() - timedelta(minutes=DIAGNOSIS_WINDOW_MINUTES), now())
    return traces[0].get("traceID") if traces else None


def trace_summary(trace: dict[str, Any], failed: bool = False) -> dict[str, Any]:
    spans = trace.get("spans") or []
    def duration(span: dict[str, Any]) -> float:
        try:
            return float(span.get("duration") or 0)
        except (TypeError, ValueError):
            return 0.0

    total = sum(duration(span) for span in spans) or 1.0
    bottleneck = max(spans, key=duration, default={})
    process = (trace.get("processes") or {}).get(bottleneck.get("processID"), {})
    tags = {tag.get("key"): tag.get("value") for tag in bottleneck.get("tags", [])}
    return {
        "trace_id": trace.get("traceID"),
        "failed": failed or tags.get("error") is True or str(tags.get("error", "")).lower() == "true",
        "duration_ms": round(total / 1000, 2),
        "span_service": process.get("serviceName"),
        "span_operation": bottleneck.get("operationName"),
        "pct_of_total_duration": round(duration(bottleneck) / total * 100, 2),
    }


def duration_bucket(duration_ms: float) -> str:
    if duration_ms < 100:
        return "lt_100ms"
    if duration_ms < 500:
        return "100_500ms"
    if duration_ms < 1000:
        return "500ms_1s"
    if duration_ms < 5000:
        return "1_5s"
    return "gte_5s"


def log_categories(lines: list[str]) -> list[str]:
    """Return stable evidence labels; never fingerprint raw log text."""
    categories: set[str] = set()
    for line in lines:
        text = str(line).lower()
        if any(word in text for word in ("timeout", "timed out", "deadline")):
            categories.add("timeout")
        if any(word in text for word in ("connection refused", "connection reset", "connecterror")):
            categories.add("connection_error")
        if any(word in text for word in ("500", "502", "503", "504", "internal server error")):
            categories.add("http_5xx")
        if any(word in text for word in ("traceback", "exception", "error")):
            categories.add("application_error")
        if any(word in text for word in ("database", "postgres", "pool", "lock")):
            categories.add("database")
    return sorted(categories)


def pod_categories(pods: list[dict[str, Any]]) -> list[str]:
    categories: set[str] = set()
    for pod in pods:
        if pod.get("error"):
            categories.add("unavailable")
            continue
        phase = str(pod.get("phase") or "unknown").lower()
        if phase != "running":
            categories.add(f"pod_{phase}")
        try:
            restarts = int(pod.get("restarts") or 0)
        except (TypeError, ValueError):
            restarts = 0
        if restarts:
            categories.add("restarts_1_2" if restarts < 3 else "restarts_3_plus")
    return sorted(categories)


def trace_fingerprint(trace_items: list[dict[str, Any]]) -> dict[str, Any]:
    durations = []
    for item in trace_items:
        try:
            durations.append(float(item.get("duration_ms") or 0))
        except (TypeError, ValueError):
            durations.append(0.0)
    services = sorted({item.get("span_service") for item in trace_items if item.get("span_service")})
    operations = sorted({item.get("span_operation") for item in trace_items if item.get("span_operation")})
    failed_count = sum(1 for item in trace_items if item.get("failed"))
    max_duration = max(durations, default=0.0)
    return {
        "count": len(trace_items),
        "failed_count": failed_count,
        "slow_count": sum(1 for duration in durations if duration >= 1000),
        "max_duration_ms": round(max_duration, 2),
        "max_duration_bucket": duration_bucket(max_duration) if trace_items else None,
        "failed_or_slow": bool(trace_items),
        "services": services,
        "operations": operations,
    }


async def pod_evidence() -> list[dict[str, Any]]:
    if client is None or kube_config is None:
        return []
    try:
        try:
            kube_config.load_incluster_config()
        except Exception:
            kube_config.load_kube_config()
        pods = client.CoreV1Api().list_namespaced_pod("incident-platform", label_selector="app=incident-api").items
        return [
            {"name": pod.metadata.name, "phase": pod.status.phase, "restarts": sum((container.restart_count or 0) for container in (pod.status.container_statuses or []))}
            for pod in pods
        ]
    except Exception as error:
        return [{"error": str(error)}]


async def log_evidence(since_seconds: int = DIAGNOSIS_WINDOW_MINUTES * 60) -> list[str]:
    if client is None or kube_config is None:
        return []
    try:
        try:
            kube_config.load_incluster_config()
        except Exception:
            kube_config.load_kube_config()
        pods = client.CoreV1Api().list_namespaced_pod("incident-platform", label_selector="app=incident-api").items
        lines: list[str] = []
        for pod in pods:
            text = client.CoreV1Api().read_namespaced_pod_log(
                pod.metadata.name, "incident-platform", since_seconds=since_seconds, tail_lines=80
            )
            lines.extend(text.splitlines()[-80:])
        return lines[-200:]
    except Exception as error:
        return [f"log collection error={error}"]


async def diagnosis_telemetry() -> dict[str, Any]:
    end = now()
    start = end.replace(microsecond=0)
    start = start - timedelta(minutes=DIAGNOSIS_WINDOW_MINUTES)
    range_results = await asyncio.gather(*(prometheus_range(rule.query, start, end) for rule in RULES))
    ranges = {rule.name: payload for rule, payload in zip(RULES, range_results)}
    rules_by_name = {rule.name: rule for rule in RULES}
    metrics = {name: metric_summary(rules_by_name[name], payload) for name, payload in ranges.items()}
    breached = [item for item in metrics.values() if item["status"] == "BREACHED"]
    dominant = min(breached, key=lambda item: item.get("first_breached_at") or "9999")["rule"] if breached else None
    trend_payload: dict[str, Any] = {}
    trend, slope = "insufficient_data", None
    if dominant:
        trend_start = end - timedelta(hours=TREND_LOOKBACK_HOURS)
        trend_payload = await prometheus_range(rules_by_name[dominant].query, trend_start, end)
        trend, slope = trend_classification(range_values(trend_payload), rules_by_name[dominant].threshold)
    failed_traces, slow_traces = await asyncio.gather(
        jaeger_traces(start, end, tags={"error": "true"}),
        jaeger_traces(start, end, min_duration="1s"),
    )
    trace_items = [trace_summary(trace, failed=True) for trace in failed_traces]
    trace_items.extend(trace_summary(trace) for trace in slow_traces if trace.get("traceID") not in {item.get("trace_id") for item in trace_items})
    bottleneck = next((item for item in trace_items if item.get("span_service") and item.get("span_operation")), {})
    pods, logs = await asyncio.gather(pod_evidence(), log_evidence())
    fingerprint = {
        "workload": "incident-api",
        "dominant_signal": dominant,
        "breached_signals": sorted(item["rule"] for item in breached),
        "metrics": {name: {"mean": item["mean"], "threshold": item["threshold"], "normalized": round(normalized_metric(item), 4), "status": item["status"]} for name, item in metrics.items()},
        "bottleneck": {key: bottleneck.get(key) for key in ("span_service", "span_operation", "pct_of_total_duration") if bottleneck.get(key) is not None},
        "trace_evidence": trace_fingerprint(trace_items),
        "log_categories": log_categories(logs),
        "pod_categories": pod_categories(pods),
        "trend": trend,
        "slope": slope,
        "observation_count": 1,
    }
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "metrics": metrics,
        "traces": trace_items[:20],
        "dominant_signal": dominant,
        "trend": trend,
        "fingerprint": fingerprint,
        "pods": pods,
        "logs": logs,
        "trace_reference": trace_items[0].get("trace_id") if trace_items else await trace_reference(),
        "raw_metrics": ranges,
        "raw_trend": trend_payload,
    }


def is_triggered(rule: Rule, value: float) -> bool:
    return value > rule.threshold if rule.comparison == ">" else value < rule.threshold


async def detect_once() -> None:
    """Keep the background collector read-only; breaches are not incidents."""
    for rule in RULES:
        await prometheus_query(rule.query)


async def detector_loop() -> None:
    while True:
        try:
            await detect_once()
        except Exception:
            logger.exception("incident detection cycle failed")
        await asyncio.sleep(DETECTION_INTERVAL)


class ResolveRequest(BaseModel):
    title: str
    outcome: str


async def llm_diagnosis(incident: dict[str, Any], similar: list[dict[str, Any]], telemetry: dict[str, Any]) -> dict[str, Any]:
    def local_analysis() -> dict[str, Any]:
        breached = [item.get("rule", name) for name, item in telemetry.get("metrics", {}).items() if item.get("status") == "BREACHED"]
        signal_text = ", ".join(breached) if breached else "no configured metric crossed its threshold"
        return {
            "analysis_summary": f"Telemetry evidence collected. Signals above threshold: {signal_text}.",
            "possible_root_causes": [],
            "supporting_evidence": ["Review the breached metric rows, failed or slow traces, pod state, and logs."],
            "confidence": None,
            "recommended_action": "Use the evidence in this report to investigate the affected service and dependency.",
            "mode": "local-fallback",
        }

    if LLM_API_BASE and LLM_API_KEY and LLM_MODEL:
        try:
            prompt = json.dumps({"incident": incident, "telemetry": telemetry, "similar_incidents": similar})
            async with httpx.AsyncClient(timeout=45) as http:
                response = await http.post(
                    f"{LLM_API_BASE.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                    json={"model": LLM_MODEL, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [
                        {"role": "system", "content": "Analyze the telemetry evidence, do not assume the detector signal is the root cause, and return JSON with analysis_summary, possible_root_causes, supporting_evidence, confidence, recommended_action."},
                        {"role": "user", "content": prompt},
                    ]},
                )
                response.raise_for_status()
                result = json.loads(response.json()["choices"][0]["message"]["content"])
                result["mode"] = "llm"
                return result
        except Exception as error:
            logger.warning("LLM diagnosis failed; using evidence-only fallback: %s", error)
    return local_analysis()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    task = asyncio.create_task(detector_loop())
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


app = FastAPI(title="Incident Management Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "incident-service"}


@app.get("/api/incidents")
async def list_incidents(status: str | None = None) -> list[dict[str, Any]]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            if status:
                cursor.execute("SELECT id, COALESCE(title, 'Unclassified incident candidate'), scenario, workload, rule, severity, status, first_seen, last_seen, observation_count, trace_reference FROM incidents WHERE status=%s ORDER BY first_seen DESC", (status,))
            else:
                cursor.execute("SELECT id, COALESCE(title, 'Unclassified incident candidate'), scenario, workload, rule, severity, status, first_seen, last_seen, observation_count, trace_reference FROM incidents ORDER BY first_seen DESC")
            keys = ("id", "title", "scenario", "workload", "rule", "severity", "status", "first_seen", "last_seen", "observation_count", "trace_reference")
            return [dict(zip(keys, row)) for row in cursor.fetchall()]


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict[str, Any]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, title, scenario, workload, rule, severity, status, first_seen, last_seen, resolved_at, observation_count, symptoms, evidence, diagnosis_window, trace_reference, diagnosis, resolution_outcome FROM incidents WHERE id=%s", (incident_id,))
            row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    result = dict(zip(("id", "title", "scenario", "workload", "rule", "severity", "status", "first_seen", "last_seen", "resolved_at", "observation_count", "symptoms", "evidence", "diagnosis_window", "trace_reference", "diagnosis", "resolution_outcome"), row))
    result["title"] = result["title"] or "Unclassified incident candidate"
    return result


@app.get("/api/incidents/{incident_id}/similar")
async def similar_incidents(incident_id: str, fingerprint: dict[str, Any] | None = None, limit: int = 5) -> list[dict[str, Any]]:
    incident = await get_incident(incident_id)
    return await find_similar(fingerprint or incident.get("canonical_fingerprint") or {}, limit=limit, exclude_id=incident_id)


def _breaches(fingerprint: dict[str, Any]) -> set[str]:
    explicit = {str(value) for value in fingerprint.get("breached_signals", []) if value}
    if explicit:
        return explicit
    return {
        str(name) for name, value in (fingerprint.get("metrics") or {}).items()
        if isinstance(value, dict) and value.get("status") == "BREACHED"
    }


def _set_similarity(left: Any, right: Any) -> float | None:
    a, b = set(left or []), set(right or [])
    if not a or not b:
        return None
    return len(a & b) / len(a | b)


def fingerprint_similarity(live: dict[str, Any], historical: dict[str, Any]) -> tuple[float, str] | None:
    live_breaches, old_breaches = _breaches(live), _breaches(historical)
    # Healthy/no-data snapshots and historical rows without a real breach are never incidents.
    if not live_breaches or not old_breaches or not (live_breaches & old_breaches):
        return None
    if live.get("dominant_signal") and historical.get("dominant_signal") and live["dominant_signal"] != historical["dominant_signal"]:
        return None

    live_metrics, old_metrics = live.get("metrics") or {}, historical.get("metrics") or {}
    shared = live_breaches & old_breaches
    signal_score = len(shared) / len(live_breaches | old_breaches)
    distances = []
    for name in shared:
        left = float((live_metrics.get(name) or {}).get("normalized") or 0)
        right = float((old_metrics.get(name) or {}).get("normalized") or 0)
        distances.append(min(abs(left - right) / max(max(left, right), 1.0), 1.0))
    metric_score = signal_score * (1.0 - sum(distances) / len(distances))
    components = [(0.45, metric_score)]

    live_trace, old_trace = live.get("trace_evidence") or {}, historical.get("trace_evidence") or {}
    if live_trace.get("failed_or_slow") and old_trace.get("failed_or_slow"):
        trace_scores = [
            1.0 if bool(live_trace.get("failed_count")) == bool(old_trace.get("failed_count")) else 0.0,
            1.0 if live_trace.get("max_duration_bucket") == old_trace.get("max_duration_bucket") else 0.0,
        ]
        service_score = _set_similarity(live_trace.get("services"), old_trace.get("services"))
        operation_score = _set_similarity(live_trace.get("operations"), old_trace.get("operations"))
        if service_score is not None:
            trace_scores.append(service_score)
        if operation_score is not None:
            trace_scores.append(operation_score)
        components.append((0.35, sum(trace_scores) / len(trace_scores)))

    for weight, key in ((0.10, "log_categories"), (0.10, "pod_categories")):
        score = _set_similarity(live.get(key), historical.get(key))
        if score is not None:
            components.append((weight, score))

    score = sum(weight * value for weight, value in components) / sum(weight for weight, _ in components)
    both_trace = live_trace.get("failed_or_slow") and old_trace.get("failed_or_slow")
    same_bottleneck = (
        live.get("bottleneck", {}).get("span_service") == historical.get("bottleneck", {}).get("span_service")
        and live.get("bottleneck", {}).get("span_operation") == historical.get("bottleneck", {}).get("span_operation")
        and live.get("bottleneck", {}).get("span_service") is not None
    )
    if both_trace and not same_bottleneck:
        score = min(score, 0.69)
    tier = "strong_match" if score >= 0.80 and (not both_trace or same_bottleneck) else "partial_match"
    return round(min(score, 1.0), 4), tier


async def find_similar(fingerprint: dict[str, Any], limit: int = 5, exclude_id: str | None = None) -> list[dict[str, Any]]:
    if not _breaches(fingerprint):
        return []
    try:
        with db_connect() as connection:
            with connection.cursor() as cursor:
                clauses = ["status = 'resolved'", "resolution_outcome IS NOT NULL", "canonical_fingerprint IS NOT NULL"]
                params: list[Any] = []
                if exclude_id:
                    clauses.append("id <> %s")
                    params.append(exclude_id)
                params.append(min(limit * 4, 40))
                cursor.execute(f"SELECT id, title, scenario, workload, rule, severity, status, diagnosis, resolution_outcome, canonical_fingerprint FROM incidents WHERE {' AND '.join(clauses)} ORDER BY resolved_at DESC LIMIT %s", tuple(params))
                keys = ("id", "title", "scenario", "workload", "rule", "severity", "status", "diagnosis", "resolution_outcome", "canonical_fingerprint")
                matches = []
                for row in cursor.fetchall():
                    match = dict(zip(keys, row))
                    historical = match.pop("canonical_fingerprint") or {}
                    if isinstance(historical, str):
                        try:
                            historical = json.loads(historical)
                        except json.JSONDecodeError:
                            continue
                    if not isinstance(historical, dict):
                        continue
                    similarity = fingerprint_similarity(fingerprint, historical)
                    if similarity is None:
                        continue
                    match["similarity_score"], match["match_tier"] = similarity
                    match["observation_count"] = historical.get("observation_count", 1)
                    matches.append(match)
                matches.sort(key=lambda item: item["similarity_score"], reverse=True)
                return [match for match in matches if match["similarity_score"] >= 0.70][:limit]
    except Exception as error:
        logger.warning("resolved memory lookup failed; continuing without matches: %s", error)
        return []


@app.post("/api/diagnose")
async def diagnose_current() -> dict[str, str]:
    try:
        telemetry = await diagnosis_telemetry()
    except Exception as error:
        # A broken optional telemetry adapter must not prevent an evidence report.
        logger.exception("diagnosis telemetry collection failed; returning no-data report")
        telemetry = {
            "window_start": (now() - timedelta(minutes=DIAGNOSIS_WINDOW_MINUTES)).isoformat(),
            "window_end": now().isoformat(),
            "metrics": {rule.name: metric_summary(rule, {}) for rule in RULES},
            "traces": [], "dominant_signal": None, "trend": "unavailable",
            "fingerprint": {"workload": "incident-api", "dominant_signal": None, "breached_signals": [], "metrics": {rule.name: {"mean": None, "threshold": rule.threshold, "normalized": 0.0, "status": "NO_DATA"} for rule in RULES}, "trace_evidence": {}, "bottleneck": {}, "log_categories": [], "pod_categories": []},
            "pods": [], "logs": [], "trace_reference": None,
        }
    fingerprint = telemetry["fingerprint"]
    similar = await find_similar(fingerprint)
    diagnosis = await llm_diagnosis({"workload": "incident-api", "rule": telemetry.get("dominant_signal") or "none", "symptoms": {}}, similar, {key: value for key, value in telemetry.items() if key not in {"raw_metrics", "raw_trend"}})
    report_id = str(uuid.uuid4())
    public_telemetry = {key: value for key, value in telemetry.items() if key not in {"raw_metrics", "raw_trend"}}
    insert_error = None
    for attempt in range(2):
        try:
            with db_connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("INSERT INTO diagnosis_reports (id, incident_id, title, window_start, window_end, fingerprint, summary, evidence, diagnosis, similar_incidents) VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s)", (report_id, "Diagnosis report", telemetry["window_start"], telemetry["window_end"], json.dumps(fingerprint, default=str), json.dumps(public_telemetry, default=str), json.dumps(public_telemetry, default=str), json.dumps(diagnosis, default=str), json.dumps(similar, default=str)))
            insert_error = None
            break
        except Exception as error:
            insert_error = error
            if attempt == 0:
                await asyncio.sleep(0.15)
    if insert_error:
        logger.exception("diagnosis report persistence failed")
        raise HTTPException(status_code=503, detail="Diagnosis storage is temporarily unavailable") from insert_error
    return {"report_id": report_id}


def report_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    keys = ("id", "incident_id", "title", "status", "created_at", "updated_at", "window_start", "window_end", "fingerprint", "summary", "evidence", "diagnosis", "similar_incidents")
    return dict(zip(keys, row))


@app.get("/api/diagnosis-reports")
async def list_diagnosis_reports() -> list[dict[str, Any]]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, incident_id, COALESCE(title, 'Diagnosis report'), status, created_at, updated_at, window_start, window_end, fingerprint, summary, evidence, diagnosis, similar_incidents FROM diagnosis_reports ORDER BY created_at DESC")
            return [report_from_row(row) for row in cursor.fetchall()]


@app.get("/api/diagnosis-reports/{report_id}")
async def get_diagnosis_report(report_id: str) -> dict[str, Any]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, incident_id, COALESCE(title, 'Diagnosis report'), status, created_at, updated_at, window_start, window_end, fingerprint, summary, evidence, diagnosis, similar_incidents FROM diagnosis_reports WHERE id=%s", (report_id,))
            row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Diagnosis report not found")
    return report_from_row(row)


class ReportUpdate(BaseModel):
    title: str


@app.patch("/api/diagnosis-reports/{report_id}")
async def update_diagnosis_report(report_id: str, request: ReportUpdate) -> dict[str, Any]:
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE diagnosis_reports SET title=%s, updated_at=now() WHERE id=%s RETURNING id",
                (title[:200], report_id),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Diagnosis report not found")
    return await get_diagnosis_report(report_id)


@app.delete("/api/diagnosis-reports/{report_id}")
async def delete_diagnosis_report(report_id: str) -> dict[str, str]:
    # The FK is intentionally retained/set NULL: deleting a report must never delete resolved memory.
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM diagnosis_reports WHERE id=%s RETURNING id", (report_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Diagnosis report not found")
    return {"id": report_id, "status": "deleted"}


@app.post("/api/diagnosis-reports/{report_id}/cancel")
async def cancel_diagnosis_report(report_id: str) -> dict[str, Any]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE diagnosis_reports SET status='cancelled', updated_at=now() WHERE id=%s AND status='open' RETURNING id", (report_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=409, detail="Only an open diagnosis report can be cancelled")
    return await get_diagnosis_report(report_id)


async def save_resolved_memory(report: dict[str, Any], request: ResolveRequest) -> dict[str, Any]:
    if not request.title.strip() or not request.outcome.strip():
        raise HTTPException(status_code=400, detail="title and outcome are required")
    fingerprint = report.get("fingerprint") or {}
    dominant = fingerprint.get("dominant_signal") or "telemetry"
    symptom_text = json.dumps(fingerprint, sort_keys=True)
    resolved_embedding = vector_literal(await embedding(symptom_text))
    incident_id = str(uuid.uuid4())
    evidence = report.get("evidence") or {}
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO incidents (id, fingerprint, title, scenario, workload, rule, severity, status, first_seen, last_seen, resolved_at, symptoms, evidence, diagnosis, resolution_outcome, canonical_fingerprint, embedding) VALUES (%s, %s, %s, %s, %s, %s, %s, 'resolved', %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)", (incident_id, symptom_text, request.title.strip(), "engineer_resolved_diagnosis", "incident-api", dominant, "high", report["created_at"], report["updated_at"], now(), json.dumps({"summary": "Engineer-resolved telemetry diagnosis"}), json.dumps(evidence), json.dumps(report.get("diagnosis") or {}), request.outcome.strip(), json.dumps(fingerprint), resolved_embedding))
            cursor.execute("UPDATE diagnosis_reports SET incident_id=%s, status='resolved', updated_at=now() WHERE id=%s AND status='open' RETURNING id", (incident_id, report["id"]))
            if not cursor.fetchone():
                raise HTTPException(status_code=409, detail="Diagnosis report is no longer open")
    return await get_incident(incident_id)


@app.post("/api/diagnosis-reports/{report_id}/resolve")
async def resolve_diagnosis_report(report_id: str, request: ResolveRequest) -> dict[str, Any]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, incident_id, status, created_at, updated_at, fingerprint, summary, evidence, diagnosis, similar_incidents FROM diagnosis_reports WHERE id=%s", (report_id,))
            report = cursor.fetchone()
    if not report:
        raise HTTPException(status_code=404, detail="Diagnosis report not found")
    if report[2] != "open":
        raise HTTPException(status_code=409, detail="Diagnosis report is already resolved")
    report_data = dict(zip(("id", "incident_id", "status", "created_at", "updated_at", "fingerprint", "summary", "evidence", "diagnosis", "similar_incidents"), report))
    result = await save_resolved_memory(report_data, request)
    return {"report": await get_diagnosis_report(report_id), "incident": result}


@app.post("/api/admin/reset-memory")
async def reset_memory() -> dict[str, int]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM diagnosis_reports")
            deleted_reports = cursor.rowcount
            cursor.execute("DELETE FROM incidents")
            return {"deleted_incidents": cursor.rowcount, "deleted_reports": deleted_reports}


@app.post("/api/admin/clear-active")
async def clear_active() -> dict[str, int]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM incidents WHERE status='active'")
            return {"deleted_active_incidents": cursor.rowcount}
