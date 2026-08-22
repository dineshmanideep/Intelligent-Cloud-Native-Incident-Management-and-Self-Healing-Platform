#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if ! minikube status --format='{{.Host}}' 2>/dev/null | grep -q '^Running$'; then
  echo "Minikube is not running. Start it with: minikube start --driver=docker" >&2
  exit 1
fi

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/00-config.yaml
kubectl apply -f k8s/06-otel.yaml

echo "Waiting for Jaeger and the OpenTelemetry Collector..."
kubectl rollout status deployment/incident-jaeger -n monitoring --timeout=180s
kubectl rollout status deployment/incident-otel-collector -n monitoring --timeout=180s

echo "Rebuilding the telemetry-enabled API image..."
minikube image build -t incident-demo-api:local -f backend/Dockerfile .
kubectl rollout restart deployment/incident-api -n incident-platform
kubectl rollout status deployment/incident-api -n incident-platform --timeout=180s

echo
kubectl get pods,svc -n monitoring -l 'app in (incident-jaeger,incident-otel-collector)'
echo
echo "Jaeger UI: kubectl port-forward -n monitoring svc/incident-jaeger 16686:16686"
