#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

# Validate all required tools before creating a venv or replacing node_modules.
command -v python3 >/dev/null 2>&1 || fail "Python 3.11+ is required. Install it and make python3 available on PATH."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' ||
  fail "Python 3.11+ is required; found $(python3 --version 2>&1)."
command -v node >/dev/null 2>&1 || fail "Node.js 22.12+ is required. Install it and make node available on PATH."
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 22 || (major === 22 && minor >= 12) ? 0 : 1)' ||
  fail "Node.js 22.12+ is required; found $(node --version 2>&1)."
command -v npm >/dev/null 2>&1 || fail "npm is required. Install npm with Node.js 22.12+ and make it available on PATH."
npm --version >/dev/null || fail "npm could not run. Check your Node.js/npm installation."

VENV_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
if [[ -e "$REPO_ROOT/backend/.venv" ]]; then
  [[ -x "$VENV_PYTHON" ]] || fail "backend/.venv is incomplete. Move or remove it, then rerun ./demo.sh to recreate it with Python 3.11+."
  "$VENV_PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' ||
    fail "backend/.venv must use Python 3.11+. Move or remove it, then rerun ./demo.sh."
fi
[[ -f frontend/package-lock.json ]] || fail "frontend/package-lock.json is missing. Restore it before running the demo."

# Do not mistake an already-running service for one started by this launcher.
python3 - <<'PY'
import socket
import sys

sockets = []
try:
    for port in (8000, 5173):
        sock = socket.socket()
        sockets.append(sock)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as error:
            sys.exit(f"Error: Cannot use 127.0.0.1:{port}: {error}. Stop the conflicting service and rerun ./demo.sh.")
finally:
    for sock in sockets:
        sock.close()
PY

printf '\nSetting up the TribeSignal demo (dependency downloads may require internet access)...\n'
if [[ ! -d "$REPO_ROOT/backend/.venv" ]]; then
  python3 -m venv "$REPO_ROOT/backend/.venv" || fail "Could not create backend/.venv. Check that your Python 3.11+ installation includes venv support."
fi
"$VENV_PYTHON" -m pip install -e 'backend[test]' || fail "Backend dependency installation failed. See the pip output above."
# Always reconcile with the committed lockfile, including on subsequent runs.
(cd "$REPO_ROOT/frontend" && npm ci) || fail "Frontend dependency installation failed. See the npm output above."

backend_pid=''
frontend_pid=''

cleanup() {
  local exit_status=$?
  local pid attempt running
  trap - EXIT INT TERM
  printf '\nStopping TribeSignal demo...\n'
  # Each service has its own process group, including npm/Vite descendants.
  for pid in "$backend_pid" "$frontend_pid"; do
    if [[ -n "$pid" ]]; then
      kill -TERM -- "-$pid" 2>/dev/null || true
    fi
  done
  for attempt in {1..50}; do
    running=false
    for pid in "$backend_pid" "$frontend_pid"; do
      if [[ -n "$pid" ]] && kill -0 -- "-$pid" 2>/dev/null; then
        running=true
      fi
    done
    [[ "$running" == true ]] || break
    sleep 0.1
  done
  for pid in "$backend_pid" "$frontend_pid"; do
    if [[ -n "$pid" ]]; then
      kill -KILL -- "-$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  exit "$exit_status"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Bash job control gives each background service a process group on macOS/Linux;
# this avoids requiring Linux-only setsid or Bash 4's wait -n.
set -m

printf '\nStarting backend and frontend...\n'
TRIBESIGNAL_DEMO_MODE=true \
TRIBESIGNAL_CORS_ORIGINS=http://127.0.0.1:5173 \
  "$VENV_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
backend_pid=$!
(
  cd "$REPO_ROOT/frontend"
  export VITE_API_BASE_URL=http://127.0.0.1:8000
  # Preserve backend errors in the shared terminal when Vite starts/rebuilds.
  exec npm run dev -- --clearScreen false
) &
frontend_pid=$!

check_services() {
  local pid name status
  for name in backend frontend; do
    if [[ "$name" == backend ]]; then pid=$backend_pid; else pid=$frontend_pid; fi
    if ! kill -0 "$pid" 2>/dev/null; then
      status=0
      wait "$pid" || status=$?
      fail "The $name exited unexpectedly (status $status). See its output above."
    fi
  done
}

# Use the required Python runtime for HTTP checks instead of requiring curl.
# Bound every request and keep checking both children while startup is pending.
ready=false
deadline=$((SECONDS + 60))
while (( SECONDS < deadline )); do
  check_services
  if "$VENV_PYTHON" - <<'PY'
import json
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

opener = build_opener(ProxyHandler({}))
try:
    with opener.open("http://127.0.0.1:8000/health", timeout=1) as response:
        if response.status != 200 or json.load(response) != {"status": "ok"}:
            raise ValueError("Backend is not healthy")
    with opener.open("http://127.0.0.1:5173", timeout=1) as response:
        if response.status != 200:
            raise ValueError("Frontend is not ready")
except (OSError, URLError, ValueError):
    raise SystemExit(1)
PY
  then
    check_services
    ready=true
    break
  fi
  sleep 0.5
done
[[ "$ready" == true ]] || fail "Startup timed out after 60 seconds waiting for the backend health endpoint and frontend. See service output above."

cat <<'BANNER'

TribeSignal demo
Frontend: http://127.0.0.1:5173
Backend API: http://127.0.0.1:8000
API docs: http://127.0.0.1:8000/docs
Demo mode: enabled
Gemini API key: not required

Both services are ready. Press Ctrl-C to stop them.
Restart ./demo.sh to reset the seeded demo data.
BANNER

while true; do
  check_services
  sleep 1
done
