 # Step 1 — Set Up the Local Kubernetes Environment
  
  ## Summary
  
  Prepare this Manjaro x86_64 machine for the project using Minikube with Docker as the container runtime. Install and verify the required tools, start a dedicated cluster, and create the incident-platform namespace.
  
  ## Implementation Changes
  
  - Install missing tools:
      - kubectl
      - helm
      - minikube
  
  - Verify the existing Docker installation and resolve Docker daemon access if required.
  - Add a reproducible setup script, such as scripts/setup-cluster.sh, that:
      - Validates Docker, Minikube, kubectl, and Helm.
      - Starts Minikube with the Docker driver.
      - Enables the required Minikube addons for later monitoring work.
      - Creates or reuses the incident-platform namespace.
      - Prints cluster and namespace status.
  
  - Add setup documentation describing prerequisites, commands, expected output, and cleanup commands.
  - Do not create application services, monitoring deployments, or incident logic in this step.
  
  ## Verification
  
  The step is complete when:
  
  - Docker is running and accessible by the current user.
  - minikube status reports a healthy cluster.
  - kubectl cluster-info succeeds.
  - The active Kubernetes context points to Minikube.
  - The incident-platform namespace exists and is active.
  - Helm can communicate with the cluster.
  - The setup script can be safely rerun without duplicating or breaking resources.
  
  ## Assumptions
  
  - Minikube is the selected Kubernetes platform.
  - Docker is the Minikube driver.
  - The namespace name is incident-platform.
  - System package installation may require administrator permission.
  - The next step will build the frontend, FastAPI API, and PostgreSQL services.
 

 # Step 2 — Build the Sample Microservices

  ## Summary

  Create a small three-service application:

  - FastAPI backend
  - Simple frontend
  - PostgreSQL database

  The services will run locally first using Python/npm, then later be containerized and deployed to Minikube.

  ## Implementation Changes

  ### Backend

  Create a FastAPI service with:

  - GET /health — service health check
  - GET /api/hello — normal response
  - GET /api/db-check — test PostgreSQL connectivity
  - GET /api/error — controlled HTTP 500 error
  - GET /api/delay?seconds=5 — controlled latency
  - GET /api/cpu?seconds=10 — controlled CPU load
  - GET /metrics — Prometheus metrics endpoint

  Add:

  - Python virtual environment
  - Dependency file with pinned packages
  - Environment-based database configuration
  - Structured logging
  - Basic automated API tests

  ### Database

  Use PostgreSQL for application data.

  Create:

  - Database connection configuration
  - A small sample table
  - Startup database health check
  - Safe connection failure handling

  Database credentials will be read from environment variables and will not be committed to Git.

  ### Frontend

  Create a minimal frontend that:

  - Displays the application status
  - Calls the FastAPI backend
  - Provides buttons for normal response, database check, error, delay, and CPU test
  - Displays the backend response clearly

  Frontend dependencies will be isolated using its local package manager.

  ### Project Structure

  Create an initial structure similar to:

  backend/
    app/
    tests/
    requirements.txt
    .env.example

  frontend/
    src/
    package.json

  database/
    init.sql

  scripts/
    setup-python.sh
    run-local.sh

  .gitignore
  README.md

  ## Local Verification

  Before Kubernetes deployment, verify:

  - FastAPI starts successfully.
  - The frontend can call the backend.
  - The backend connects to PostgreSQL.
  - /health returns successfully.
  - /metrics returns Prometheus-formatted metrics.
  - Controlled error, delay, and CPU endpoints work.
  - Automated backend tests pass.
  - No secrets are committed.

  ## Assumptions

  - Python remains the backend language.
  - FastAPI remains the backend framework.
  - PostgreSQL is the application database.
  - The frontend will be intentionally simple because the project’s main focus is Kubernetes observability and incident management.
  - PostgreSQL will initially run locally for development; Kubernetes deployment will be handled in the following step.


 # Step 3 — Deploy the Application to Minikube

  ## Summary

  Containerize the FastAPI backend and frontend, deploy them with PostgreSQL to the existing incident-platform namespace, and verify that the complete
  application works inside Kubernetes.

  ## Implementation Changes

  ### Containerization

  - Add a backend Dockerfile using Python and Uvicorn.
  - Add a frontend Dockerfile using Nginx to serve the static frontend.
  - Add an Nginx reverse-proxy configuration so browser requests can reach the internal API service without exposing cluster-only DNS names.
  - Add a .dockerignore file.
  - Build images directly into Minikube using minikube image build; no external image registry is required.

  ### Kubernetes Resources

  Create Kubernetes manifests for:

  - PostgreSQL Deployment
  - PostgreSQL PersistentVolumeClaim
  - PostgreSQL Service
  - PostgreSQL initialization ConfigMap
  - API Deployment with two replicas
  - API Service
  - Frontend Deployment
  - Frontend Service
  - Application ConfigMap
  - Database Secret

  Resource requirements:

  - CPU and memory requests for every Deployment
  - CPU and memory limits for every Deployment
  - PostgreSQL password stored in a Secret
  - Non-sensitive configuration stored in a ConfigMap
  - PostgreSQL data stored through a persistent volume

  ### Deployment Workflow

  Add a deployment script that:

  1. Confirms Minikube is running.
  2. Builds the backend and frontend images inside Minikube.
  3. Applies the manifests to incident-platform.
  4. Waits for PostgreSQL, API, and frontend rollouts.
  5. Displays pod, service, and deployment status.
  6. Prints the command for opening the frontend through Minikube.

  ## Verification

  Verify all of the following:

  - PostgreSQL pod is running and ready.
  - Two API replicas are running.
  - Frontend pod is running.
  - Kubernetes services have endpoints.
  - API health endpoint works inside the cluster.
  - Database check and database query endpoints work.
  - Frontend opens through Minikube.
  - Frontend buttons still trigger normal responses, errors, delays, CPU load, and database requests.
  - Deleting one API pod causes Kubernetes to recreate it.
  - API resource requests and limits are visible through Kubernetes.

  ## Test Scenarios

  - Normal request through the frontend.
  - Database request through the API.
  - Controlled HTTP 500 error.
  - Delete one API pod and confirm the second replica remains available.
  - Confirm the deleted pod is automatically recreated.
  - Restart PostgreSQL and verify the application reconnects after PostgreSQL becomes ready.

  ## Assumptions

  - Minikube remains the Kubernetes platform.
  - Application manifests will use standard Kubernetes YAML rather than a Helm chart.
  - Images will be built directly into Minikube rather than pushed to Docker Hub.
  - PostgreSQL will use a single replica for the demo.
  - The API will use two replicas.
  - Monitoring with Prometheus and Grafana will be implemented after the application deployment is stable.


 # Step 4 — Add Prometheus and Grafana Monitoring

  ## Summary

  Install the kube-prometheus-stack Helm chart, configure Prometheus to scrape the FastAPI metrics endpoint, and create a Grafana dashboard for
  Kubernetes and application health. This stack provides Prometheus, Grafana, kube-state-metrics, node-exporter, dashboards, and alerting rules
  through one maintained chart. kube-prometheus-stack documentation
  (https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)

  ## Implementation Changes

  ### Monitoring Installation

  - Create a monitoring namespace.
  - Add the Prometheus Community Helm repository.
  - Install or upgrade kube-prometheus-stack using a committed values file.
  - Keep monitoring resources separate from the application namespace.
  - Configure Grafana persistence only if needed; use a small local-storage volume for Minikube.

  ### API Scraping

  - Label the incident-api Service as scrape-enabled.
  - Add a ServiceMonitor targeting the API Service’s named HTTP port.
  - Configure the scrape path as /metrics.
  - Scrape both API replicas.
  - Confirm Prometheus discovers both API endpoints and reports them as healthy.

  The ServiceMonitor is the Kubernetes-native Prometheus Operator mechanism for selecting Services and defining their scrape endpoint.
  ServiceMonitor reference (https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/values.yaml)

  ### Grafana Dashboard

  Create a dashboard containing:

  - Kubernetes node health
  - Pod availability and restart count
  - API replica availability
  - API CPU usage
  - API memory usage
  - HTTP request rate
  - HTTP 5xx error rate
  - Request latency, including p95 latency
  - PostgreSQL pod health
  - Prometheus target health

  Provision the dashboard through Kubernetes configuration so it is recreated automatically when the monitoring stack is installed.

  ### Access and Credentials

  - Add a script such as scripts/install-monitoring.sh.
  - The script will install or upgrade the Helm release idempotently.
  - Grafana access will use a Kubernetes Secret.
  - The Grafana password will come from GRAFANA_ADMIN_PASSWORD; if it is not provided, the script will generate a local password and print it
    once.

  - Prometheus and Grafana will be accessed through port-forwarding to avoid adding unnecessary public NodePorts.

  ## Verification

  The implementation is complete when:

  - Prometheus and Grafana pods are running in monitoring.
  - kubectl get servicemonitor -A shows the API monitor.
  - Prometheus’s target page shows both API replicas as UP.
  - The Grafana dashboard loads successfully.
  - Normal frontend requests increase the request-rate panel.
  - /api/error increases the 5xx error panel.
  - /api/delay increases the latency panel.
  - /api/cpu increases API CPU usage.
  - Deleting one API pod temporarily reduces capacity and Kubernetes recreates it.
  - The replacement API pod is scraped again after becoming ready.

  ## Planned Files

  - monitoring/values.yaml — Helm configuration
  - monitoring/dashboard.json — Grafana dashboard definition
  - k8s/04-api-monitoring.yaml — ServiceMonitor and monitoring labels
  - scripts/install-monitoring.sh — repository setup, Helm installation, and verification
  - README.md — monitoring access and verification commands

  ## Assumptions

  - Prometheus and Grafana will be installed using kube-prometheus-stack.
  - The API will continue exposing metrics through /metrics.
  - The dashboard will use PromQL queries over the existing request and latency metrics plus Kubernetes-exported metrics.
  - Monitoring will be installed after the application deployment and will not change the current application behavior.
# Step 5 — Add OpenTelemetry Tracing and Structured Logs

  ## Summary

  Add distributed tracing across the FastAPI request path and PostgreSQL calls. Run an OpenTelemetry Collector and Jaeger inside Minikube, then
  expose Jaeger’s UI for trace inspection. The existing Prometheus metrics will remain unchanged.

  OpenTelemetry supports OTLP exporters through configurable endpoints such as ports 4317 for gRPC and 4318 for HTTP. OTLP configuration
  (https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/)

  ## Implementation Changes

  ### FastAPI and PostgreSQL Instrumentation

  Add OpenTelemetry Python dependencies for:

  - OpenTelemetry API and SDK
  - FastAPI instrumentation
  - Psycopg instrumentation
  - OTLP gRPC exporter

  Configure the API to:

  - Set service.name=incident-demo-api.
  - Set deployment environment attributes.
  - Automatically create spans for incoming FastAPI requests.
  - Create database spans for PostgreSQL queries.
  - Propagate W3C trace context.
  - Export spans to the internal Collector Service.
  - Continue exposing the existing /metrics endpoint.

  The instrumentation will be initialized in application code rather than requiring developers to run a separate wrapper command.
  OpenTelemetry’s Python SDK requires an SDK/provider setup before application instrumentation emits telemetry. OpenTelemetry Python
  instrumentation (https://opentelemetry.io/docs/languages/python/instrumentation/)

  ### Frontend Trace Propagation

  Update the frontend request logic so calls to the API carry trace context.

  The initial implementation will:

  - Add browser-side trace context propagation to API fetch requests.
  - Keep the existing frontend behavior and buttons unchanged.
  - Configure the frontend to send OTLP/HTTP data to the Collector through a browser-accessible endpoint if browser spans are enabled.
  - Allow local development and Kubernetes deployment to use different Collector URLs through runtime configuration.

  ### OpenTelemetry Collector

  Deploy an OpenTelemetry Collector in the monitoring namespace with:

  - OTLP gRPC receiver on port 4317
  - OTLP HTTP receiver on port 4318
  - Trace pipeline receiving OTLP data
  - Trace exporter forwarding spans to Jaeger
  - Debug logging enabled initially for troubleshooting
  - Health and readiness probes
  - CPU and memory requests/limits

  The Collector configuration will be stored in a Kubernetes ConfigMap and exposed through a ClusterIP Service.

  ### Jaeger

  Deploy Jaeger all-in-one for the local demonstration:

  - OTLP gRPC ingestion enabled
  - Collector-to-Jaeger trace delivery
  - In-memory storage for the Minikube demo
  - CPU and memory requests/limits
  - Readiness and liveness checks
  - ClusterIP Service for internal access
  - Port-forward command for the Jaeger UI

  Jaeger all-in-one is suitable for this single-node demo, but its default in-memory storage loses traces when the pod restarts. Jaeger
  deployment documentation (https://www.jaegertracing.io/docs/1.76/deployment/)

  ### Structured Logging

  Update API logging to emit structured JSON containing:

  - Timestamp
  - Log level
  - Service name
  - Environment
  - Message
  - HTTP method and path where applicable
  - HTTP status
  - Duration
  - Trace ID
  - Span ID
  - Error details and stack trace when applicable

  Logs will continue to be written to container stdout so they can be inspected with:

  kubectl logs -n incident-platform deployment/incident-api

  ## Planned Files

  - backend/app/telemetry.py — OpenTelemetry initialization
  - backend/app/logging_config.py — JSON logging and trace context injection
  - backend/requirements.txt — OpenTelemetry dependencies
  - k8s/06-otel.yaml — Collector and Jaeger resources
  - monitoring/otel-collector-config.yaml — Collector pipelines
  - scripts/install-telemetry.sh — idempotent deployment and verification
  - README.md — Jaeger access and trace verification instructions

  ## Verification

  The step is complete when:

  - The Collector and Jaeger pods are running.
  - The API starts successfully with telemetry enabled.
  - A frontend request creates a trace visible in Jaeger.
  - A database request shows separate API and PostgreSQL spans.
  - The controlled delay endpoint shows the delay duration in its trace.
  - The controlled error endpoint creates an error span with HTTP status 500.
  - Trace IDs and span IDs appear in API logs.
  - Two API replicas report separate service-instance attributes.
  - Prometheus metrics continue working after telemetry is enabled.
  - Restarting the Collector does not prevent the API from serving requests.

  ## Assumptions

  - Jaeger all-in-one is sufficient for the local presentation environment.
  - Trace data is temporary and does not require persistent storage yet.
  - Prometheus remains responsible for metrics; OpenTelemetry will primarily add traces and trace-correlated logs.
  - Automatic healing, incident detection, and permanent trace storage remain future steps.

## Phase 1 status

  Completed:

  1. Local Docker, Minikube, kubectl, and Helm setup
  2. FastAPI backend
  3. Frontend
  4. PostgreSQL
  5. Kubernetes deployment
  6. Prometheus monitoring
  7. Grafana dashboard
  8. OpenTelemetry API instrumentation
  9. PostgreSQL tracing
  10. OpenTelemetry Collector
  11. Jaeger deployment
  12. Trace-aware JSON logs

  Remaining Phase 1 work:

  ### Step 6 — Controlled incident scenarios

  Implement and document safe ways to create incidents:

  - High CPU using /api/cpu
  - High latency using /api/delay
  - HTTP 500 errors using /api/error
  - Database connection failure or timeout
  - API pod failure using kubectl delete pod

  For every scenario, record:

  Trigger command
  Expected Prometheus evidence
  Expected API log evidence
  Expected Jaeger trace evidence
  Recovery action

  ### Step 7 — Incident detection service

  Create a separate FastAPI service that:

  - Periodically queries Prometheus
  - Checks Kubernetes pod status
  - Detects CPU, latency, errors, restarts, and database failures
  - Creates one incident per active fault
  - Stores incident details
  - Exposes incident list and detail endpoints

  ### Step 8 — Incident memory

  Add PostgreSQL with pgvector for:

  - Historical incidents
  - Symptoms
  - Metrics
  - Logs
  - Root cause
  - Recommended action
  - Recovery outcome

  Add embedding generation and similarity search.

  ### Step 9 — LLM diagnosis

  Send the following to the LLM:

  - Current incident
  - Prometheus evidence
  - Logs
  - Jaeger trace references
  - Kubernetes status
  - Similar historical incidents

  Return:

  - Probable root cause
  - Supporting evidence
  - Confidence
  - Recommended manual recovery

  Automatic healing remains outside Phase 1.

  ### Step 10 — Complete Phase 1 demonstration

  The final Phase 1 demo should show:

  Kubernetes application
          ↓
  Prometheus and Grafana
          ↓
  Controlled incident
          ↓
  Incident detection
          ↓
  Jaeger/log evidence
          ↓
  Similar historical incident
          ↓
  LLM diagnosis
          ↓
  Manual recovery

  ## Fix and verify Jaeger

  Keep Jaeger running in one terminal:

  kubectl port-forward -n monitoring svc/incident-jaeger 16686:16686

  Open:

  http://localhost:16686

  In another terminal, generate a real application request:

  curl http://$(minikube ip):30080/api/items

  Or generate a delayed request:

  curl "http://$(minikube ip):30080/api/delay?seconds=5"

  Or generate an error:

  curl http://$(minikube ip):30080/api/error

  Wait 5–10 seconds, refresh Jaeger, then select:

  Service: incident-demo-api

  For a database trace, use:

  curl http://$(minikube ip):30080/api/items

  You should see spans similar to:

  GET /api/items
  SELECT
  GET /api/items http send

  ## Verify Jaeger without using the UI

  Check available services:

  curl http://localhost:16686/api/services

  Check traces:

  curl "http://localhost:16686/api/traces?service=incident-demo-api&limit=20"

  Check recent API trace logs:

  for pod in $(kubectl get pods -n incident-platform \
    -l app=incident-api \
    -o jsonpath='{.items[*].metadata.name}'); do
    kubectl logs "$pod" -n incident-platform --since=5m |
      grep -E 'api/items|api/delay|api/error|trace_id'
  done

  Check recent Collector logs:

  kubectl logs deployment/incident-otel-collector \
    -n monitoring \
    --since=5m

  Do not rely on the old full Collector log output. The log beginning at 09:28:11 is
  only the Collector startup event. Use --since=5m immediately after generating a
  request.

  Also remember that Jaeger currently uses in-memory storage, so traces disappear
  whenever the Jaeger pod restarts.
 