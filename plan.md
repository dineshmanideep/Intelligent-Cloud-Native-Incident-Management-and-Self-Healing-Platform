  # Intelligent Cloud-Native Incident Management and Self-Healing Platform

  ## Project Overview

  This project builds an open-source cloud-native platform that monitors containerized applications, detects incidents, diagnoses
  their probable root cause using historical incident knowledge, and performs controlled recovery actions.

  The complete workflow is:

  **Observe → Detect → Diagnose → Heal → Verify → Learn**

  The project is divided into two implementation phases. Phase 1 creates the cloud-native monitoring and AI diagnosis foundation.
  Phase 2 adds eBPF-based deep observability and automated self-healing.

  ---

  ## Cloud Computing Concepts Demonstrated

  This is a cloud computing project because the application runs as distributed containerized workloads managed by Kubernetes.

  The project demonstrates:

  - **Containerization:** Docker packages each application service.
  - **Container orchestration:** Kubernetes deploys and manages containers.
  - **Scalability:** Kubernetes Deployments can increase or decrease pod replicas.
  - **High availability:** Multiple replicas keep the application available if one pod fails.
  - **Fault tolerance:** Kubernetes recreates failed containers and pods.
  - **Resource management:** CPU and memory requests/limits are assigned to workloads.
  - **Service discovery and networking:** Kubernetes Services enable communication between microservices.
  - **Monitoring and observability:** Metrics, logs, traces, and later eBPF telemetry monitor the cloud environment.
  - **Automated recovery:** Kubernetes API actions restart, scale, or replace unhealthy workloads.

  ---

  # Phase 1: Cloud-Native Monitoring and Incident Intelligence

  ## Goal

  Build a Kubernetes-based application environment that can be monitored, can generate incidents, and can diagnose incidents using
  RAG and historical incident memory.

  ## Implementation Steps

  ### 1. Create a Containerized Sample Application

  Create a simple microservices application, for example:

  - Frontend service
  - API service
  - Database service

  Containerize each service using Docker.

  ### 2. Deploy the Application on Kubernetes

  Deploy the application to a local Kubernetes cluster such as Minikube or Kind.

  Create:

  - Kubernetes Deployments
  - Kubernetes Services
  - ConfigMaps and Secrets if required
  - CPU and memory resource limits
  - Multiple replicas for selected services

  ### 3. Add Cloud Monitoring

  Install Prometheus and Grafana.

  Collect monitoring data such as:

  - Pod CPU and memory usage
  - Pod restart count
  - Pod status
  - Request rate
  - Error rate
  - Response latency
  - Node health

  Create Grafana dashboards to show the health of the cloud-native application.

  ### 4. Add Logs and Traces

  Use OpenTelemetry to collect application logs and distributed traces.

  The system should identify events such as:

  - HTTP 500 errors
  - Database connection timeout
  - Service unavailable
  - High response latency
  - Container crash
  - Out-of-memory error

  ### 5. Detect Incidents

  Create an incident detection service.

  It should detect conditions such as:

  - CPU usage above a configured threshold
  - Memory usage above a configured threshold
  - Pod restart or crash
  - Increased error rate
  - High request latency
  - Database connection failure

  When a condition is detected, create an incident record.

  ### 6. Store Incident Information

  Store incidents in PostgreSQL.

  Each incident record should include:

  - Incident ID
  - Time of occurrence
  - Affected service or pod
  - Symptoms
  - Metrics and logs
  - Detected severity
  - Root cause, when known
  - Recommended solution
  - Recovery outcome

  ### 7. Implement RAG-Based Diagnosis

  Convert previous incident descriptions into embeddings and store them using pgvector.

  For every new incident:

  1. Collect its logs, metrics, traces, and affected workload details.
  2. Retrieve similar previous incidents.
  3. Send the current incident context and similar incidents to the LLM.
  4. Receive a probable root cause and recommended recovery action.

  ## Phase 1 Output

  At the end of Phase 1, the platform should be able to:

  - Run a distributed application on Kubernetes.
  - Monitor workloads using Prometheus and OpenTelemetry.
  - Detect common cloud incidents.
  - Store incidents as historical knowledge.
  - Retrieve similar past incidents using RAG.
  - Provide an AI-generated diagnosis and recovery recommendation.

  ---
---

  # Mid-Presentation Demo: Phase 1 Completion

  The mid-presentation demonstrates that the core cloud-computing platform is working before eBPF and automated self-healing are
  added.

  ## What We Will Present

  ### 1. Cloud-Native Application Deployment

  Show the sample application running on Kubernetes.

  Demonstrate:

  - Multiple containerized services running as pods
  - Kubernetes Deployments and Services
  - Multiple replicas for availability
  - CPU and memory resource limits
  - Kubernetes dashboard or `kubectl get pods` output

  This proves that the project uses container orchestration and distributed cloud-native workloads.

  ### 2. Monitoring Dashboard

  Show Prometheus and Grafana dashboards.

  Demonstrate:

  - CPU and memory utilization
  - Pod status and restart count
  - Request rate
  - Error rate
  - Response latency
  - Node or cluster health

  This proves that the platform can observe and monitor cloud workloads.

  ### 3. Incident Generation and Detection

  Intentionally create one or more controlled incidents, such as:

  - Increase CPU load on an API service
  - Stop or crash a pod
  - Create a high-latency condition
  - Cause a database connection timeout
  - Generate HTTP 500 errors

  Show that the incident detection service identifies the abnormal condition and creates an incident record.

  ### 4. Logs and Traces

  Show application logs and distributed traces collected through OpenTelemetry.

  Demonstrate how the platform identifies:

  - Which service failed
  - Which request became slow
  - Error messages such as database timeout or service unavailable
  - The path of a request across services

  ### 5. Incident Memory and RAG Diagnosis

  Show previously stored incident records in PostgreSQL.

  For a newly generated incident:

  1. Collect current metrics, logs, traces, and Kubernetes workload details.
  2. Retrieve a similar historical incident using vector search.
  3. Send both the current incident and retrieved history to the LLM.
  4. Display the probable root cause and recommended recovery action.

  Example output:

  > Incident detected: API latency is high and database timeout errors are increasing.
  > Similar incident found: Database connection overload.
  > Recommended action: Scale the API workload or restart the affected database client pod.

  ## Mid-Presentation Result

  At the end of the mid-presentation, the platform will demonstrate:

  - A containerized microservices application deployed on Kubernetes.
  - Core cloud computing concepts: orchestration, scalability, resource management, availability, and fault tolerance.
  - Monitoring through Prometheus and Grafana.
  - Logs and traces through OpenTelemetry.
  - Detection of a real or simulated incident.
  - Historical incident storage in PostgreSQL.
  - RAG-based retrieval of similar incidents.
  - LLM-based diagnosis and a recommended recovery action.

  ## Not Included in the Mid-Presentation

  The following features are planned for Phase 2:

  - eBPF-based network and process telemetry
  - TCP retransmission and deep network analysis
  - Automated Kubernetes recovery actions
  - Self-healing verification and learning loop

  During the mid-presentation, the system will recommend an action, but recovery will be demonstrated manually. In the final
  presentation, the platform will execute safe recovery actions automatically through the Kubernetes API.

  ---

  This gives your mid presentation a complete, convincing story: Kubernetes cloud deployment → monitoring → incident detection →
  RAG/LLM diagnosis. Phase 2 then becomes a clear upgrade: eBPF evidence + automatic self-healing.

  # Phase 2: eBPF-Enhanced Observability and Self-Healing

  ## Goal

  Enhance diagnosis with eBPF-level process and network telemetry, then automatically recover affected Kubernetes workloads.

  ## Implementation Steps

  ### 1. Add eBPF-Based Observability

  Use Cilium, Hubble, or another eBPF tool to collect deeper telemetry.

  Collect information such as:

  - Service-to-service network traffic
  - TCP connections
  - TCP retransmissions
  - Network latency
  - Connection failures
  - Process-level activity
  - DNS requests, if available
  - Network flow between Kubernetes services

  ### 2. Enrich Incident Context

  Combine the eBPF signals with Phase 1 telemetry:

  - Prometheus metrics
  - Application logs
  - Distributed traces
  - Kubernetes pod status
  - Historical incident records

  For example, instead of only detecting high latency, the platform can identify that a particular service has increased TCP
  retransmissions or repeated failed database connections.

  ### 3. Improve RAG and LLM Diagnosis

  Pass the enriched eBPF evidence to the RAG and LLM diagnosis pipeline.

  The LLM should provide:

  - Probable root cause
  - Supporting evidence
  - Confidence level
  - Recommended recovery action

  Example:

  > Payment service is slow because database communication has high TCP retransmissions and repeated connection timeouts.
  Recommended action: restart the affected workload and verify database connectivity.

  ### 4. Implement a Safe Self-Healing Engine

  Create a healing service that uses the Kubernetes API.

  Supported recovery actions can include:

  - Restart an unhealthy pod
  - Delete a failed pod so Kubernetes recreates it
  - Scale a Deployment when CPU usage remains high
  - Roll out a Deployment restart
  - Reschedule a workload when it remains unhealthy

  Only allow predefined and safe actions. Record every action taken.

  ### 5. Verify Recovery

  After performing a recovery action, check whether:

  - Pod becomes healthy
  - Error rate decreases
  - Latency returns to normal
  - CPU or memory pressure reduces
  - Network errors or retransmissions decrease

  Mark the incident as resolved only when verification succeeds.

  ### 6. Learn from the Incident

  Store the final incident result in PostgreSQL:

  - Symptoms and collected evidence
  - eBPF telemetry
  - LLM diagnosis
  - Recovery action
  - Recovery success or failure

  This allows future incidents to use the new incident as RAG knowledge.

  ## Phase 2 Output

  At the end of Phase 2, the platform should be able to:

  - Use eBPF for deeper Kubernetes network and process visibility.
  - Diagnose incidents with metrics, logs, traces, eBPF data, and incident memory.
  - Automatically perform predefined Kubernetes recovery actions.
  - Verify whether recovery succeeded.
  - Learn from every resolved incident.

  ---

  ## Final Demonstration Scenario

  A suitable final demo is:

  1. Deploy the microservices application on Kubernetes.
  2. Intentionally create a failure such as high CPU, pod crash, or database connection timeout.
  3. Show Prometheus and Grafana detecting the abnormal behavior.
  4. Show logs, traces, and eBPF network evidence.
  5. Show RAG retrieving a similar historical incident.
  6. Show the LLM diagnosis and suggested healing action.
  7. Allow the self-healing engine to restart or scale the workload.
  8. Show that Kubernetes recovers the application.
  9. Verify through dashboards that latency and error rate return to normal.
  10. Store the resolved incident for future retrieval.

  