# Phase 1 status

Phase 1 is implemented as a local, Kubernetes-first incident-management MVP.

## Included

- FastAPI demo API with health, database, CPU, latency, error, and metrics endpoints.
- Prometheus, Grafana, OpenTelemetry Collector, and Jaeger deployment manifests.
- Automatic incident detection for CPU, latency, 5xx rate, target availability, and database failures.
- Fingerprint-based deduplication of active incidents.
- PostgreSQL with `pgvector` for incident history and similarity lookup.
- Jaeger trace references and Prometheus evidence attached to incidents.
- Rule-based diagnosis that works without an external API key.
- Optional OpenAI-compatible diagnosis provider through environment configuration.
- Incident list, diagnosis, and resolution endpoints, plus the frontend incident panel.

## Phase 1 boundary

Diagnosis is advisory. Automatic Kubernetes remediation, alert routing, authentication,
and production-grade retention policies are intentionally deferred to later phases.

## Verification flow

```bash
./scripts/deploy-kubernetes.sh
kubectl get pods,svc,pvc -n incident-platform
curl "http://$(minikube ip):30080/incidents/api/incidents"
```

Generate a controlled error incident:

```bash
for i in $(seq 1 10); do
  curl -s -o /dev/null "http://$(minikube ip):30080/api/error"
done
sleep 20
curl "http://$(minikube ip):30080/incidents/api/incidents?status=active"
```

Use the returned incident ID for diagnosis and resolution:

```bash
curl -X POST "http://$(minikube ip):30080/incidents/api/incidents/ID/diagnose"
curl -X POST "http://$(minikube ip):30080/incidents/api/incidents/ID/resolve" \
  -H 'content-type: application/json' \
  -d '{"outcome":"Validated the alert and restored the service."}'
```
