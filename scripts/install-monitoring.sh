#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

monitoring_namespace="monitoring"
release="incident-monitoring"
chart="oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack"

if ! minikube status --format='{{.Host}}' 2>/dev/null | grep -q '^Running$'; then
  echo "Minikube is not running. Start it with: minikube start --driver=docker" >&2
  exit 1
fi

echo "Creating monitoring namespace..."
kubectl create namespace "$monitoring_namespace" --dry-run=client -o yaml | kubectl apply -f -

if ! kubectl get secret grafana-admin -n "$monitoring_namespace" >/dev/null 2>&1; then
  grafana_password="${GRAFANA_ADMIN_PASSWORD:-}"
  if [[ -z "$grafana_password" ]]; then
    grafana_password="$(openssl rand -hex 16)"
    echo "Generated Grafana password: $grafana_password"
  fi
  kubectl create secret generic grafana-admin \
    --namespace "$monitoring_namespace" \
    --from-literal=admin-user=admin \
    --from-literal="admin-password=$grafana_password"
else
  echo "Grafana admin Secret already exists; keeping its password."
fi

echo "Installing or upgrading kube-prometheus-stack..."
helm upgrade --install "$release" "$chart" \
  --namespace "$monitoring_namespace" \
  --values monitoring/values.yaml \
  --wait \
  --timeout 10m

echo "Applying API ServiceMonitor and Grafana dashboard..."
kubectl apply -f k8s/04-api-monitoring.yaml
kubectl apply -f k8s/05-grafana-dashboard.yaml

echo "Waiting for monitoring workloads..."
kubectl rollout status deployment/"$release"-grafana -n "$monitoring_namespace" --timeout=180s
kubectl rollout status statefulset/prometheus-"$release"-kube-p-prometheus -n "$monitoring_namespace" --timeout=180s

echo
kubectl get pods,svc -n "$monitoring_namespace"
echo
echo "Grafana:    kubectl port-forward -n $monitoring_namespace svc/$release-grafana 3000:80"
echo "Prometheus: kubectl port-forward -n $monitoring_namespace svc/$release-kube-p-prometheus 9090:9090"
echo "Grafana username: admin"
