# Incident Management Platform

This repository starts with a small cloud-native demo application. Step 1 prepares Minikube; Step 2 provides the local frontend,
FastAPI backend, and PostgreSQL application used by the later observability and incident-management features.

## Local setup

```bash
./scripts/setup-python.sh
./scripts/run-local.sh
```

Open <http://localhost:3000> for the frontend or <http://localhost:8000/docs> for the API documentation.

The frontend supports an alternate API URL through a query parameter, for example:

```text
http://localhost:3000/?api=http://localhost:8000
```

## Useful checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/db-check
curl http://localhost:8000/metrics
source .venv/bin/activate
pytest backend/tests
```

Stop the local database with:

```bash
docker compose down
```

## Kubernetes deployment

With Minikube running, deploy the application into the project namespace:

```bash
./scripts/deploy-kubernetes.sh
```

Open the printed frontend URL. The Nginx frontend proxies `/health` and `/api/*` to the internal FastAPI service.

Useful Kubernetes checks:

```bash
kubectl get pods,svc,pvc -n incident-platform
kubectl logs deployment/incident-api -n incident-platform
kubectl port-forward -n incident-platform service/incident-api 8000:8000
```

## Monitoring

Install Prometheus and Grafana with:

```bash
./scripts/install-monitoring.sh
```

Then open Grafana through a port-forward:

```bash
kubectl port-forward -n monitoring svc/incident-monitoring-grafana 3000:80
```

Open <http://localhost:3000>, sign in as `admin`, and use the generated password printed by the install script.

Prometheus target status can be checked with:

```bash
kubectl get servicemonitor -n incident-platform
kubectl port-forward -n monitoring svc/incident-monitoring-kube-p-prometheus 9090:9090
```

## Tracing

Install OpenTelemetry Collector and Jaeger with:

```bash
./scripts/install-telemetry.sh
```

Open Jaeger with:

```bash
kubectl port-forward -n monitoring svc/incident-jaeger 16686:16686
```

Then visit <http://localhost:16686>, select `incident-demo-api`, and generate a frontend request. Database-backed requests should
show a PostgreSQL child span.

## Incident management

Deploy the Phase 1 incident service and pgvector memory with the application deployment:

```bash
./scripts/deploy-kubernetes.sh
```

The incident API is available through the frontend proxy at:

```bash
curl http://$(minikube ip):30080/incidents/api/incidents
```

Generate an incident, wait for the detector cycle, and request a diagnosis:

```bash
curl "http://$(minikube ip):30080/api/cpu?seconds=20"
curl http://$(minikube ip):30080/incidents/api/incidents
```

The frontend also provides controlled scenarios for database pool exhaustion, database lock contention, and downstream retry
storms. Use the **Cause** buttons, then click **Diagnose current incident** when you want to inspect the latest two minutes.
The current active signal is queried at that moment; if several are active, choose one inline. Open the report, then
**Resolve** it to save the solution. The next run retrieves relevant resolved memory.

The same scenarios are available from the API:

```bash
curl -X POST http://$(minikube ip):30080/api/demo/db-pool-exhaust
curl -X POST http://$(minikube ip):30080/api/demo/db-lock/start
curl -X POST http://$(minikube ip):30080/api/demo/dependency-failure
curl -X POST http://$(minikube ip):30080/api/demo/reset
```

Diagnosis collects a two-minute Prometheus range, recent API logs, pod status, and a Jaeger trace reference. The default
diagnosis is a safe local fallback; the LLM is called only when the Diagnose action is requested. Configure
`LLM_API_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in the incident service Secret/ConfigMap to enable an OpenAI-compatible
diagnosis provider. Kubernetes recovery is intentionally manual; the demo reset endpoints only release controlled resources.
