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



-------------

# After the implimentation of the diagnose and resolve


• ## 1. Start the project

  Open a terminal:

  cd /home/dinesh/Desktop/course_projects/cc_project
  source .venv/bin/activate

  Start Minikube:

  minikube start --driver=docker

  Deploy the application:

  ./scripts/deploy-kubernetes.sh

  If monitoring or Jaeger are not already installed:

  ./scripts/install-monitoring.sh
  ./scripts/install-telemetry.sh

  Check everything:

  kubectl get pods -n incident-platform
  kubectl get pods -n monitoring

  All important pods should show Running and Ready.

  ## 2. Open the project

  Find the frontend URL:

  minikube service incident-frontend -n incident-platform --url

  Open the printed URL, usually:

  http://192.168.49.2:30080

  Use this URL for the application demo.

  Do not use localhost:3000 unless you specifically want Grafana.

  ## 3. Open Grafana and Jaeger

  Run Grafana in a separate terminal:

  kubectl port-forward -n monitoring svc/incident-monitoring-grafana 3000:80

  Open:

  http://localhost:3000

  Run Jaeger in another terminal:

  kubectl port-forward -n monitoring svc/incident-jaeger 16686:16686

  Open:

  http://localhost:16686

  Stop port-forwards with:

  Ctrl+C

  ## 4. Recommended demo scenario

  The best first demo is database connection pool exhaustion.

  ### Step 1: Reset the system

  From a terminal:

  node_ip="$(minikube ip)"
  base="http://${node_ip}:30080"

  curl -X POST "$base/api/demo/reset"

  Or click:

  Fix/reset demo scenarios

  on the frontend.

  ### Step 2: Cause the problem

  Click:

  Cause DB pool exhaustion

  or run:

  curl -X POST "$base/api/demo/db-pool-exhaust"

  The API deliberately holds all available database-pool connections.

  Expected behavior:

  - Database-backed requests begin failing
  - /api/items may return HTTP 503
  - Database latency increases
  - CPU remains relatively normal
  - Prometheus records pool occupancy
  - Logs record the scenario
  - Jaeger records affected requests

  Test the affected endpoint:

  curl --max-time 5 "$base/api/items"

  ### Step 3: Wait for detection

  Wait approximately:

  sleep 30

  The detector runs every 15 seconds, and Prometheus needs time to scrape the metrics.

  The frontend refreshes automatically every 15 seconds. You can also click:

  Refresh incidents

  The incident should show:

  - Database pool exhaustion title
  - High severity
  - Active status
  - Scenario name
  - Observation count
  - First-seen and last-seen times
  - Trace reference

  ## 5. Diagnose the incident

  On the incident card, click:

  Diagnose with telemetry + memory

  The system then collects:

  - Five-minute Prometheus metric history
  - Metric values and thresholds
  - Metric trends
  - Kubernetes pod status
  - Recent API logs
  - Jaeger trace reference
  - Previously resolved similar incidents from pgvector

  The LLM is called only at this point, if configured.

  Without an LLM key, the system displays a deterministic local diagnosis such as:

  Probable root cause:
  Database connection pool exhaustion

  Recommended action:
  Release blocked connections, increase the pool size, and restart the API service.

  You can also diagnose through the API:

  curl -X POST \
    "$base/incidents/api/incidents/INCIDENT_ID/diagnose"

  Replace INCIDENT_ID with the actual incident ID.

  ## 6. Resolve the incident

  After diagnosis, click:

  Resolve incident

  Enter:

  Title:
  Database connection pool exhaustion

  Example solution:

  Released blocked connections, increased the pool size, and restarted the API service.

  The system then:

  - Saves the final title
  - Saves the diagnosis
  - Saves metrics, logs, traces, and pod evidence
  - Saves the resolution solution
  - Marks the incident as resolved
  - Makes it available as future RAG memory

  You can also resolve through the API:

  curl -X POST \
    "$base/incidents/api/incidents/INCIDENT_ID/resolve" \
    -H 'content-type: application/json' \
    -d '{
      "title": "Database connection pool exhaustion",
      "outcome": "Released blocked connections, increased the pool size, and restarted the API service."
    }'

  ## 7. Fix the controlled problem

  Click:

  Fix/reset demo scenarios

  or run:

  curl -X POST "$base/api/demo/reset"

  Verify recovery:

  curl "$base/api/items"

  It should return the demo records successfully.

  ## 8. Demonstrate RAG memory

  Run the same scenario again:

  curl -X POST "$base/api/demo/db-pool-exhaust"
  sleep 30

  Then diagnose the new active incident.

  This time, the diagnosis should include the previous resolved incident and its solution:

  Similar incident:
  Database connection pool exhaustion

  Previous solution:
  Released blocked connections, increased the pool size, and restarted the API service.

  This demonstrates:

  First occurrence:
  Detect → diagnose → resolve → save memory

  Second occurrence:
  Detect → diagnose → retrieve previous incident → show previous solution

  ## 9. Other available scenarios

  ### Database lock contention

  Frontend:

  Cause DB lock contention

  API:
  curl -X POST "$base/api/demo/db-lock/start"

  Expected behavior:

  - Database-backed requests become slow
  - CPU remains relatively normal
  - Jaeger shows slow database-related traces
  - Diagnosis suggests database lock contention

  ### Dependency retry storm

  Frontend:

  Cause dependency retry storm

  API:

  curl -X POST "$base/api/demo/dependency-failure"

  Generate requests:

  for i in $(seq 1 10); do
    curl --max-time 5 -sS -o /dev/null \
      "$base/api/demo/downstream" || true
  done

  Expected behavior:

  - Requests retry the dependency
  - Retry metrics increase
  - Logs show retry attempts
  - Requests eventually return HTTP 504
  - Diagnosis identifies downstream timeout/retry behavior

  ## 10. What to show in Grafana and Jaeger

  In Grafana, show:

  - Request count
  - Error rate
  - Request latency
  - CPU usage
  - Database-related scenario metrics
  - Retry metrics

  In Jaeger:

  1. Select service:

  incident-demo-api

  2. Generate an API request.
  3. Open the resulting trace.
  4. Show the FastAPI span and PostgreSQL child span.
  5. Use the trace ID shown on the incident card.

  ## 11. Stop the project

  Stop port-forward terminals with:

  Ctrl+C

  Stop Minikube while preserving data:

  minikube stop

  Start again later:

  minikube start --driver=docker
  ./scripts/deploy-kubernetes.sh

  Do not use:

  minikube delete

  unless you intentionally want to delete the cluster and possibly lose persistent demo data.

  
  The complete handoff is documented in CODEX_HANDOFF.md.


# when the minikube already running with all the services to stop and restart

 There are three different things running:

  1. Minikube cluster
  2. Your application deployments
  3. Monitoring tools and port-forwards

  ### Stop everything temporarily

  Stop port-forwards with:

  Ctrl+C

  Then stop Minikube:

  minikube stop

  This stops the entire Kubernetes cluster but preserves deployments, databases, and persistent volumes.

  ### Restart after minikube stop

  minikube start --driver=docker

  Then redeploy/restart the project:

  cd /home/dinesh/Desktop/course_projects/cc_project
  ./scripts/deploy-kubernetes.sh

  You normally do not need to run the monitoring or telemetry installation scripts again because those resources are preserved.

  ### Check what is running

  Application:

  kubectl get pods -n incident-platform

  Monitoring:

  kubectl get pods -n monitoring

  ### Difference between scripts

  deploy-kubernetes.sh:

  - Builds the API, frontend, and incident-service images
  - Applies application manifests
  - Restarts application deployments
  - Does not install Prometheus or Jaeger from scratch

  install-monitoring.sh:

  - Installs or updates Prometheus and Grafana
  - Run it only for first-time setup or monitoring changes

  install-telemetry.sh:

  - Installs or updates OpenTelemetry Collector and Jaeger
  - Run it only for first-time setup or telemetry changes

  These installation scripts are generally repeatable, but they are not required every time you restart Minikube.

  ### Restart only the application

  If Minikube is already running and you only want to restart the app:

  kubectl rollout restart deployment/incident-api \
    deployment/incident-frontend \
    deployment/incident-service \
    -n incident-platform

  Or simply run:

  ./scripts/deploy-kubernetes.sh

  ### Restart only monitoring

  kubectl rollout restart deployment \
    -n monitoring \
    -l app.kubernetes.io/instance=incident-monitoring

  Usually this is unnecessary.

  ### Start the browser access again

  Frontend:

  minikube service incident-frontend -n incident-platform --url

  Grafana:

  kubectl port-forward -n monitoring svc/incident-monitoring-grafana 3000:80

  Jaeger:

  kubectl port-forward -n monitoring svc/incident-jaeger 16686:16686

  The simplest daily workflow is:

  minikube start --driver=docker
  cd /home/dinesh/Desktop/course_projects/cc_project
  ./scripts/deploy-kubernetes.sh
  minikube service incident-frontend -n incident-platform --url

  Only run the monitoring and telemetry installation scripts again if those services are missing or their configuration has changed.
 