#!/usr/bin/env bash
# stack.sh — start / stop / restart the entire internalCMDB application stack
#
# Usage:
#   ./stack.sh start    — starts FastAPI, ARQ worker, collector agent, Next.js UI
#   ./stack.sh stop     — stops all services
#   ./stack.sh restart  — stop then start
#   ./stack.sh status   — show running state of each service
#   ./stack.sh logs     — tail logs from all services

set -euo pipefail

# ── Config ─────────────────────────────────────────────────────────────────────
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
FRONTEND="$ROOT/frontend"
LOG_DIR="$ROOT/.stack/logs"
PID_DIR="$ROOT/.stack/pids"
# Local Redis via compose: use `make dev-up` (docker-compose.dev.yml); stack.sh uses REDIS_URL from .env.

API_HOST="0.0.0.0"
API_PORT="4444"
UI_PORT="3333"
AGENT_API_URL="${AGENT_API_URL:-http://127.0.0.1:${API_PORT}/api/v1/collectors}"
AGENT_HOST_CODE="${AGENT_HOST_CODE:-$(hostname -s 2>/dev/null || hostname 2>/dev/null || printf 'dev-local')}"

mkdir -p "$LOG_DIR" "$PID_DIR"

# ── Helpers ────────────────────────────────────────────────────────────────────
info()    { echo "$(date '+%H:%M:%S') [INFO]  $*"; }
success() { echo "$(date '+%H:%M:%S') [OK]    $*"; }
warn()    { echo "$(date '+%H:%M:%S') [WARN]  $*"; }
error()   { echo "$(date '+%H:%M:%S') [ERROR] $*" >&2; }

pid_is_running() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

stop_pid() {
  local name="$1"
  local pidfile="$PID_DIR/${name}.pid"
  if pid_is_running "$pidfile"; then
    local pid
    pid=$(cat "$pidfile")
    info "Stopping ${name} (PID ${pid})..."
    kill -TERM "$pid" 2>/dev/null || true
    # wait up to 10 s
    local i=0
    while kill -0 "$pid" 2>/dev/null && (( i < 20 )); do
      sleep 0.5; (( i++ ))
    done
    kill -KILL "$pid" 2>/dev/null || true
    rm -f "$pidfile"
    success "$name stopped"
  else
    rm -f "$pidfile"
    warn "$name was not running"
  fi
}

# ── Redis: cluster instance at redis.infraq.app:443 (TLS) ─────────────────────
verify_redis() {
  local url
  local py
  local safe_url
  url=$(grep -E '^REDIS_URL=' "$(dirname "$0")/.env" 2>/dev/null | cut -d= -f2-)
  url="${url:-$REDIS_URL}"

  if [[ -z "${url:-}" ]]; then
    error "REDIS_URL is not set (.env or environment)"
    exit 1
  fi

  py="$VENV/bin/python"
  if [[ ! -x "$py" ]]; then
    error "Python virtual environment missing at $VENV — run 'make init' first"
    exit 1
  fi

  safe_url=$(printf '%s' "$url" | sed -E 's#(rediss?://)[^@]+@#\1***@#')

  if REDIS_CHECK_URL="$url" "$py" -c "
import os
import redis
import sys

try:
    r = redis.from_url(os.environ['REDIS_CHECK_URL'], socket_connect_timeout=5)
    r.ping()
except Exception as e:
    print(e, file=sys.stderr)
    sys.exit(1)
" 2>/tmp/redis_check.err; then
  success "Redis OK (${safe_url})"
  else
    error "Cannot reach Redis: $(cat /tmp/redis_check.err)"
    exit 1
  fi
}

redis_is_reachable() {
  local url
  local py

  url=$(grep -E '^REDIS_URL=' "$(dirname "$0")/.env" 2>/dev/null | cut -d= -f2-)
  url="${url:-$REDIS_URL}"
  py="$VENV/bin/python"

  [[ -n "${url:-}" && -x "$py" ]] || return 1

  REDIS_CHECK_URL="$url" "$py" -c "
import os
import redis
import sys

try:
    redis.from_url(os.environ['REDIS_CHECK_URL'], socket_connect_timeout=5).ping()
except Exception:
    sys.exit(1)
" >/dev/null 2>&1
}

# ── Start ──────────────────────────────────────────────────────────────────────
cmd_start() {
  info "=== Starting internalCMDB stack ==="

  # Activate venv
  if [[ ! -f "$VENV/bin/activate" ]]; then
    error "Virtual environment not found at $VENV — run 'make init' first"
    exit 1
  fi
  # shellcheck source=/dev/null
  source "$VENV/bin/activate"

  # 1. Redis — cluster instance (redis.infraq.app:443)
  verify_redis

  # 2. FastAPI
  local api_pid="$PID_DIR/api.pid"
  if pid_is_running "$api_pid"; then
    warn "FastAPI already running (PID $(cat "$api_pid"))"
  else
    info "Starting FastAPI on :${API_PORT}..."
    PYTHONPATH="$ROOT/src" uvicorn internalcmdb.api.main:app \
      --host "$API_HOST" --port "$API_PORT" \
      --reload \
      > "$LOG_DIR/api.log" 2>&1 &
    echo $! > "$api_pid"
    sleep 2
    if pid_is_running "$api_pid"; then
      success "FastAPI started (PID $(cat "$api_pid")) — http://localhost:$API_PORT/docs"
    else
      error "FastAPI failed to start — check $LOG_DIR/api.log"
      exit 1
    fi
  fi

  # 3. ARQ worker
  local worker_pid="$PID_DIR/worker.pid"
  if pid_is_running "$worker_pid"; then
    warn "ARQ worker already running (PID $(cat "$worker_pid"))"
  else
    info "Starting ARQ worker..."
    PYTHONPATH="$ROOT/src" python3 -m internalcmdb.workers.run \
      > "$LOG_DIR/worker.log" 2>&1 &
    echo $! > "$worker_pid"
    sleep 1
    if pid_is_running "$worker_pid"; then
      success "ARQ worker started (PID $(cat "$worker_pid"))"
    else
      error "ARQ worker failed to start — check $LOG_DIR/worker.log"
      exit 1
    fi
  fi

  # 4. Collector agent
  local agent_pid="$PID_DIR/agent.pid"
  if pid_is_running "$agent_pid"; then
    warn "Collector agent already running (PID $(cat "$agent_pid"))"
  else
    info "Starting collector agent for host '${AGENT_HOST_CODE}'..."
    PYTHONPATH="$ROOT/src" AGENT_API_URL="$AGENT_API_URL" AGENT_HOST_CODE="$AGENT_HOST_CODE" \
      python3 -m internalcmdb.collectors.agent \
      > "$LOG_DIR/agent.log" 2>&1 &
    echo $! > "$agent_pid"
    sleep 2
    if pid_is_running "$agent_pid"; then
      success "Collector agent started (PID $(cat "$agent_pid"))"
    else
      error "Collector agent failed to start — check $LOG_DIR/agent.log"
      exit 1
    fi
  fi

  # 5. Next.js UI
  if [[ ! -d "$FRONTEND/node_modules" ]]; then
    info "Installing frontend dependencies..."
    (cd "$FRONTEND" && pnpm install --frozen-lockfile)
  fi
  local ui_pid="$PID_DIR/ui.pid"
  if pid_is_running "$ui_pid"; then
    warn "Next.js already running (PID $(cat "$ui_pid"))"
  else
    # Remove stale Turbopack lock (left by a previous crashed/killed instance)
    rm -f "$FRONTEND/.next/dev/lock"
    info "Starting Next.js UI on :${UI_PORT}..."
    (cd "$FRONTEND" && pnpm dev --port "$UI_PORT") \
      > "$LOG_DIR/ui.log" 2>&1 &
    echo $! > "$ui_pid"
    sleep 3
    if pid_is_running "$ui_pid"; then
      success "Next.js started (PID $(cat "$ui_pid")) — http://localhost:$UI_PORT"
    else
      error "Next.js failed to start — check $LOG_DIR/ui.log"
      exit 1
    fi
  fi

  echo ""
  success "=== Stack is up ==="
  echo "  UI      → http://localhost:$UI_PORT"
  echo "  API     → http://localhost:$API_PORT"
  echo "  API docs → http://localhost:$API_PORT/docs"
  echo "  Logs    → $LOG_DIR/"
}

# ── Port cleanup ──────────────────────────────────────────────────────────────
kill_ports() {
  for port in "$API_PORT" "$UI_PORT"; do
    local pids
    pids=$(lsof -ti TCP:"$port" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      info "Killing stale process(es) on :${port} (PID ${pids})..."
      echo "$pids" | tr ' ' '\n' | while read -r pid; do
        kill -TERM "$pid" 2>/dev/null || true
      done
      sleep 1
      # Force-kill anything still alive
      pids=$(lsof -ti TCP:"$port" 2>/dev/null || true)
      if [[ -n "$pids" ]]; then
        echo "$pids" | tr ' ' '\n' | while read -r pid; do
          kill -KILL "$pid" 2>/dev/null || true
        done
      fi
      success "Port :${port} cleared"
    fi
  done
}

# ── Stop ───────────────────────────────────────────────────────────────────────
cmd_stop() {
  info "=== Stopping internalCMDB stack ==="
  stop_pid "ui"
  stop_pid "agent"
  stop_pid "worker"
  stop_pid "api"
  # Kill anything still holding our ports (stale processes not tracked by pidfiles)
  kill_ports
  # Clean up Next.js Turbopack lock so next start doesn't fail
  rm -f "$FRONTEND/.next/dev/lock"
  success "=== Stack stopped ==="
}

# ── Restart ────────────────────────────────────────────────────────────────────
cmd_restart() {
  cmd_stop
  echo ""
  # Extra port sweep before starting — catches processes started outside make
  kill_ports
  cmd_start
}

# ── Status ─────────────────────────────────────────────────────────────────────
cmd_status() {
  echo "=== internalCMDB stack status ==="
  for svc in api worker agent ui; do
    local pidfile="$PID_DIR/${svc}.pid"
    if pid_is_running "$pidfile"; then
      printf "  %-10s  ● running  (PID %s)\n" "$svc" "$(cat "$pidfile")"
    else
      printf "  %-10s  ○ stopped\n" "$svc"
    fi
  done
  printf "  %-10s  " "redis"
  if redis_is_reachable; then
    echo "● reachable via shared endpoint"
  else
    echo "○ unreachable"
  fi
}

# ── Logs ───────────────────────────────────────────────────────────────────────
cmd_logs() {
  if [[ ! -d "$LOG_DIR" ]]; then
    info "No logs yet (stack has not been started)"
    exit 0
  fi
  info "Tailing logs — Ctrl-C to stop"
  tail -f "$LOG_DIR"/api.log "$LOG_DIR"/worker.log "$LOG_DIR"/agent.log "$LOG_DIR"/ui.log 2>/dev/null
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "${1:-help}" in
  start)   cmd_start   ;;
  stop)    cmd_stop    ;;
  restart) cmd_restart ;;
  status)  cmd_status  ;;
  logs)    cmd_logs    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
