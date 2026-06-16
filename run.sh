#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$REPO_ROOT/app"
FRONTEND_DIR="$APP_DIR/frontend"

# Python from venv
PYTHON="$REPO_ROOT/.venv/bin/python"

# Databricks CLI — search common locations
if [ -z "${DBX_CLI:-}" ]; then
  for candidate in \
      "$(command -v databricks 2>/dev/null || true)" \
      "/opt/homebrew/bin/databricks" \
      "/usr/local/bin/databricks" \
      "$HOME/.databricks/bin/databricks"; do
    if [ -x "$candidate" ]; then
      DBX_CLI="$candidate"
      break
    fi
  done
fi

usage() {
  echo "Usage: $0 <command> [options]"
  echo ""
  echo "  ui                Run frontend dev server (Vite, port 5173 or next free port)"
  echo "  api               Run API server (uvicorn, port 8000 or next free port, --reload)"
  echo "  dev               Run both UI and API locally in parallel"
  echo "  deploy [name]     Build + push to Databricks Apps"
  echo "                    Omit [name] → use DATABRICKS_APP_NAME from .env"
  echo "                    Pass [name] → deploy a separate named copy"
  echo "  open [name]       Print + open the deployed app URL in the browser"
  exit 1
}

is_port_free() {
  "$PYTHON" - "$1" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.2)
    sys.exit(0 if sock.connect_ex(("127.0.0.1", port)) else 1)
PY
}

free_port() {
  local start="${1:-8000}"
  local port="$start"
  while [ "$port" -lt $((start + 50)) ]; do
    if is_port_free "$port"; then
      echo "$port"
      return 0
    fi
    port=$((port + 1))
  done
  echo "ERROR: no free port found in range $start-$((start + 49))" >&2
  exit 1
}

# ── load .env ────────────────────────────────────────────────────────────────
load_env() {
  if [ -f "$REPO_ROOT/.env" ]; then
    set -o allexport
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.env"
    set +o allexport
  fi
}

# ── require databricks CLI ────────────────────────────────────────────────────
require_dbx_cli() {
  if [ -z "${DBX_CLI:-}" ]; then
    echo "ERROR: databricks CLI not found."
    echo "  Install: brew tap databricks/tap && brew install databricks"
    exit 1
  fi
}

# ── run databricks CLI with profile auth ─────────────────────────────────────
dbx() {
  local profile="${DBX_PROFILE:-}"
  if [ -n "$profile" ]; then
    "$DBX_CLI" --profile "$profile" "$@"
  else
    "$DBX_CLI" "$@"
  fi
}

# ── auto-create or update a Databricks App ───────────────────────────────────
app_compute_state() {
  dbx apps get "$1" -o json 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('compute_status',{}).get('state','UNKNOWN'))" \
    2>/dev/null || echo "UNKNOWN"
}

wait_for_running() {
  local app_name="$1"
  local state
  echo -n ">>> Waiting for '$app_name' to be RUNNING"
  for _ in $(seq 1 40); do
    state=$(app_compute_state "$app_name")
    if [ "$state" = "RUNNING" ] || [ "$state" = "ACTIVE" ]; then
      echo " ✓ ($state)"
      return 0
    fi
    echo -n " ."
    sleep 10
  done
  echo ""
  echo "ERROR: App still in state '$state' after ~7 min. Check the Databricks Apps UI."
  exit 1
}

ensure_app() {
  local app_name="$1" workspace_path="$2"
  local state

  state=$(app_compute_state "$app_name")

  case "$state" in
    UNKNOWN)
      echo ">>> App '$app_name' not found — creating..."
      dbx apps create "$app_name" --no-wait
      wait_for_running "$app_name"
      ;;
    STOPPED)
      echo ">>> App is STOPPED — starting..."
      dbx apps start "$app_name" --no-wait 2>/dev/null || dbx apps start "$app_name"
      wait_for_running "$app_name"
      ;;
    STARTING|PROVISIONING|DEPLOYING|UNAVAILABLE)
      wait_for_running "$app_name"
      ;;
    RUNNING|ACTIVE)
      echo ">>> App '$app_name' is $state"
      ;;
  esac

  echo ">>> Deploying '$app_name'..."
  dbx apps deploy "$app_name" --source-code-path "$workspace_path"
}

# ── commands ─────────────────────────────────────────────────────────────────
run_ui() {
  local ui_port="${UI_PORT:-${APP_UI_PORT:-}}"
  if [ -z "$ui_port" ]; then
    ui_port="$(free_port 5173)"
  fi
  local api_port="${API_PORT:-${APP_API_PORT:-8000}}"
  local api_target="${VITE_API_TARGET:-http://127.0.0.1:$api_port}"
  echo ">>> Starting UI dev server..."
  echo ">>> UI:  http://127.0.0.1:$ui_port"
  echo ">>> Vite /api proxy: $api_target"
  cd "$FRONTEND_DIR"
  npm install --silent
  VITE_API_TARGET="$api_target" npm run dev -- --host 127.0.0.1 --port "$ui_port"
}

run_api() {
  local api_port="${API_PORT:-${APP_API_PORT:-}}"
  if [ -z "$api_port" ]; then
    api_port="$(free_port 8000)"
  fi
  echo ">>> Starting API server..."
  echo ">>> API: http://127.0.0.1:$api_port"
  cd "$APP_DIR"
  "$PYTHON" -m uvicorn server:app --host 0.0.0.0 --port "$api_port" --reload
}

run_dev() {
  local ui_port="${UI_PORT:-${APP_UI_PORT:-}}"
  if [ -z "$ui_port" ]; then
    ui_port="$(free_port 5173)"
  fi
  local api_port="${API_PORT:-${APP_API_PORT:-}}"
  if [ -z "$api_port" ]; then
    api_port="$(free_port 8000)"
  fi
  local api_target="http://127.0.0.1:$api_port"
  echo ">>> Starting UI + API (Ctrl-C stops both)..."
  echo ">>> UI:  http://127.0.0.1:$ui_port"
  echo ">>> API: $api_target"
  echo ">>> Vite /api proxy: $api_target"
  trap 'kill 0' INT TERM EXIT
  (cd "$FRONTEND_DIR" && npm install --silent && VITE_API_TARGET="$api_target" npm run dev -- --host 127.0.0.1 --port "$ui_port") &
  (cd "$APP_DIR" && "$PYTHON" -m uvicorn server:app --host 0.0.0.0 --port "$api_port" --reload) &
  wait
}

run_deploy() {
  local custom_name="${1:-}"

  require_dbx_cli
  load_env

  # App name: CLI arg > .env > default
  local app_name="${custom_name:-${DATABRICKS_APP_NAME:-dbx-hack-doctors}}"

  # Workspace path: if custom name given, derive path from it; else use .env
  local base_workspace="${DATABRICKS_WORKSPACE_PATH:-}"
  if [ -z "$base_workspace" ]; then
    echo "ERROR: DATABRICKS_WORKSPACE_PATH not set in .env"
    echo "  Add: DATABRICKS_WORKSPACE_PATH=/Workspace/Users/you@example.com/dbx-hack-doctors"
    exit 1
  fi

  # For a custom-named deploy, swap the last path segment with the app name
  local workspace_path
  if [ -n "$custom_name" ]; then
    workspace_path="$(dirname "$base_workspace")/$app_name"
  else
    workspace_path="$base_workspace"
  fi

  echo ">>> Building frontend..."
  cd "$FRONTEND_DIR"
  npm install --silent
  npm run build

  cd "$REPO_ROOT"

  echo ">>> Syncing ./app → $workspace_path ..."
  # mkdirs only the app subfolder — the user root already exists and is protected
  dbx workspace mkdirs "$workspace_path" 2>/dev/null || true
  # If mkdirs failed (folder exists or parent protected), that's fine — sync handles it
  dbx sync ./app "$workspace_path" --full --include "frontend/dist/**"

  ensure_app "$app_name" "$workspace_path"

  echo ""
  echo ">>> Done: $app_name"
  echo "    Workspace: $workspace_path"
}

run_open() {
  require_dbx_cli
  load_env
  local app_name="${1:-${DATABRICKS_APP_NAME:-dbx-hack-doctors}}"
  local url
  url=$(dbx apps get "$app_name" -o json \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('url',''))")
  if [ -z "$url" ] || [ "$url" = "Unavailable" ]; then
    echo "App URL not available yet — is the app running?"
    exit 1
  fi
  echo ">>> $app_name: $url"
  open "$url"
}

# ── dispatch ──────────────────────────────────────────────────────────────────
CMD="${1:-}"
case "$CMD" in
  ui)     run_ui ;;
  api)    run_api ;;
  dev)    run_dev ;;
  deploy) run_deploy "${2:-}" ;;
  open)   run_open "${2:-}" ;;
  *)      usage ;;
esac
