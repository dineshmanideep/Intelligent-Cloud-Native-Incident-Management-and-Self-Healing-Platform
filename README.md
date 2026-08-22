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
