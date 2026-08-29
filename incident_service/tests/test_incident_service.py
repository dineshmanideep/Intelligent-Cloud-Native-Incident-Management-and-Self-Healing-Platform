import asyncio

from incident_service.app import RULES, llm_diagnosis, local_embedding


def test_local_embedding_is_deterministic_and_64_dimensions() -> None:
    assert local_embedding("database connection pool exhaustion") == local_embedding("database connection pool exhaustion")
    assert len(local_embedding("database connection pool exhaustion")) == 64


def test_rules_include_distinct_controlled_scenarios() -> None:
    names = {rule.name for rule in RULES}
    assert {"db_pool_exhaustion", "db_lock_contention", "dependency_retry_storm"} <= names
    assert "/ clamp_min" in next(rule.query for rule in RULES if rule.name == "error_rate")


def test_fallback_diagnosis_explains_pool_exhaustion() -> None:
    incident = {"rule": "db_pool_exhaustion", "symptoms": {"summary": "pool full"}}
    result = asyncio.run(llm_diagnosis(incident, [], {}))
    assert result["mode"] == "local-fallback"
    assert "pool" in result["probable_root_cause"].lower()
    assert result["possible_root_causes"]
