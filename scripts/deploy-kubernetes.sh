#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

namespace="incident-platform"

if ! minikube status --format='{{.Host}}' 2>/dev/null | grep -q '^Running$'; then
  echo "Minikube is not running. Start it with: minikube start --driver=docker" >&2
  exit 1
fi

echo "Building images inside Minikube..."
minikube image build -t incident-demo-api:local -f backend/Dockerfile .
minikube image build -t incident-demo-frontend:local frontend/

echo "Ensuring namespace exists..."
kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -

echo "Applying Kubernetes resources..."
kubectl apply -f k8s/ -n "$namespace"

echo "Waiting for deployments..."
kubectl rollout status deployment/incident-postgres -n "$namespace" --timeout=180s
kubectl rollout status deployment/incident-api -n "$namespace" --timeout=180s
kubectl rollout status deployment/incident-frontend -n "$namespace" --timeout=180s

echo
kubectl get pods,svc,pvc -n "$namespace"
echo
echo "Frontend URL: $(minikube service incident-frontend -n "$namespace" --url)"
echo "API port-forward: kubectl port-forward -n $namespace service/incident-api 8000:8000"

