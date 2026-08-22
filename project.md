slides
gpt chat : https://chatgpt.com/share/6a79c246-62c8-83ee-96c5-97b3edd434d1	
1. Final Project Title
eBPF-Enhanced RAG-Based Intelligent Cloud Incident Management and Self-Healing
A slightly more academic alternative:
An Intelligent Cloud-Native Incident Management and Self-Healing Platform using eBPF and RAG
I recommend the second title for a college project/report because it clearly communicates the four main components:

Cloud-Native → Kubernetes + containers
Incident Management → detecting and handling failures
eBPF → deep system/network observability
RAG → remembering and retrieving previous incidents
Self-Healing → automatically recovering workloads


2. What is the project?
Your project is an open-source cloud-native platform that monitors containerized applications, detects incidents, investigates their root causes using multiple sources of telemetry and historical incident knowledge, and performs appropriate recovery actions.

The basic idea is:

Observe → Detect → Remember → Diagnose → Heal → Verify → Learn

Instead of an engineer manually looking through logs whenever a container or service fails, your platform continuously monitors the cloud environment and assists — or automatically performs — the incident response.


3. The Problem You Are Solving
Modern cloud applications are usually distributed across many containers and services.

For example:

                  Application

                      │

       ┌──────────────┼──────────────┐

       ↓              ↓              ↓

    Frontend        API          Database

       │              │              │

   Container       Container       Container

When something goes wrong, the engineer may have to look at:

Application logs
CPU and memory
Network activity
Service latency
Distributed traces
Container status
Previous incidents
Deployment history

The problem is that this information is distributed across different sources.

An engineer may know:

"The service is slow."

But determining:

Why is it slow, has this happened before, and what should I do now?

can take considerable time.

Your project addresses this by combining cloud-native observability, eBPF, historical incident memory, RAG, LLM-based reasoning, and automated recovery.


4. Your Two Main Novelties
These are the two I recommend you officially use.
Novelty 1 — Incident Memory & Similarity-Based Detection
Simple explanation
The system remembers previous cloud incidents and uses them to understand new incidents.

For every resolved incident, you store something like:

Incident

   ↓

Symptoms

   ↓

Telemetry

   ↓

Root Cause

   ↓

Solution

   ↓

Outcome

For example:

Incident #12

Symptoms:

API latency increased

CPU = 92%

Evidence:

High process CPU

Increased requests

Root Cause:

Application overload

Solution:

Scaled application containers

Outcome:

Latency returned to normal

Later, a similar problem occurs.

Your system retrieves Incident #12 and tells the LLM:

"This incident is similar to a previous incident that was caused by application overload and resolved by scaling the application."
What makes this useful?
Normal monitoring says:

"Something is wrong."

Your system can say:

"This looks similar to a previous problem, and this is how it was successfully resolved."

That is your incident memory.


5. Novelty 2 — eBPF-Enhanced Self-Healing
This combines two ideas:
eBPF
Provides deeper visibility into:

Processes
Containers
Network connections
TCP behavior
System calls
Kernel-level activity
Self-healing
Allows the platform to take recovery actions such as:

Restarting a failed container
Rescheduling a workload
Scaling containers
Replacing unhealthy workloads

So your second novelty is:

Use deep eBPF-based telemetry to improve diagnosis and trigger appropriate self-healing actions for cloud-native workloads.


6. Why eBPF is important
Without eBPF:

Prometheus

   ↓

CPU = 90%

You know the resource is under pressure.

But you may not know exactly what is causing it.

With eBPF:

CPU = 90%

      ↓

Process A consuming most CPU

      ↓

Process A generating high network activity

      ↓

Network retransmissions increasing

      ↓

Database communication affected

Now your system has much richer evidence.

So your project combines:

Metrics

+

Logs

+

Traces

+

eBPF

+

Historical incidents

before asking the LLM to diagnose the problem.

That is much stronger than simply feeding logs to an LLM.


7. Overall Architecture
Your high-level architecture can be:

                       CLOUD-NATIVE PLATFORM

                              │

                         Kubernetes

                              │

             ┌────────────────┼────────────────┐

             ↓                ↓                ↓

        Container A      Container B      Container C

             │                │                │

             └────────────────┼────────────────┘

                              ↓

                    OBSERVABILITY LAYER

                              │

              ┌───────────────┼───────────────┐

              ↓               ↓               ↓

         Prometheus      OpenTelemetry       eBPF

           Metrics        Logs/Traces      Process/Network

              └───────────────┼───────────────┘

                              ↓

                    Incident Detection

                              ↓

                    Incident Context

                              │

                ┌─────────────┴─────────────┐

                ↓                           ↓

        Current Telemetry            Incident Memory

                │                           │

                │                          RAG

                │                           │

                └─────────────┬─────────────┘

                              ↓

                             LLM

                              ↓

                  Root Cause + Recommendation

                              ↓

                       Self-Healing Engine

                              ↓

              ┌───────────────┼───────────────┐

              ↓               ↓               ↓

           Restart          Scale         Reschedule

          Container        Workload         Pod

              └───────────────┼───────────────┘

                              ↓

                       Recovery Verification

                              ↓

                      Incident Resolved

                              ↓

                       Store in Memory


8. What is the Cloud Computing part?
This is important for your project evaluation.

You are not just running an AI application inside a container.

Your actual infrastructure demonstrates cloud-computing concepts.
Kubernetes provides:
Distributed computing
Multiple workloads run across multiple nodes.
Resource management
Kubernetes allocates CPU and memory to workloads.
Scalability
Workloads can be scaled based on demand.
Elasticity
Resources can increase/decrease according to workload.
High availability
Multiple replicas can keep an application available.
Fault tolerance
If a container fails, Kubernetes can recreate it.
Service discovery
Services can communicate with each other through the cloud-native networking layer.
Container orchestration
Kubernetes schedules and manages containers.

So your project demonstrates genuine cloud computing concepts.


9. Why not AWS?
You decided to make the platform open-source instead of AWS-dependent.

That is completely reasonable.

Instead of:

AWS

├── EC2

├── RDS

├── CloudWatch

└── S3

you can build:

Open-source cloud-native environment

├── Kubernetes

├── Containers

├── Prometheus

├── OpenTelemetry

├── eBPF

├── Grafana

├── PostgreSQL

└── RAG + LLM

This also makes your project more portable.

You could theoretically deploy the same platform on:

Local machines
Virtual machines
OpenStack
AWS
Azure
Other Kubernetes environments

The project isn't tied to one cloud provider.


10. Recommended Technology Stack
Don't feel that you need to implement every possible tool. This is a recommended stack.

Layer
Technology
Purpose
Containerization
Docker
Package applications
Orchestration
Kubernetes
Manage containers
Networking/eBPF
Cilium
eBPF-based networking/observability
Metrics
Prometheus
Collect/store metrics
Telemetry
OpenTelemetry
Collect logs/traces/telemetry
Visualization
Grafana
Monitoring dashboard
eBPF
Cilium/eBPF tools
Kernel/process/network visibility
Incident database
PostgreSQL
Store incidents
Vector retrieval
pgvector or vector DB
Similarity search
RAG
Custom pipeline / LangChain / LlamaIndex
Retrieve relevant knowledge
LLM
Open-source LLM
Diagnosis/recommendation
Automation
Kubernetes API
Execute recovery actions



11. What exactly will be monitored?
Your platform should not just monitor CPU.

For each workload, you can collect:
Infrastructure
CPU utilization
Memory utilization
Disk usage
Network traffic
Node health
Container
Container restarts
Container CPU
Container memory
Pod status
Resource limits
OOM kills
Application
Request rate
Error rate
Response latency
HTTP status codes
Network
Through eBPF:

Connections
TCP retransmissions
Network latency
Service-to-service traffic
Connection failures
Logs
Examples:

Database connection timeout

HTTP 500

Service unavailable

Out of memory

Connection refused
Traces
For example:

Request

  ↓

API

  ↓

Payment Service

  ↓

Database

This allows you to identify which service is causing latency.


12. What does an incident look like?
Imagine this situation.

A user requests a page.

User

 ↓

API

 ↓

Payment Service

 ↓

Database

Suddenly the application becomes slow.

Your system detects:

CPU: 85%

Latency: ↑

Errors: ↑

Database connections: ↑

TCP retransmissions: ↑

eBPF gives:

Payment container

      ↓

High network activity

      ↓

Repeated database connections

Logs show:

Database connection timeout

The RAG system finds:

Previous Incident #23

Cause:

Database connection saturation

Solution:

Restart affected service and increase

connection pool / scale workload

Result:

Recovered successfully

The LLM receives all of this context.

It generates:

Likely Root Cause:

Database connection saturation.

Evidence:

• Increased database connections

• Connection timeout errors

• Increased network retransmissions

• Similarity to Incident #23

Recommended Action:

Restart affected workload and scale

the service if the load remains high.


13. Self-Healing
Now the important part.

The system can execute a controlled recovery action.

For example:

Incident

   ↓

Diagnosis

   ↓

Recovery policy

   ↓

Kubernetes API

   ↓

Restart pod

Or:

High workload

   ↓

Diagnosis

   ↓

Scale deployment

   ↓

2 replicas → 4 replicas

Or:

Unhealthy pod

   ↓

Detected

   ↓

Remove pod

   ↓

Kubernetes creates replacement


14. Verification is very important
Don't stop after taking the action.

Your system should check:

Before healing

CPU = 95%

Latency = 4 seconds

Errors = 15%

Then:

Healing action

     ↓

Wait

     ↓

Monitor

After healing:

CPU = 45%

Latency = 300 ms

Errors = normal

Then:

Incident successfully resolved.

This makes the self-healing feature much more convincing.


15. Incident Memory After Healing
The final step is:

Incident

   ↓

Diagnosis

   ↓

Action

   ↓

Recovery

   ↓

Store result

So the next time the same issue occurs, the system becomes more useful.

Your incident database could contain:

{

  "incident": "High database connection usage",

  "symptoms": [...],

  "telemetry": [...],

  "root_cause": "...",

  "action": "...",

  "result": "successful"

}

This becomes your organizational memory.


16. Full End-to-End Workflow
Your project can be explained in these 8 steps:
Step 1 — Deploy
Deploy a distributed application on Kubernetes.
Step 2 — Observe
Collect metrics, logs, traces and eBPF telemetry.
Step 3 — Detect
Identify abnormal behavior or an incident.
Step 4 — Build Context
Combine current telemetry into an incident context.
Step 5 — Retrieve
Search historical incidents using RAG.
Step 6 — Diagnose
LLM analyzes current + historical evidence.
Step 7 — Heal
Execute an approved or automated recovery action.
Step 8 — Verify & Learn
Check whether the system recovered and store the incident outcome.

So:

Observe → Detect → Retrieve → Diagnose → Heal → Verify → Remember


17. What is actually novel?
This distinction is important for your viva.

You should not claim:

"Nobody has ever used RAG for cloud incidents."

or

"Nobody has ever used eBPF for cloud observability."

Those technologies already exist individually.

Your novelty is the integration and workflow you implement.
Novelty 1
Incident Memory & Similarity-Based Detection

Integration of historical incident memory with current cloud telemetry so that new incidents can be compared with previously resolved incidents.
Novelty 2
eBPF-Enhanced Self-Healing Cloud Infrastructure

Integration of deep kernel/process/network observability with an incident-response engine that can select, execute, and verify recovery actions for containerized workloads.


18. What is your research question?
You can frame the project around:

Can combining multi-signal cloud observability, eBPF telemetry, and historical incident memory improve the accuracy and speed of cloud incident diagnosis and automated recovery?

Then you can experimentally compare:
System A
Metrics + Logs
System B
Metrics + Logs + Traces + eBPF
System C
Metrics + Logs + Traces + eBPF

              +

         RAG Memory

And finally:
System D
System C

   +

Self-Healing

This gives you something measurable for your final report.


19. Metrics you can evaluate
You can measure:
Detection
Detection latency
Detection accuracy
False positives
Diagnosis
Root-cause accuracy
Similar-incident retrieval accuracy
Time to diagnosis
Self-healing
Recovery success rate
Mean time to recovery
Recovery latency
Number of manual interventions
System overhead
This is particularly important for eBPF:

CPU overhead
Memory overhead
Network/telemetry overhead

You can demonstrate whether adding eBPF provides useful diagnostic information without excessive overhead.


20. Example experiment
Create three failure scenarios.
Scenario 1 — CPU overload
Normal

 ↓

Artificial workload

 ↓

CPU ↑

 ↓

Incident detected

 ↓

RAG finds similar incident

 ↓

Scale workload

 ↓

Recovery
Scenario 2 — Network problem
Service A

   ↓

Network degradation

   ↓

eBPF detects abnormal network behavior

   ↓

RAG retrieves similar incident

   ↓

LLM identifies likely cause

   ↓

Recovery action
Scenario 3 — Container failure
Container crashes

 ↓

eBPF / Kubernetes detects failure

 ↓

Incident generated

 ↓

Previous incident retrieved

 ↓

Kubernetes restarts workload

 ↓

Health restored

These are excellent demonstrations for your project presentation.


21. Your final architecture in one diagram
For your report, I would use something approximately like this:

┌───────────────────────────────────────────────────────────────┐

│                    CLOUD-NATIVE ENVIRONMENT                   │

│                                                               │

│                    Kubernetes Cluster                         │

│                                                               │

│   ┌──────────┐     ┌──────────┐     ┌──────────┐             │

│   │ Service A│     │ Service B│     │ Service C│             │

│   │Container │     │Container │     │Container │             │

│   └────┬─────┘     └────┬─────┘     └────┬─────┘             │

│        └─────────────────┼────────────────┘                  │

│                          │                                   │

│              ┌───────────┴───────────┐                       │

│              │    OBSERVABILITY       │                       │

│              │                        │                       │

│              │ Prometheus             │                       │

│              │ OpenTelemetry          │                       │

│              │ eBPF / Cilium          │                       │

│              └───────────┬───────────┘                       │

└──────────────────────────┼────────────────────────────────────┘

                           ↓

                 ┌──────────────────┐

                 │ Incident Engine  │

                 └────────┬─────────┘

                          ↓

                ┌────────────────────┐

                │ Current Incident   │

                │ Context            │

                └─────────┬──────────┘

                          ↓

              ┌────────────────────────┐

              │  Incident Memory / RAG │

              └───────────┬────────────┘

                          ↓

                     ┌─────────┐

                     │   LLM   │

                     └────┬────┘

                          ↓

               ┌─────────────────────┐

               │ Root Cause + Action │

               └──────────┬──────────┘

                          ↓

                ┌────────────────────┐

                │ Self-Healing Engine│

                └──────────┬─────────┘

                           ↓

                 Kubernetes API

                           ↓

              ┌────────────┼────────────┐

              ↓            ↓            ↓

           Restart       Scale       Reschedule

              └────────────┼────────────┘

                           ↓

                  Recovery Verification

                           ↓

                    Incident Memory


22. What your project is NOT
This will help you explain it during your viva.
It is not just an ML project
Because the core infrastructure is Kubernetes/container-based cloud computing.
It is not just an LLM chatbot
The LLM doesn't simply answer questions. It receives structured incident evidence and helps perform incident management.
It is not just an observability dashboard
Grafana/Prometheus/eBPF are used to feed an intelligent incident-response pipeline.
It is not just an automation script
The system performs detection, diagnosis, action, and recovery verification.


23. The one-minute explanation for your guide
You can explain the entire project like this:

“Our project is an open-source cloud-native incident management and self-healing platform for containerized applications. We deploy distributed workloads using Kubernetes and monitor them using metrics, logs, traces, and eBPF-based process and network telemetry. When an abnormal condition occurs, the system creates an incident context and uses RAG to retrieve similar historical incidents and their successful resolutions. An LLM then assists in identifying the root cause and selecting an appropriate remediation action. The system can perform actions such as restarting or scaling workloads through Kubernetes and then verifies whether the system has recovered. The resolved incident is stored back into the incident memory so that future similar incidents can be diagnosed more quickly.”

That's your project in one paragraph.


24. Final project identity
I would define it as:

Domain: Cloud Computing / Cloud-Native Systems

Secondary domains: Distributed Systems, Observability, AIOps, Linux Systems, RAG/LLM

Infrastructure: Kubernetes + Containers

Observability: OpenTelemetry + Prometheus + eBPF/Cilium + Grafana

Intelligence: RAG + LLM

Automation: Kubernetes API / self-healing controller

Novelty 1: Incident Memory & Similarity-Based Detection

Novelty 2: eBPF-Enhanced Self-Healing Cloud Infrastructure

Core workflow:

Observe → Detect → Retrieve → Diagnose → Heal → Verify → Learn

And importantly, this gives you a strong separation:

Cloud Computing is the foundation. eBPF is the deep observability layer. RAG/LLM is the intelligence layer. Self-healing is the action layer.

That is a much more convincing final-year Cloud Computing project than the original “RAG analyzes cloud logs” concept.

