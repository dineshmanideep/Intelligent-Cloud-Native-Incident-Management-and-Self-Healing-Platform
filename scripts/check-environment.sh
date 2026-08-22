 #!/usr/bin/env bash

  set -u

  failed=0

  check_command() {
      local command_name="$1"

      if command -v "$command_name" >/dev/null 2>&1; then
          printf "OK   %-12s %s\n" "$command_name" "$(command -v "$command_name")"
      else
          printf "FAIL %-12s not installed\n" "$command_name"
          failed=1
      fi
  }

  echo "Checking required commands..."
  check_command docker
  check_command minikube
  check_command kubectl
  check_command helm
  check_command python3
  check_command git
  check_command curl

  echo
  echo "Checking Docker daemon..."

  if docker info >/dev/null 2>&1; then
      echo "OK   Docker daemon is running and accessible"
  else
      echo "FAIL Docker daemon is unavailable or inaccessible"
      echo "      Start Docker and ensure your user can access /var/run/docker.sock"
      failed=1
  fi

  echo
  echo "Checking Python version..."

  if command -v python3 >/dev/null 2>&1; then
      python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
      echo "INFO Python version: $python_version"
  fi

  echo
  echo "Checking Minikube..."

  if command -v minikube >/dev/null 2>&1; then
      if minikube status >/dev/null 2>&1; then
          echo "OK   Minikube cluster is running"
      else
          echo "INFO Minikube is installed but the cluster is not running"
          echo "      This is expected before the first project setup."
      fi
  fi

  echo
  echo "Checking kubectl..."

  if command -v kubectl >/dev/null 2>&1; then
      if kubectl cluster-info >/dev/null 2>&1; then
          echo "OK   kubectl can connect to Kubernetes"
          kubectl config current-context
      else
          echo "INFO kubectl is installed but cannot connect to a cluster yet"
      fi
  fi

  echo
  if [ "$failed" -eq 0 ]; then
      echo "Environment check passed."
      echo "You can proceed with Minikube cluster setup."
  else
      echo "Environment check failed."
      echo "Install or fix the failed requirements before continuing."
      exit 1
  fi