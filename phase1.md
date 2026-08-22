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
