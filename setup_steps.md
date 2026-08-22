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



Phase 1 is complete and deployed successfully.

  Implemented:

  - Incident detection using Prometheus metrics
  - Kubernetes pod evidence collection
  - Jaeger trace references
  - PostgreSQL + pgvector incident memory
  - Similar-incident retrieval
  - Automatic fingerprint deduplication
  - Local fallback diagnosis
  - Optional LLM diagnosis configuration
  - Incident resolve endpoint
  - Frontend incident panel
  - Kubernetes deployment automation
  - Python setup dependency installation
  - Phase 1 documentation

  Important files:

  - incident_service/app.py
  - k8s/07-incident-service.yaml
  - scripts/deploy-kubernetes.sh
  - PHASE1_STATUS.md

  Verified successfully:

  - All Kubernetes deployments running
  - Controlled HTTP 500 incident detected
  - Prometheus evidence captured
  - Jaeger trace ID attached
  - Local diagnosis generated
  - pgvector similar incidents returned
  - Duplicate detections merged into one active incident
  - Incident resolved successfully
  - Backend tests: 4 passed

  Current frontend URL:

  http://192.168.49.2:30080

  Incident API:

  curl http://$(minikube ip):30080/incidents/api/incidents

  Phase 1 is now ready.



  Your variables are fine, but not all are required.

  For the current project:

  Required:

  INCIDENT_DB_HOST=localhost
  INCIDENT_DB_PORT=5433
  INCIDENT_DB_NAME=incident_memory
  INCIDENT_DB_USER=incident_user
  INCIDENT_DB_PASSWORD=incident_password
  PROMETHEUS_URL=http://localhost:9090
  JAEGER_URL=http://localhost:16686
  INCIDENT_API_URL=http://localhost:8000
  DETECTION_INTERVAL_SECONDS=15

  Optional:

  LLM_API_BASE_URL=
  LLM_API_KEY=
  LLM_MODEL=
  EMBEDDING_API_BASE_URL=
  EMBEDDING_API_KEY=
  EMBEDDING_MODEL=

  For the current demo, leave all embedding variables empty. The project already uses a built-in deterministic 64-dimensional embedding
  generator, so pgvector similarity search works without downloading or installing an embedding model.

  For full RAG generation, configure only an LLM:

  LLM_API_BASE_URL=https://api.openai.com/v1
  LLM_API_KEY=your_api_key
  LLM_MODEL=your_supported_model

  You do not need an external embedding model for the demo.

  Important: these localhost values are correct only when running the incident service directly on your computer. Inside Kubernetes, use
  the internal service URLs already defined in k8s/07-incident-service.yaml.

  Also, the database currently uses:

  vector(64)

  Therefore, most external embedding models such as standard 1536-dimensional models cannot be used directly without changing the
  database schema and embedding code. For simplicity and reliable demonstration, keep the built-in 64-dimensional embeddings.

  Recommended setup:

  - Local embeddings: enabled by default
  - External LLM: optional
  - External embeddings: leave disabled
  - DETECTION_INTERVAL_SECONDS=15: keep it
  - Do not commit .env files containing API keys to Git

  This gives you a working retrieval system immediately, and optionally adds LLM-generated answers when an API key is available.
 



 ## all
  Use these commands to stop and restart the existing Kubernetes setup.

  ### Stop the running project

  Stop port-forward commands first with:

  Ctrl+C

  Then stop Minikube:

  minikube stop

  This stops all Kubernetes workloads while preserving the cluster and data.

  ### Start again

  minikube start --driver=docker

  Check the cluster:

  minikube status
  kubectl get nodes
  kubectl get pods -n incident-platform

  Deploy the application and incident service:

  cd /home/dinesh/Desktop/course_projects/cc_project
  ./scripts/deploy-kubernetes.sh

  Start monitoring if needed:

  ./scripts/install-monitoring.sh

  Start Jaeger and OpenTelemetry if needed:

  ./scripts/install-telemetry.sh

  ### Open the frontend

  minikube service incident-frontend -n incident-platform --url

  Or open directly:

  http://$(minikube ip):30080

  ### Open Grafana

  Run in a separate terminal:

  kubectl port-forward -n monitoring svc/incident-monitoring-grafana 3000:80

  Open:

  http://localhost:3000

  ### Open Jaeger

  Run in another terminal:

  kubectl port-forward -n monitoring svc/incident-jaeger 16686:16686

  Open:

  http://localhost:16686

  ### Stop local Docker Compose services

  If you started local services with Docker Compose:

  docker compose down
  docker compose -f compose.incident.yaml down

  Do not delete the Kubernetes namespaces unless you intentionally want to remove the stored incident and database data.
 ------------------------------------------------------------------------------------------------------------
 ---

 Yes, RAG is partially implemented.

  The current project includes:

  - Incident storage in PostgreSQL with pgvector
  - Vector embeddings for incident symptoms
  - Similar-incident retrieval using cosine similarity
  - Historical incidents used as memory
  - Diagnosis endpoint that sends the incident plus similar incidents to an optional LLM

  Without an LLM API key, the system uses a local rule-based diagnosis and still demonstrates retrieval. With an OpenAI-compatible API
  configured, it becomes a complete retrieval-augmented generation flow.

  For the demo, you can show:

  1. Open the frontend dashboard.
  2. Trigger a controlled HTTP 500 error.
  3. Prometheus records the error metrics.
  4. The incident service detects the abnormal error rate.
  5. The incident appears in the frontend incident list.
  6. Jaeger trace information is attached to the incident.
  7. Request diagnosis.
  8. Display:
      - probable root cause
      - supporting evidence
      - recommended action
      - confidence
      - similar historical incidents

  9. Trigger the same issue again and show deduplication.
  10. Resolve the incident and show the resolution outcome.
  11. Open Grafana to show metrics.
  12. Open Jaeger to show the related request traces.

  You can demonstrate these scenarios:

  - HTTP 500 error-rate spike
  - CPU saturation using /api/cpu
  - Slow requests using /api/delay
  - Database failure by temporarily scaling down PostgreSQL
  - API pod failure by deleting an API pod
  - Repeated incidents being grouped together

  How well it works currently:

  - Kubernetes deployment: working
  - Prometheus metrics: working
  - Grafana dashboards: working
  - Jaeger tracing: working
  - Incident detection: working
  - Incident deduplication: working
  - pgvector similarity search: working
  - Local diagnosis: working
  - Optional LLM-based RAG diagnosis: implemented but requires an API key
  - Automatic remediation: not implemented yet; recovery is manual

  The best explanation during the demo is:

  > The system observes metrics, logs, and traces; detects an incident; retrieves similar historical incidents from pgvector; and
  > generates a diagnosis with recommended actions.

  The current implementation is a strong Phase 1 MVP. The main limitation is that the default demo uses deterministic local diagnosis. To
  demonstrate full RAG generation, configure an OpenAI-compatible LLM provider in the incident-service Kubernetes Secret.
