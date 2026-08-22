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






  ## web app steps



  ./scripts/setup-python.sh
  source .venv/bin/activate
  pytest backend/tests

  Then start the local application:

  ./scripts/run-local.sh

  Open:

  - Frontend: http://localhost:3000
  - API docs: http://localhost:8000/docs
  - Metrics: http://localhost:8000/metrics
