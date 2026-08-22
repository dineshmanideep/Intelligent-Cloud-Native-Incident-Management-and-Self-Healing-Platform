## 1
do not use 
`
  for i in $(seq 1 120); do
    curl -s -o /dev/null "http://$(minikube ip):30080/api/error" &
  done
  wait
  `
  for the 500 error test 

 - solution
 This was not an application failure. The command overloaded Minikube and Docker.

  The problem was this part:

  $(minikube ip)

  It ran minikube ip approximately 120 times concurrently. Each background request launched another Minikube/Docker inspection, causing:

  context deadline exceeded
  docker container inspect minikube took an unusually long time

  The curl requests then failed because Minikube became temporarily unresponsive.

  The Grafana port-forward stopped because the Kubernetes connection to the Grafana pod was interrupted:

  error forwarding port ... Connection refused
  error: lost connection to pod

  First, wait a minute for the background processes to finish. Then check:

  minikube status
  kubectl get pods -n monitoring
  kubectl get pods -n incident-platform

  If Minikube is healthy, restart Grafana forwarding:

  kubectl port-forward -n monitoring svc/incident-monitoring-grafana 3000:80

  Use this safer incident-generation command next time:

  node_ip="$(minikube ip)"

  for i in $(seq 1 60); do
    curl --max-time 10 -sS -o /dev/null \
      "http://${node_ip}:30080/api/error" &

    if (( i % 10 == 0 )); then
      wait
    fi
  done

  wait

  This calls minikube ip only once and sends requests in batches of ten.

  Then wait for detection:

  sleep 30

  Check the incident:

  curl "http://${node_ip}:30080/incidents/api/incidents?status=active"

  The messages:

  failed to close the audit log: invalid argument

  are Minikube cleanup warnings caused by the overloaded concurrent commands. They are not evidence of an application-code problem.

  Avoid running 120 commands with $(minikube ip) inside the loop.

## 2 : not able to see the errors(incidents) in frontend page
