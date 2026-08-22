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

