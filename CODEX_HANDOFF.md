# Codex Handoff: Incident Management Platform

Last updated: 2026-08-28.

## Project goal

This repository is a local Kubernetes incident-management demonstration. The target workflow is:

```text
Controlled failure -> metrics/logs/traces -> detector -> active incident
-> Diagnose -> telemetry window + pgvector retrieval + optional LLM
-> Resolve with title and solution -> future occurrence retrieves the solution
```

Detection is deterministic. The LLM is optional and is called only when the user clicks Diagnose. The system works without an API key using deterministic local 64-dimensional embeddings and local fallback diagnosis.

## Architecture

```text
Browser :30080
  -> Nginx incident-frontend
       /api/*       -> incident-api:8000
       /incidents/* -> incident-service:8080

incident-api (2 replicas)
  -> application PostgreSQL
  -> Prometheus metrics and JSON logs
  -> OpenTelemetry Collector -> Jaeger

incident-service
  -> Prometheus instant/range queries
  -> Jaeger recent trace query
  -> Kubernetes pod/log evidence
  -> pgvector incident-memory-postgres
  -> optional OpenAI-compatible LLM
```

Namespaces:

- `incident-platform`: API, frontend, application PostgreSQL, incident service, pgvector PostgreSQL.
- `monitoring`: Prometheus, Grafana, OpenTelemetry Collector, Jaeger.

Kubernetes monitoring URLs use absolute service DNS names with a trailing dot because the cluster DNS search suffix previously caused incorrect resolution.

## Decisions made

- Minikube with the Docker driver is the target environment.
- Python dependencies are installed into `.venv`; container dependencies are installed during image builds.
- Prometheus and Jaeger retain telemetry; the incident service queries history when needed.
- Detection runs every 15 seconds in the backend; the browser refreshes incident data only when Refresh incidents is clicked.
- Repeated observations update `last_seen` and `observation_count`; one failed request does not create one incident per request.
- Active incidents remain neutral candidates. A final root-cause title is entered only during Resolve.
- Long-term similarity memory contains only incidents that were explicitly diagnosed and resolved.
- `POST /incidents/api/admin/reset-memory` deletes all incident records, including resolved RAG memory, without deleting the database volume.
- The current pgvector column is `vector(64)`; external embeddings remain optional.
- LLM diagnosis is manual and optional. The provider must expose an OpenAI-compatible `/chat/completions` endpoint. Native Gemini payloads are not implemented.
- Kubernetes remediation is not automatic. Demo reset endpoints release controlled resources; Resolve records the human solution.
- `incident-api` uses `sessionAffinity: ClientIP` so Cause and Reset requests remain on the same pod during the demo.

## Current implementation

### Existing foundation

- FastAPI API with `/health`, `/api/hello`, `/api/db-check`, `/api/items`, `/api/error`, `/api/delay`, `/api/cpu`, and `/metrics`.
- Application PostgreSQL database.
- Prometheus/Grafana manifests and dashboard.
- OpenTelemetry FastAPI/psycopg instrumentation.
- OpenTelemetry Collector and Jaeger manifests.
- Jaeger database child spans were previously verified.

### Latest additions

- `psycopg_pool` bounded application connection pool.
- Database pool exhaustion: `POST /api/demo/db-pool-exhaust`.
- Database lock contention: `POST /api/demo/db-lock/start`.
- Downstream retry scenario: `POST /api/demo/dependency-failure`, then `GET /api/demo/downstream`.
- Common reset: `POST /api/demo/reset`.
- Prometheus metrics for held connections, capacity, lock mode, dependency failure, and retries.
- True 5xx ratio rule: 5xx requests divided by all requests.
- Rules for CPU, p95 latency, error ratio, pool occupancy, lock contention, retry storm, target availability, and database failure.
- Five-minute Prometheus range collection during diagnosis.
- Kubernetes API log collection with `pods/log` RBAC.
- Incident title, scenario, observation count, diagnosis window, metrics, logs, pod evidence, and trace reference fields.
- Similarity results restricted to resolved incidents with diagnosis.
- Resolve accepts a title and outcome.
- Frontend scenario controls, neutral incident cards, manual Refresh, standalone Diagnose, Resolve/Cancel controls, and memory reset.

## Important files

- `backend/app/config.py`: pool settings.
- `backend/app/db.py`: pool lifecycle, held connections, advisory lock, custom metrics.
- `backend/app/main.py`: scenario endpoints and dependency retries.
- `backend/app/telemetry.py`: JSON logs and OpenTelemetry.
- `backend/requirements.txt`: includes `psycopg[pool,binary]`.
- `incident_service/app.py`: schema migration, detector, telemetry collection, diagnosis, retrieval, resolution APIs.
- `incident_service/tests/test_incident_service.py`: embedding/rule/fallback tests.
- `frontend/index.html`: scenario controls and incident console.
- `frontend/nginx.conf`: `/incidents/` proxy.
- `k8s/00-config.yaml`: pool settings.
- `k8s/02-api.yaml`: API session affinity.
- `k8s/07-incident-service.yaml`: pgvector DB, service, configuration, RBAC.
- `scripts/deploy-kubernetes.sh`: builds images, applies manifests, restarts workloads, waits for rollouts.
- `scripts/setup-python.sh`: installs backend and incident-service dependencies.
- `README.md`: operation and demo notes.

## Commands

### Setup and deployment

```bash
cd /home/dinesh/Desktop/course_projects/cc_project
chmod +x scripts/*.sh
./scripts/check-environment.sh
./scripts/setup-python.sh
minikube start --driver=docker
./scripts/deploy-kubernetes.sh
```

### Verify

```bash
minikube status
kubectl get pods,svc,pvc -n incident-platform
kubectl logs deployment/incident-service -n incident-platform --tail=100
kubectl logs deployment/incident-api -n incident-platform --tail=100
```

### Open the frontend

```bash
minikube service incident-frontend -n incident-platform --url
```

Open the printed URL, normally `http://192.168.49.2:30080`. `localhost:3000` is normally Grafana when Grafana is port-forwarded, not the Kubernetes frontend.

### Monitoring and tracing

```bash
./scripts/install-monitoring.sh
./scripts/install-telemetry.sh
kubectl port-forward -n monitoring svc/incident-monitoring-grafana 3000:80
kubectl port-forward -n monitoring svc/incident-jaeger 16686:16686
```

Run port-forwards in separate terminals and stop them with `Ctrl+C`.

### Incident API and scenarios

```bash
node_ip="$(minikube ip)"
base="http://${node_ip}:30080"
curl "$base/incidents/health"
curl "$base/incidents/api/incidents"
curl "$base/incidents/api/incidents?status=active"
curl -X POST "$base/api/demo/db-pool-exhaust"
curl -X POST "$base/api/demo/db-lock/start"
curl -X POST "$base/api/demo/dependency-failure"
curl -X POST "$base/api/demo/reset"
```

Pool and lock scenarios affect `/api/items`. Dependency failure affects `/api/demo/downstream`:

```bash
for i in $(seq 1 10); do curl --max-time 5 -sS -o /dev/null "$base/api/demo/downstream" || true; done
```

Wait 30–45 seconds after causing a scenario so Prometheus can scrape samples and the 15-second detector can run.

### Diagnose and resolve

```bash
id="INCIDENT_ID"
curl -X POST "$base/incidents/api/incidents/$id/diagnose"
curl -X POST "$base/incidents/api/incidents/$id/resolve" \
  -H 'content-type: application/json' \
  -d '{"title":"Database connection pool exhaustion","outcome":"Released blocked connections, increased the pool size, and restarted the API service."}'
```

Never put `$(minikube ip)` inside a large background loop; that starts many Minikube inspections and can overload Docker. Resolve it once and use batches of ten requests.

## Configuration and LLM behavior

Host-running incident-service defaults:

```env
INCIDENT_DB_HOST=localhost
INCIDENT_DB_PORT=5433
INCIDENT_DB_NAME=incident_memory
INCIDENT_DB_USER=incident_user
INCIDENT_DB_PASSWORD=incident_password
PROMETHEUS_URL=http://localhost:9090
JAEGER_URL=http://localhost:16686
INCIDENT_API_URL=http://localhost:8000
DETECTION_INTERVAL_SECONDS=15
LLM_API_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
EMBEDDING_API_BASE_URL=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
```

Inside Kubernetes, use the values in `k8s/07-incident-service.yaml`, not localhost.

Leave embedding variables empty for the current setup. The local embedding is deterministic and matches `vector(64)`. External embedding models commonly return 1536 dimensions and require a deliberate schema migration.

The LLM is called only by `POST /api/incidents/{id}/diagnose`. Empty LLM variables use local fallback diagnosis. Current code supports OpenAI-compatible providers, not native Gemini request/response formats.

## Verification completed

Local tests passed:

```text
7 passed
```

Kubernetes verification passed after restarting Minikube:

- API, frontend, both PostgreSQL services, and incident service became Ready.
- Pool trigger returned `held_connections=8` and `pool_capacity=8`.
- `/api/items` returned HTTP 503 during pool exhaustion.
- Lock contention caused `/api/items` to time out.
- Reset restored `/api/items` successfully.
- The detector created a `db_pool_exhaustion` incident.
- Diagnose returned local fallback mode and a five-minute telemetry snapshot containing metrics, logs, pods, and trace fields.
- Diagnose returned similar incidents from pgvector.
- Resolve stored the title and solution and marked the incident resolved.

## Known issues and unfinished work

1. **Correlated incidents:** pool exhaustion also holds an advisory lock and can produce `db_lock_contention` and `database_failure` incidents. Add correlation precedence so the primary pool incident contains secondary evidence instead of creating confusing extra active incidents. Recommended precedence: pool exhaustion, lock contention, generic database failure.

2. **Persistent old active incidents:** Reset releases demo resources but does not resolve incident rows. Old active records from testing can clutter the UI. Add a clearly labelled demo-only cleanup operation or resolve them manually; do not delete the pgvector PVC casually.

3. **Automatic recovery:** Reset does not automatically resolve incidents. Manual Resolve is intentional. A later phase can add recovery observation and a separate recovered state.

4. **External embeddings:** `embedding()` exists, but current creation/similarity code primarily uses `local_embedding()`. Complete provider use consistently only after deciding dimension and failure behavior.

5. **Native Gemini:** Not implemented. Add a provider adapter if native Gemini REST support is required.

6. **Frontend security/presentation:** Incident titles use `innerHTML` and evidence is shown as JSON. Escape values and render structured fields/charts before production use.

7. **Database pool integration coverage:** Existing tests avoid database routes. Add lifespan-aware integration tests with test PostgreSQL for pool exhaustion, lock reset, and dependency scenario behavior.

## Exactly what to do next

1. Implement incident correlation/suppression so one scenario produces one primary incident.
2. Add safe demo-only cleanup for stale active incidents without deleting historical memory.
3. Run each scenario twice: reset, cause, detect, diagnose, resolve, cause again, diagnose again.
4. Confirm the second diagnosis returns the first run's title and solution from pgvector.
5. Verify the frontend at the NodePort URL visibly shows thresholds, telemetry window, logs, trace ID, similar incidents, Diagnose, and Resolve.
6. If an external LLM is needed for evaluation, configure and test its OpenAI-compatible endpoint while retaining fallback.
7. Only after repeatability is proven, consider native Gemini, automatic recovery, authentication, alert routing, charts, and remediation.

## Clean stop/start

Stop port-forwards with `Ctrl+C`. Stop Minikube without deleting data:

```bash
minikube stop
minikube start --driver=docker
./scripts/deploy-kubernetes.sh
```

Do not use `minikube delete` or delete namespaces unless intentionally resetting persistent data.
