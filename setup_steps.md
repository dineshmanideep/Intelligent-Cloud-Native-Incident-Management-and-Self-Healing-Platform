  Run:

  minikube start \
    --driver=docker \
    --cpus=4 \
    --memory=4096 \
    --disk-size=20g

  Then create the project namespace:

  kubectl create namespace incident-platform
  kubectl config set-context --current --namespace=incident-platform

  Verify everything:

  minikube status
  kubectl get nodes
  kubectl get namespaces
  kubectl get pods
  helm version



  Expected result:

  - Minikube status: Running
  - Node status: Ready
  - Namespace: incident-platform
  - No pods yet is normal






  ## web app steps( in local environment)



  ./scripts/setup-python.sh
  source .venv/bin/activate
  pytest backend/tests

  Then start the local application:

  ./scripts/run-local.sh

  Open:

  - Frontend: http://localhost:3000
  - API docs: http://localhost:8000/docs
  - Metrics: http://localhost:8000/metrics


## Run kuberneties setup
 Implemented:

  - Backend and frontend Dockerfiles
  - Nginx reverse proxy for frontend-to-API communication
  - Kubernetes Deployments and Services
  - PostgreSQL PersistentVolumeClaim
  - ConfigMap and Secret
  - API deployment with 2 replicas
  - Minikube build/deploy script
  - Kubernetes deployment documentation

  Run future deployments with:

  ./scripts/deploy-kubernetes.sh

  Verified successfully:

  - Frontend: 200
  - API health: 200
  - Database check: 200
  - Database query: 200
  - Controlled error: 500
  - PostgreSQL PVC: Bound
  - API replicas: 2/2
  - Deleting an API pod caused Kubernetes to recreate it successfully

  Frontend URL:

  http://192.168.49.2:30080

  The next project step is Step 4: install Prometheus and Grafana and connect the API metrics to a monitoring dashboard.
 

 ## run monitoring setup
 • Step 4 is complete.

  Implemented:

  - Prometheus and Grafana via kube-prometheus-stack
  - API ServiceMonitor
  - Grafana dashboard with request rate, 5xx errors, latency, CPU, memory, pod readiness, and target health
  - Idempotent monitoring installer
  - OCI chart download fallback for reliable installation

  Files added/updated:

  - monitoring/values.yaml
  - k8s/04-api-monitoring.yaml
  - k8s/05-grafana-dashboard.yaml
  - scripts/install-monitoring.sh

  Verification passed:

  - Helm release status: deployed
  - All Prometheus/Grafana pods: Running
  - Prometheus reports 2 API targets
  - Request metrics are available
  - Grafana dashboard exists: Incident Platform Overview

  Access Grafana:

  kubectl port-forward -n monitoring svc/incident-monitoring-grafana 3000:80

  Open http://localhost:3000.

  Retrieve the Grafana password:

  kubectl get secret grafana-admin -n monitoring \
    -o jsonpath='{.data.admin-password}' | base64 -d

  Prometheus:

  kubectl port-forward -n monitoring svc/incident-monitoring-kube-p-prometheus 9090:9090

  The monitoring stack is based on the Prometheus Community Kubernetes stack. Official chart
  (https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)


  The issue was in the dashboard configuration, not Prometheus.

  Prometheus had data and Grafana had the datasource, but the dashboard panels did not explicitly reference the Prometheus datasource. I fixed
  all panels to use datasource UID prometheus.

  Now:

  1. Keep port-forward running:

  kubectl port-forward -n monitoring svc/incident-monitoring-grafana 3000:80

  2. Refresh Grafana with Ctrl+Shift+R.
  3. Open:

  Dashboards → Incident Platform Overview

  4. Set the time range to:

  Last 30 minutes

  5. Click the dashboard refresh button.

  Prometheus currently confirms:

  - 2 API targets
  - API request metrics
  - CPU and memory metrics
  - Kubernetes pod readiness metrics

  The dashboard configuration has been updated and verified; every panel now references Prometheus.


 Step 5 is implemented and verified.

  Added:

  - OpenTelemetry FastAPI instrumentation
  - PostgreSQL tracing through Psycopg
  - OTLP Collector in Kubernetes
  - Jaeger all-in-one
  - Trace-aware JSON logs
  - Frontend traceparent propagation
  - Telemetry installation script

  Files added/updated:

  - backend/app/telemetry.py
  - k8s/06-otel.yaml
  - scripts/install-telemetry.sh
  - backend/requirements.txt

  Verification passed:

  - Backend tests: 4 passed
  - Collector pod: Running
  - Jaeger pod: Running
  - API replicas: 2/2
  - JSON logs contain trace_id and span_id
  - Jaeger contains the database request trace:

  GET /api/items
  SELECT
  GET /api/items http send

  Open Jaeger:

  kubectl port-forward -n monitoring svc/incident-jaeger 16686:16686

  Then visit:

  http://localhost:16686

  Select service:

  incident-demo-api

  The implementation uses OpenTelemetry OTLP export and Python instrumentation.
  OpenTelemetry Python documentation
  (https://opentelemetry.io/docs/languages/python/instrumentation/)
