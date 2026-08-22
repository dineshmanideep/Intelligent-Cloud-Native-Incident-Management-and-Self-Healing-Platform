- could choose among MiniKube and Kind 
- 
- llm model local or open ai api 
- web app stack too fast api becase easy to impliment open telementary and good with rag 

## steps 
 # Phase 1 Implementation Plan — Mid-Presentation MVP

  ## Summary

  Build a three-service Kubernetes demo on Minikube: a frontend, a FastAPI API, and PostgreSQL. Add Prometheus/Grafana
  monitoring, OpenTelemetry logs and traces, an incident-service with PostgreSQL + pgvector memory, and API-based LLM diagnosis.
  The mid-demo ends with a detected incident and an evidence-based diagnosis; healing remains manual until Phase 2.

  ## Implementation Steps

  1. Set up the local cloud environment
      - Install and verify Docker, Minikube, kubectl, Helm, and Python.
      - Start Minikube and create a dedicated Kubernetes namespace, e.g. incident-platform.
      - Use this cluster as the cloud environment for all demos.

  2. Build the sample microservices
      - Create a simple frontend that calls the FastAPI backend.
      - Create FastAPI endpoints for a normal response, database-backed request, controlled error, controlled latency, and CPU-
        load generation.

      - Use PostgreSQL as the application database so database-timeout incidents can be demonstrated.
      - Containerize frontend and API with Docker.

  3. Deploy the application to Kubernetes
      - Create Kubernetes Deployments and Services for frontend, API, and PostgreSQL.
      - Configure API with at least two replicas to demonstrate availability and scaling readiness.
      - Set CPU and memory requests/limits on every workload.
      - Use ConfigMaps for non-secret configuration and a Secret for the database password.
      - Confirm pods, services, inter-service communication, and browser/API access work.

  4. Install monitoring
      - Install Prometheus and Grafana with Helm in the Minikube cluster.
      - Expose FastAPI Prometheus metrics, including request count, error count, response latency, and process CPU/memory usage.
      - Configure Prometheus to scrape the API metrics endpoint.
      - Build a Grafana dashboard showing pod health, CPU, memory, API request rate, error rate, and latency.

  5. Add OpenTelemetry observability
      - Instrument FastAPI with OpenTelemetry automatic/manual tracing.
      - Propagate trace context from frontend to API and API to PostgreSQL.
      - Send traces to a lightweight OpenTelemetry Collector and a trace backend such as Jaeger.
      - Configure structured application logs to include service name, severity, timestamp, trace ID, and error message.

  6. Create controlled incident scenarios
      - Add safe demo-only API endpoints or scripts to trigger:
          - High CPU load
          - Delayed API responses
          - HTTP 500 errors
          - Database connection failure/timeout
          - Pod failure through a controlled pod deletion

      - Document the trigger command and expected dashboard/log evidence for each scenario.

  7. Build the incident-detection service
      - Implement a separate FastAPI incident service that periodically queries Prometheus and Kubernetes status.
      - Detect Phase 1 conditions: high CPU, high latency, error-rate increase, pod restart/failure, and database connectivity
        errors.

      - Deduplicate repeated alerts so one active fault produces one incident instead of many duplicates.
      - Store each detected incident with the workload, timestamp, severity, trigger rule, current metrics, logs, and trace
        reference.

  8. Implement incident memory with PostgreSQL and pgvector
      - Enable pgvector in the incident-service PostgreSQL database.
      - Store resolved/sample incidents with symptoms, evidence summary, root cause, recommended action, and outcome.
      - Generate embeddings through a general API-based embedding provider.
      - For each new incident, retrieve the most similar historical incident records using vector similarity search.

  9. Add LLM-based diagnosis
      - Send the current incident summary, Prometheus evidence, relevant logs/traces, Kubernetes status, and retrieved incident
        memory to an API-based LLM.

      - Require a structured response containing: probable root cause, supporting evidence, confidence, and recommended manual
        recovery action.

      - Display diagnosis in the incident-service API and optionally a small frontend incident page.
      - Do not permit the LLM to call Kubernetes or execute recovery commands in Phase 1.

  10. Prepare the mid-presentation flow

  - Show the running Kubernetes services and replicas.
  - Open Grafana and Jaeger to show normal observability.
  - Trigger one prepared incident, preferably API CPU/latency or database timeout.
  - Show abnormal metrics, related logs/traces, the incident record, similar incident retrieval, and LLM diagnosis.
  - Apply the recommended recovery manually, such as deleting a failed pod or scaling the API deployment, and show the workload
    recovering.

  ## Interfaces and Data

  - Demo API: normal, database, error, latency, and CPU-load endpoints; Prometheus /metrics endpoint.
  - Incident service: endpoints to list incidents, inspect an incident, retrieve similar incidents, and request diagnosis.
  - Incident record: incident ID, affected workload, status, severity, timestamps, telemetry evidence, diagnosis, recommendation,
    and later resolution outcome.

  - Phase 1 recovery boundary: recommendations are shown to the operator; automated healing is reserved for Phase 2.

  - All three services deploy and communicate inside Minikube.
  - Prometheus scrapes API metrics and Grafana displays health, CPU, latency, and errors.
  - A controlled incident visibly changes metrics and/or logs/traces.
  - The incident service records the event exactly once while it remains active.
  - Similar historical incidents are retrieved from pgvector.
  - The LLM returns a diagnosis supported by supplied evidence and a safe recovery recommendation.
  - Manual recovery restores pod health and normal metrics.

  ## Assumptions

  - Minikube is the Phase 1 Kubernetes platform.
  - The demo application uses Python FastAPI and PostgreSQL.
  - A general API-based embedding and LLM provider will be configured through environment variables/Kubernetes Secrets; no key is
    committed to the repository.

  - eBPF, Cilium/Hubble, automatic Kubernetes recovery, recovery verification, and learning from automated outcomes are Phase 2
    features.
