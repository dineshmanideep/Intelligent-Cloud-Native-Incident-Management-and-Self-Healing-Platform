• Proposed Plan


  # Reliable Telemetry Fingerprinting

  ## Summary

  Replace the current permissive similarity scoring with a deterministic, evidence-based fingerprint. Idle or normal diagnoses will
  never match saved incidents. A 500 diagnosis will match only when its actual breached metrics and supporting trace/evidence patterns
  are compatible.

  ## Implementation Changes

  - Add a hard guard in similarity matching:
      - If the current report has no breached metrics, return no matches.
      - If a historical record has no breached metrics, exclude it.
      - Require at least one shared breached signal before calculating similarity.

  - Build a normalized fingerprint from:
      - Breached metric names.
      - Actual two-minute metric means.
      - Threshold-relative values, capped to avoid extreme values dominating.
      - Dominant breach.
      - Trace failure count, slow-trace count, duration bucket, bottleneck service, and operation.
      - Stable log categories such as connection_error, timeout, 5xx, or dependency_error.
      - Stable Kubernetes categories such as pod-not-ready, restart bucket, or crash state.
      - Exclude raw log text, pod names, trace IDs, timestamps, and scenario names.

  - Use weighted similarity:
      - 45% breached metric overlap and normalized metric distance.
      - 35% API trace compatibility: failed/slow state, duration bucket, bottleneck service, and operation.
      - 10% stable logs.
      - 10% Kubernetes health/restart evidence.

  - Apply compatibility rules before scoring:
      - Different dominant breached signals cannot produce a strong match.
      - A diagnosis with API failures cannot strongly match an idle or healthy diagnosis.
      - A diagnosis with a different bottleneck service/operation is at most a weak partial match.
      - Missing Jaeger data is neutral: it neither earns similarity nor automatically rejects an otherwise valid metric match.

  - Require a meaningful minimum score and label results:
      - strong only when breach signals and trace/evidence patterns agree.
      - partial only when metric evidence agrees but optional trace/evidence is missing.
      - Otherwise return no relevant previous memory.

  - Preserve the fingerprint captured at Diagnose time and use that exact fingerprint on Resolve.
  - Keep similarity restricted to records created through Resolve.

  ## API and Failure Handling

  - Ensure /incidents/api/diagnose always returns a report, even when Prometheus, Jaeger, Kubernetes, logs, or LLM integration fails.
  - Convert integration failures into evidence fields such as unavailable/empty data instead of raising HTTP 500.
  - Add defensive handling for malformed or legacy fingerprints so one bad historical row cannot fail diagnosis.
  - Keep demo scenarios and their stop controls unchanged.

  ## Tests

  Add tests covering:

  - Same breached metrics with compatible failed traces produces a strong match.
  - Same metrics but a different bottleneck service/operation cannot be strong.
  - Missing Jaeger data still permits a metric-based partial match.
  - Different log or Kubernetes categories reduce or eliminate similarity appropriately.
  - Raw pod names, trace IDs, timestamps, and scenario labels do not affect matching.
  - Legacy/malformed memory rows are ignored safely.
  - Diagnose remains successful after multiple Resolve operations.
  - Prometheus, Jaeger, Kubernetes, log, and LLM failures each still produce a diagnosis report.
  - Run backend tests, incident-service tests, JavaScript syntax checks, git diff --check, and the Kubernetes end-to-end flow:
    trigger 500 → diagnose → resolve → repeat → diagnose → verify the saved solution appears.

  ## Assumptions

  - “Idle” means no breached metric, including reports containing only NORMAL or NO_DATA.
  - Missing optional telemetry is neutral rather than a mismatch.
  - Stable derived categories from logs and Kubernetes contribute to matching; raw values remain display-only.
  - Existing resolved memory is preserved, but invalid or incomplete fingerprints are excluded from similarity results.


─ Worked for 2m 53s ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 
 
  Implement this plan?
 
› 1. Yes, implement this plan          Switch to Default and start coding.
  2. Yes, clear context and implement  Fresh thread. Context: 3% used.
  3. No, stay in Plan mode             Continue planning with the model.
 
  Press enter to confirm or esc to go back                              