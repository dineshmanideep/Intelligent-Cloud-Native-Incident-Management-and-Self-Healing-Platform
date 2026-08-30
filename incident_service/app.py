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
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
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
        'sum(rate(process_cpu_seconds_total{namespace="incident-platform",service="incident-api"}[2m]))',
        0.50,
        ">",
        "high",
        "API process CPU is above the demo threshold",
    ),
    Rule(
        "high_memory",
        'sum(container_memory_working_set_bytes{namespace="incident-platform",pod=~"incident-api-.*",container!=""}) / clamp_min(sum(container_spec_memory_limit_bytes{namespace="incident-platform",pod=~"incident-api-.*",container!=""}), 1)',
        0.80,
        ">",
        "high",
        "API memory is above 80 percent of its configured limit",
    ),
    Rule(
        "high_latency",
        'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{namespace="incident-platform",service="incident-api"}[2m])))',
        1.0,
        ">",
        "high",
        "API p95 latency is above one second",
    ),
    Rule(
        "error_rate",
        'sum(rate(http_requests_total{namespace="incident-platform",service="incident-api",status=~"5.."}[2m])) / clamp_min(sum(rate(http_requests_total{namespace="incident-platform",service="incident-api"}[2m])), 0.001)',
        0.05,
        ">",
        "high",
        "API HTTP 5xx percentage is above the five percent threshold",
    ),
    Rule(
        "db_pool_exhaustion",
        'max(demo_db_held_connections{namespace="incident-platform",service="incident-api"} / clamp_min(demo_db_pool_capacity{namespace="incident-platform",service="incident-api"}, 1))',
        0.90,
        ">",
        "high",
        "Database connection pool is at least 90 percent occupied",
    ),
    Rule(
        "db_lock_contention",
        'max(demo_db_lock_contention_active{namespace="incident-platform",service="incident-api"})',
        0.5,
        ">",
        "high",
        "Database lock contention mode is active",
    ),
    Rule(
        "dependency_retry_storm",
        'sum(rate(demo_dependency_retries_total{namespace="incident-platform",service="incident-api"}[2m]))',
        0.10,
        ">",
        "high",
        "Downstream dependency retries are above the demo threshold",
    ),
    Rule(
        "api_target_down",
        'sum(up{namespace="incident-platform",service="incident-api"})',
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
        "status": "breached" if mean is not None and breached(mean) else "normal",
        "first_breached_at": datetime.fromtimestamp(first, timezone.utc).isoformat() if first else None,
        "sample_count": len(values),
    }


def normalized_metric(summary: dict[str, Any]) -> float:
    mean = summary.get("mean")
    threshold = float(summary.get("threshold") or 1)
    if mean is None:
        return 0.0
    if summary.get("comparison") == "<":
        return min(1.0, threshold / max(float(mean), 0.000001))
    return min(1.0, max(0.0, float(mean) / threshold))


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
    spans = trace.get("spans", [])
    total = sum(float(span.get("duration", 0)) for span in spans) or 1.0
    bottleneck = max(spans, key=lambda span: float(span.get("duration", 0)), default={})
    process = (trace.get("processes") or {}).get(bottleneck.get("processID"), {})
    tags = {tag.get("key"): tag.get("value") for tag in bottleneck.get("tags", [])}
    return {
        "trace_id": trace.get("traceID"),
        "failed": failed or tags.get("error") is True or tags.get("error") == "true",
        "duration_ms": round(total / 1000, 2),
        "span_service": process.get("serviceName"),
        "span_operation": bottleneck.get("operationName"),
        "pct_of_total_duration": round(float(bottleneck.get("duration", 0)) / total * 100, 2),
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


async def diagnosis_telemetry(incident: dict[str, Any]) -> dict[str, Any]:
    end = now()
    start = end.replace(microsecond=0)
    start = start - timedelta(minutes=DIAGNOSIS_WINDOW_MINUTES)
    ranges = {rule.name: await prometheus_range(rule.query, start, end) for rule in RULES}
    rules_by_name = {rule.name: rule for rule in RULES}
    metrics = {name: metric_summary(rules_by_name[name], payload) for name, payload in ranges.items()}
    breached = [item for item in metrics.values() if item["status"] == "breached" and item.get("first_breached_at")]
    dominant = min(breached, key=lambda item: item["first_breached_at"])["rule"] if breached else incident["rule"]
    trend_start = end - timedelta(hours=TREND_LOOKBACK_HOURS)
    trend_payload = await prometheus_range(rules_by_name[dominant].query, trend_start, end)
    trend, slope = trend_classification(range_values(trend_payload), rules_by_name[dominant].threshold)
    failed_traces = await jaeger_traces(start, end, tags={"error": "true"})
    slow_traces = await jaeger_traces(start, end, min_duration="1s")
    trace_items = [trace_summary(trace, failed=True) for trace in failed_traces]
    trace_items.extend(trace_summary(trace) for trace in slow_traces if trace.get("traceID") not in {item.get("trace_id") for item in trace_items})
    bottleneck = next((item for item in trace_items if item.get("span_service") and item.get("span_operation")), {})
    fingerprint = {
        "workload": incident["workload"],
        "dominant_signal": dominant,
        "metrics": {name: {"mean": item["mean"], "threshold": item["threshold"], "normalized": normalized_metric(item)} for name, item in metrics.items()},
        "bottleneck": {key: bottleneck.get(key) for key in ("span_service", "span_operation", "pct_of_total_duration") if bottleneck.get(key) is not None},
        "trend": trend,
        "slope": slope,
        "observation_count": incident.get("observation_count", 1),
    }
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "metrics": metrics,
        "traces": trace_items[:20],
        "dominant_signal": dominant,
        "trend": trend,
        "fingerprint": fingerprint,
        "pods": await pod_evidence(),
        "logs": await log_evidence(),
        "trace_reference": trace_items[0].get("trace_id") if trace_items else await trace_reference(),
        "raw_metrics": ranges,
        "raw_trend": trend_payload,
        "candidate_started": incident["first_seen"].isoformat() if isinstance(incident.get("first_seen"), datetime) else str(incident.get("first_seen")),
    }


async def db_failure() -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            response = await http.get(f"{INCIDENT_API_URL.rstrip('/')}/api/db-check")
            return response.status_code == 200, f"database endpoint status={response.status_code}"
    except Exception as error:
        return False, f"database endpoint error={error}"


def is_triggered(rule: Rule, value: float) -> bool:
    return value > rule.threshold if rule.comparison == ">" else value < rule.threshold


async def create_or_update(rule: Rule, value: float, raw: dict[str, Any], pods: list[dict[str, Any]], trace_id: str | None) -> None:
    fingerprint = f"{rule.name}:incident-api"
    symptoms = {"summary": rule.symptom, "value": value, "threshold": rule.threshold}
    evidence = {"prometheus": raw, "pods": pods}
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM incidents WHERE fingerprint = %s AND status = 'active'", (fingerprint,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE incidents SET last_seen=now(), observation_count=observation_count+1, evidence=%s, trace_reference=COALESCE(%s, trace_reference) WHERE id=%s",
                    (json.dumps(evidence), trace_id, existing[0]),
                )
            else:
                cursor.execute(
                    """INSERT INTO incidents
                    (id, fingerprint, title, scenario, workload, rule, severity, status, first_seen, last_seen, symptoms, evidence, trace_reference, observation_count, embedding)
                    VALUES (%s, %s, 'Unclassified incident candidate', %s, 'incident-api', %s, %s, 'active', now(), now(), %s, %s, %s, 1, NULL)""",
                    (str(uuid.uuid4()), fingerprint, rule.name, rule.name, rule.severity, json.dumps(symptoms), json.dumps(evidence), trace_id),
                )
                logger.warning("incident detected rule=%s value=%s", rule.name, value)


async def detect_once() -> None:
    pods = await pod_evidence()
    trace_id = await trace_reference()
    triggered: list[tuple[Rule, float, dict[str, Any]]] = []
    for rule in RULES:
        value, raw = await prometheus_query(rule.query)
        if value is not None and is_triggered(rule, value):
            triggered.append((rule, value, raw))

    # A controlled demo failure can make the generic checks fail as a side
    # effect. Keep the incident list focused on the more specific symptom
    # instead of presenting several duplicate root-cause candidates.
    triggered_names = {rule.name for rule, _, _ in triggered}
    if "db_pool_exhaustion" in triggered_names:
        triggered = [item for item in triggered if item[0].name != "db_lock_contention"]
    explicit_demo_rules = {"db_pool_exhaustion", "db_lock_contention", "dependency_retry_storm"}
    triggered = [item for item in triggered if not (
        item[0].name == "database_failure" and triggered_names & explicit_demo_rules
    )]
    for rule, value, raw in triggered:
        await create_or_update(rule, value, raw, pods, trace_id)

    healthy, db_message = await db_failure()
    if not healthy and not (triggered_names & explicit_demo_rules):
        await create_or_update(Rule("database_failure", "database", 0, ">", "high", db_message), 1, {"message": db_message}, pods, trace_id)


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
    if LLM_API_BASE and LLM_API_KEY and LLM_MODEL:
        prompt = json.dumps({"incident": incident, "telemetry": telemetry, "similar_incidents": similar})
        async with httpx.AsyncClient(timeout=45) as http:
            response = await http.post(
                f"{LLM_API_BASE.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={"model": LLM_MODEL, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [
                    {"role": "system", "content": "Return JSON with possible_root_causes (array), probable_root_cause, supporting_evidence, confidence, recommended_action."},
                    {"role": "user", "content": prompt},
                ]},
            )
            response.raise_for_status()
            return json.loads(response.json()["choices"][0]["message"]["content"])
    rule = incident["rule"]
    fallback = {
        "high_cpu": ("API workload saturation", "Process CPU exceeded the configured threshold.", "Scale API replicas and inspect request volume."),
        "high_memory": ("API memory pressure", "API memory exceeded 80 percent of its configured limit.", "Inspect allocation growth, reduce retained state, and restart or scale the API service."),
        "high_latency": ("Slow API or database operation", "The p95 request latency exceeded one second.", "Inspect Jaeger for the slow span and check database health."),
        "error_rate": ("Application errors increased", "The API produced HTTP 5xx responses above the configured rate.", "Inspect API logs and the failing trace, then correct the application or dependency."),
        "api_target_down": ("API replica or scrape target unavailable", "Prometheus reports fewer than two API targets.", "Inspect pod status and allow Kubernetes to recreate the failed pod."),
        "database_failure": ("Database connectivity failure", "The API database health endpoint failed.", "Inspect PostgreSQL and API database connection errors."),
        "db_pool_exhaustion": ("Database connection pool exhaustion", "Held connections consumed at least 90 percent of the API pool while requests were failing or slowing.", "Release blocked connections, increase the pool size, and restart the API service."),
        "db_lock_contention": ("Database lock contention", "Requests waited on a database advisory lock and database-backed latency increased.", "Release the blocking transaction and restart or recover the affected service."),
        "dependency_retry_storm": ("Downstream dependency failure", "Repeated retries indicate that a dependent service is timing out or returning errors.", "Inspect the dependency trace and restore the downstream service or apply bounded retry/backoff."),
    }.get(rule, ("Unknown incident condition", incident["symptoms"]["summary"], "Inspect metrics, logs, and traces manually."))
    return {"possible_root_causes": [fallback[0]], "probable_root_cause": fallback[0], "supporting_evidence": [fallback[1]], "confidence": 0.65, "recommended_action": fallback[2], "mode": "local-fallback"}


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
    fingerprint = fingerprint or incident.get("canonical_fingerprint") or {}
    dominant = fingerprint.get("dominant_signal") or incident["rule"]
    live_metrics = fingerprint.get("metrics", {})
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, title, scenario, workload, rule, severity, status, diagnosis, resolution_outcome, canonical_fingerprint FROM incidents WHERE id <> %s AND status = 'resolved' AND diagnosis IS NOT NULL AND resolution_outcome IS NOT NULL AND canonical_fingerprint->>'dominant_signal' = %s ORDER BY resolved_at DESC LIMIT %s", (incident_id, dominant, min(limit * 4, 40)))
            keys = ("id", "title", "scenario", "workload", "rule", "severity", "status", "diagnosis", "resolution_outcome", "canonical_fingerprint")
            matches = []
            for row in cursor.fetchall():
                match = dict(zip(keys, row))
                historical = match.pop("canonical_fingerprint") or {}
                historical_metrics = historical.get("metrics", {})
                shared = set(live_metrics) & set(historical_metrics)
                score = 0.0 if not shared else 1.0 - sum(abs(float(live_metrics[name].get("normalized", 0)) - float(historical_metrics[name].get("normalized", 0))) for name in shared) / len(shared)
                live_bottleneck = fingerprint.get("bottleneck", {})
                old_bottleneck = historical.get("bottleneck", {})
                same_bottleneck = bool(live_bottleneck and old_bottleneck and live_bottleneck.get("span_service") == old_bottleneck.get("span_service") and live_bottleneck.get("span_operation") == old_bottleneck.get("span_operation"))
                match["similarity_score"] = round(max(0.0, min(1.0, score)), 4)
                match["match_tier"] = "strong_match" if same_bottleneck else "partial_match"
                match["observation_count"] = historical.get("observation_count", 1)
                matches.append(match)
            matches.sort(key=lambda item: item["similarity_score"], reverse=True)
            return [match for match in matches if match["similarity_score"] >= 0.55][:limit]


@app.post("/api/incidents/{incident_id}/diagnose")
async def diagnose_incident(incident_id: str) -> dict[str, Any]:
    incident = await get_incident(incident_id)
    if incident["status"] != "active":
        raise HTTPException(status_code=409, detail="Only active incidents can be diagnosed")
    symptoms = dict(incident["symptoms"] or {})
    symptoms["canonical_text"] = f"incident-api rule={incident['rule']} symptom={symptoms.get('summary', '')}"
    incident["symptoms"] = symptoms
    telemetry = await diagnosis_telemetry(incident)
    fingerprint = telemetry["fingerprint"]
    similar = await similar_incidents(incident_id, fingerprint)
    diagnosis = await llm_diagnosis(incident, similar, {key: value for key, value in telemetry.items() if key not in {"raw_metrics", "raw_trend"}})
    incident["possible_causes"] = diagnosis.get("possible_root_causes", [diagnosis.get("probable_root_cause", "Telemetry anomaly requiring investigation")])
    report_id = str(uuid.uuid4())
    public_telemetry = {key: value for key, value in telemetry.items() if key not in {"raw_metrics", "raw_trend"}}
    with db_connect() as connection:
        with connection.cursor() as cursor:
            snapshot = dict(incident["evidence"] or {})
            snapshot["diagnosis_telemetry"] = telemetry
            cursor.execute("UPDATE incidents SET diagnosis=%s, diagnosis_window=%s, canonical_fingerprint=%s, evidence=%s, symptoms=%s WHERE id=%s", (json.dumps(diagnosis), json.dumps(public_telemetry), json.dumps(fingerprint), json.dumps(snapshot), json.dumps(symptoms), incident_id))
            cursor.execute("INSERT INTO diagnosis_reports (id, incident_id, window_start, window_end, fingerprint, summary, evidence, diagnosis, similar_incidents) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (report_id, incident_id, telemetry["window_start"], telemetry["window_end"], json.dumps(fingerprint), json.dumps(public_telemetry), json.dumps(public_telemetry), json.dumps(diagnosis), json.dumps(similar)))
    incident["diagnosis"] = diagnosis
    incident["symptoms"] = symptoms
    incident["diagnosis_report_id"] = report_id
    incident["diagnosis_window"] = public_telemetry
    incident["evidence"] = {key: value for key, value in snapshot.items() if key != "diagnosis_telemetry"}
    incident["similar_incidents"] = similar
    return incident


def report_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    keys = ("id", "incident_id", "status", "created_at", "updated_at", "window_start", "window_end", "fingerprint", "summary", "evidence", "diagnosis", "similar_incidents")
    return dict(zip(keys, row))


@app.get("/api/diagnosis-reports")
async def list_diagnosis_reports() -> list[dict[str, Any]]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, incident_id, status, created_at, updated_at, window_start, window_end, fingerprint, summary, evidence, diagnosis, similar_incidents FROM diagnosis_reports ORDER BY created_at DESC")
            return [report_from_row(row) for row in cursor.fetchall()]


@app.get("/api/diagnosis-reports/{report_id}")
async def get_diagnosis_report(report_id: str) -> dict[str, Any]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, incident_id, status, created_at, updated_at, window_start, window_end, fingerprint, summary, evidence, diagnosis, similar_incidents FROM diagnosis_reports WHERE id=%s", (report_id,))
            row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Diagnosis report not found")
    return report_from_row(row)


@app.post("/api/diagnosis-reports/{report_id}/cancel")
async def cancel_diagnosis_report(report_id: str) -> dict[str, Any]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE diagnosis_reports SET status='cancelled', updated_at=now() WHERE id=%s AND status='open' RETURNING id", (report_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=409, detail="Only an open diagnosis report can be cancelled")
    return await get_diagnosis_report(report_id)


@app.post("/api/incidents/{incident_id}/resolve")
async def resolve_incident(incident_id: str, request: ResolveRequest) -> dict[str, Any]:
    if not request.title.strip() or not request.outcome.strip():
        raise HTTPException(status_code=400, detail="title and outcome are required")
    incident = await get_incident(incident_id)
    if not incident.get("diagnosis"):
        raise HTTPException(status_code=409, detail="Diagnose the incident before resolving it")
    symptom_text = json.dumps(incident.get("canonical_fingerprint") or incident["symptoms"].get("canonical_text") or {"rule": incident["rule"], "symptom": incident["symptoms"].get("summary", "")}, sort_keys=True)
    resolved_embedding = vector_literal(await embedding(symptom_text))
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE incidents SET title=%s, status='resolved', resolved_at=now(), resolution_outcome=%s, canonical_fingerprint=COALESCE(canonical_fingerprint, '{}'::jsonb), embedding=%s::vector WHERE id=%s RETURNING id", (request.title.strip(), request.outcome.strip(), resolved_embedding, incident_id))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Incident not found")
            cursor.execute("UPDATE diagnosis_reports SET status='resolved', updated_at=now() WHERE incident_id=%s AND status='open'", (incident_id,))
    return await get_incident(incident_id)


@app.post("/api/diagnosis-reports/{report_id}/resolve")
async def resolve_diagnosis_report(report_id: str, request: ResolveRequest) -> dict[str, Any]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT incident_id, status FROM diagnosis_reports WHERE id=%s", (report_id,))
            report = cursor.fetchone()
    if not report:
        raise HTTPException(status_code=404, detail="Diagnosis report not found")
    if report[1] not in {"open", "cancelled"}:
        raise HTTPException(status_code=409, detail="Diagnosis report is already resolved")
    result = await resolve_incident(report[0], request)
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE diagnosis_reports SET status='resolved', updated_at=now() WHERE id=%s", (report_id,))
    return {"report": await get_diagnosis_report(report_id), "incident": result}


@app.post("/api/admin/reset-memory")
async def reset_memory() -> dict[str, int]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM incidents")
            return {"deleted_incidents": cursor.rowcount}


@app.post("/api/admin/clear-active")
async def clear_active() -> dict[str, int]:
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM incidents WHERE status='active'")
            return {"deleted_active_incidents": cursor.rowcount}
