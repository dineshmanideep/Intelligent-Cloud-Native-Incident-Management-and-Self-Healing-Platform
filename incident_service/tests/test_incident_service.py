import asyncio

from incident_service.app import RULES, llm_diagnosis, local_embedding, metric_summary, trace_summary, trend_classification


def test_local_embedding_is_deterministic_and_64_dimensions() -> None:
    assert local_embedding("database connection pool exhaustion") == local_embedding("database connection pool exhaustion")
    assert len(local_embedding("database connection pool exhaustion")) == 64


def test_rules_include_distinct_controlled_scenarios() -> None:
    names = {rule.name for rule in RULES}
    assert {"db_pool_exhaustion", "db_lock_contention", "dependency_retry_storm"} <= names
    assert "/ clamp_min" in next(rule.query for rule in RULES if rule.name == "error_rate")
    assert "demo_memory_pressure_bytes" in next(rule.query for rule in RULES if rule.name == "high_memory")


def test_fallback_diagnosis_reports_signal_without_root_cause() -> None:
    incident = {"rule": "db_pool_exhaustion", "symptoms": {"summary": "pool full"}}
    result = asyncio.run(llm_diagnosis(incident, [], {"metrics": {"db_pool_exhaustion": {"status": "BREACHED"}}}))
    assert result["mode"] == "local-fallback"
    assert result["possible_root_causes"] == []
    assert "db_pool_exhaustion" in result["analysis_summary"]


def test_metric_summary_uses_window_mean_and_first_breach() -> None:
    rule = next(rule for rule in RULES if rule.name == "high_cpu")
    payload = {"data": {"result": [{"values": [[100, "0.2"], [115, "0.8"], [130, "0.6"]]}]}}
    result = metric_summary(rule, payload)
    assert result["mean"] == 0.533333
    assert result["status"] == "BREACHED"
    assert result["first_breached_at"] is not None


def test_metric_summary_reports_no_data() -> None:
    rule = next(rule for rule in RULES if rule.name == "high_memory")
    result = metric_summary(rule, {"data": {"result": []}})
    assert result["status"] == "NO_DATA"
    assert result["sample_count"] == 0


def test_trace_summary_tolerates_missing_duration() -> None:
    result = trace_summary({"traceID": "trace-1", "spans": [{"duration": None, "tags": []}]})
    assert result["trace_id"] == "trace-1"
    assert result["duration_ms"] == 0.0


def test_trend_classification_handles_sudden_change() -> None:
    trend, slope = trend_classification([(100, 0.1), (115, 0.8)], 0.5)
    assert trend == "sudden"
    assert slope is not None
