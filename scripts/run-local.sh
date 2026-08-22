#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "Missing .venv. Run ./scripts/setup-python.sh first." >&2
  exit 1
fi

docker compose up -d postgres
until docker compose exec -T postgres pg_isready -U incident_user -d incident_demo >/dev/null 2>&1; do
  sleep 1
done

cleanup() {
  kill "${backend_pid:-}" "${frontend_pid:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

.venv/bin/uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000 &
backend_pid=$!
python3 -m http.server 3000 --directory frontend &
frontend_pid=$!

echo "Backend:  http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"
wait

