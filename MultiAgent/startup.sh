#!/usr/bin/env bash
# =============================================================================
#  AgentForge launcher
#
#  Usage:  ./startup.sh [command] [options]
#
#  Commands
#    dev       (default) API with auto-reload on :8000 + UI with hot reload on :5173
#    prod      build the UI and serve UI + API from one server (ENV=production)
#    docker    docker compose up --build  (app + Postgres + Redis)
#    setup     install / update dependencies only
#    test      backend test-suite + frontend type-check
#    doctor    check Python, Node, ports, configuration and API keys
#    stop      stop servers started with --detach
#    logs      follow the logs of detached servers
#    reset     delete the local development database (asks first)
#    help      show this help
#
#  Options
#    --api-port N    API port (default 8000)
#    --ui-port N     UI dev-server port (default 5173)
#    --host H        bind address (default 127.0.0.1; use 0.0.0.0 to expose on your LAN)
#    --browser       also install Playwright + Chromium (JavaScript rendering for the browser tool)
#    --detach        run in the background; use "./startup.sh stop" / "logs"
#    --open          open the app in your browser once it is ready
#    -y, --yes       don't ask for confirmation
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
RUN_DIR="$ROOT/.run"
VENV="$BACKEND/.venv"

CMD="dev"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-5173}"
HOST="${HOST:-127.0.0.1}"
WITH_BROWSER=0
DETACH=0
OPEN=0
YES=0

# ------------------------------------------------------------------ output helpers
if [ -t 1 ]; then
  B=$'\033[1m'; DIM=$'\033[2m'; R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; C=$'\033[36m'; P=$'\033[35m'; N=$'\033[0m'
else
  B=""; DIM=""; R=""; G=""; Y=""; C=""; P=""; N=""
fi
info() { printf "%s›%s %s\n" "$C" "$N" "$*"; }
ok()   { printf "%s✓%s %s\n" "$G" "$N" "$*"; }
warn() { printf "%s!%s %s\n" "$Y" "$N" "$*"; }
die()  { printf "%s✗ %s%s\n" "$R" "$*" "$N" >&2; exit 1; }
banner() {
  printf "\n%s%s  AgentForge%s %s· multi-agent platform%s\n\n" "$B" "$P" "$N" "$DIM" "$N"
}
usage() { sed -n '3,28p' "$0" | sed 's/^# \{0,2\}//'; }

# ------------------------------------------------------------------ args
while [ $# -gt 0 ]; do
  case "$1" in
    dev|prod|docker|setup|test|doctor|stop|logs|reset|help) CMD="$1" ;;
    --api-port) API_PORT="${2:?--api-port needs a value}"; shift ;;
    --ui-port) UI_PORT="${2:?--ui-port needs a value}"; shift ;;
    --host) HOST="${2:?--host needs a value}"; shift ;;
    --browser) WITH_BROWSER=1 ;;
    --detach|-d) DETACH=1 ;;
    --open) OPEN=1 ;;
    -y|--yes) YES=1 ;;
    -h|--help) CMD="help" ;;
    *) die "Unknown argument: $1 (try ./startup.sh help)" ;;
  esac
  shift
done

# ------------------------------------------------------------------ environment checks
find_python() {
  for c in "${PYTHON:-}" python3.13 python3.12 python3.11 python3.10 python3 python; do
    [ -z "$c" ] && continue
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        command -v "$c"
        return 0
      fi
    fi
  done
  return 1
}

check_node() {
  command -v node >/dev/null 2>&1 || die "Node.js 18+ is required (https://nodejs.org)"
  local major
  major="$(node -p 'process.versions.node.split(".")[0]')"
  [ "$major" -ge 18 ] || die "Node.js 18+ is required (found $(node -v))"
}

hash_file() {
  if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else sha256sum "$1" | cut -d' ' -f1; fi
}

port_in_use() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
  fi
}

require_free_port() {
  if port_in_use "$1"; then
    die "Port $1 is already in use ($2). Stop that process or pass $3 <port>."
  fi
}

gen_secret() {
  "$PY" -c 'import secrets; print(secrets.token_urlsafe(48))'
}

ensure_env() {
  if [ ! -f "$BACKEND/.env" ]; then
    cp "$BACKEND/.env.example" "$BACKEND/.env"
    ok "Created backend/.env from .env.example (add provider API keys there or in the UI)"
  fi
}

ensure_secret_key() {
  # Production needs SECRET_KEY >= 32 chars. Reuse the dev key (backend/data/.secret_key) when present
  # so secrets encrypted in dev mode stay readable; otherwise generate one.
  local result
  result="$("$PY" - "$BACKEND/.env" "$BACKEND/data/.secret_key" <<'PYEOF'
import pathlib, re, secrets, sys
env, devkey = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
text = env.read_text()
m = re.search(r"(?m)^SECRET_KEY=(.*)$", text)
value = re.split(r"\s+#", m.group(1), maxsplit=1)[0].strip().strip("'\"") if m else ""
if len(value) >= 32:
    print("present")
    sys.exit(0)
key = devkey.read_text().strip() if devkey.exists() and len(devkey.read_text().strip()) >= 32 else secrets.token_urlsafe(48)
line = "SECRET_KEY=" + key
text = re.sub(r"(?m)^SECRET_KEY=.*$", line, text) if m else text.rstrip("\n") + "\n" + line + "\n"
env.write_text(text)
print("reused" if devkey.exists() and key == devkey.read_text().strip() else "generated")
PYEOF
)"
  chmod 600 "$BACKEND/.env" 2>/dev/null || true
  case "$result" in
    generated) ok "Generated a SECRET_KEY in backend/.env (keep it safe - it encrypts stored secrets)" ;;
    reused) ok "Saved your development encryption key as SECRET_KEY in backend/.env" ;;
  esac
}

# ------------------------------------------------------------------ setup
setup_backend() {
  PY="$(find_python)" || die "Python 3.10+ is required (found: $(python3 --version 2>&1 || echo none)). Install it, or set PYTHON=/path/to/python3.x"
  if [ ! -x "$VENV/bin/python" ]; then
    info "Creating Python virtualenv with $("$PY" --version)..."
    "$PY" -m venv "$VENV"
  fi
  local stamp="$VENV/.req-hash" want
  want="$(cat "$BACKEND/requirements.txt" "$BACKEND/requirements-dev.txt" | { if command -v shasum >/dev/null 2>&1; then shasum -a 256; else sha256sum; fi; } | cut -d' ' -f1)"
  if [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$want" ]; then
    info "Installing backend dependencies..."
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q -r "$BACKEND/requirements-dev.txt"
    echo "$want" > "$stamp"
    ok "Backend dependencies installed"
  else
    ok "Backend dependencies up to date"
  fi
  if [ "$WITH_BROWSER" = 1 ]; then
    info "Installing Playwright + Chromium (browser tool JavaScript rendering)..."
    "$VENV/bin/pip" install -q playwright
    "$VENV/bin/python" -m playwright install chromium
    ok "Headless browser installed"
  fi
}

setup_frontend() {
  check_node
  local stamp="$FRONTEND/node_modules/.lock-hash" want
  want="$(hash_file "$FRONTEND/package-lock.json")"
  if [ ! -d "$FRONTEND/node_modules" ] || [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$want" ]; then
    info "Installing frontend packages..."
    (cd "$FRONTEND" && npm install --no-audit --no-fund --loglevel=error)
    echo "$want" > "$stamp"
    ok "Frontend packages installed"
  else
    ok "Frontend packages up to date"
  fi
}

# ------------------------------------------------------------------ process management
PIDS=""
cleanup() {
  if [ -n "$PIDS" ]; then
    printf "\n"
    info "Stopping AgentForge..."
    for pid in $PIDS; do kill "$pid" 2>/dev/null || true; done
    wait 2>/dev/null || true
    ok "Stopped"
  fi
}

start_proc() { # name, dir, command...
  local name="$1" dir="$2"; shift 2
  mkdir -p "$RUN_DIR"
  if [ "$DETACH" = 1 ]; then
    # fully detached: no inherited stdin/stdout, survives the terminal closing
    (cd "$dir" && exec nohup "$@" >"$RUN_DIR/$name.log" 2>&1 </dev/null) &
    echo $! >"$RUN_DIR/$name.pid"
  else
    (cd "$dir" && exec "$@") &
    PIDS="$PIDS $!"
  fi
}

wait_http() { # url, label, seconds
  local url="$1" label="$2" secs="${3:-60}" i=0
  while [ "$i" -lt "$secs" ]; do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then ok "$label is up"; return 0; fi
    sleep 1; i=$((i + 1))
  done
  if [ "$DETACH" = 1 ]; then warn "$label did not respond within ${secs}s - check ./startup.sh logs"
  else warn "$label did not respond within ${secs}s - check the output above"; fi
  return 1
}

open_url() {
  [ "$OPEN" = 1 ] || return 0
  if command -v open >/dev/null 2>&1; then open "$1"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1" >/dev/null 2>&1 &
  fi
}

display_host() { [ "$HOST" = "0.0.0.0" ] && echo "localhost" || echo "$HOST"; }

finish() { # ui_url api_url
  printf "\n  %sApp%s   %s\n  %sAPI%s   %s/docs\n" "$B" "$N" "$1" "$B" "$N" "$2"
  if [ "$DETACH" = 1 ]; then
    printf "\n  Running in the background. %s./startup.sh logs%s to follow, %s./startup.sh stop%s to stop.\n\n" "$B" "$N" "$B" "$N"
  else
    printf "\n  Press %sCtrl+C%s to stop.\n\n" "$B" "$N"
  fi
  open_url "$1"
}

# ------------------------------------------------------------------ commands
cmd_dev() {
  banner
  setup_backend
  setup_frontend
  ensure_env
  require_free_port "$API_PORT" "API" "--api-port"
  require_free_port "$UI_PORT" "UI" "--ui-port"
  trap cleanup EXIT INT TERM
  local h; h="$(display_host)"
  info "Starting API on http://$h:$API_PORT (auto-reload)..."
  CORS_ORIGINS="http://$h:$UI_PORT,http://localhost:$UI_PORT,http://127.0.0.1:$UI_PORT" \
  PUBLIC_BASE_URL="http://$h:$API_PORT" \
    start_proc api "$BACKEND" "$VENV/bin/uvicorn" app.main:app --reload --host "$HOST" --port "$API_PORT"
  info "Starting UI on http://$h:$UI_PORT..."
  AGENTFORGE_API_PORT="$API_PORT" start_proc ui "$FRONTEND" npx vite --host "$HOST" --port "$UI_PORT" --strictPort
  wait_http "http://127.0.0.1:$API_PORT/api/health" "API" 60 || true
  wait_http "http://127.0.0.1:$UI_PORT/" "UI" 60 || true
  finish "http://$h:$UI_PORT" "http://$h:$API_PORT"
  if [ "$DETACH" = 1 ]; then PIDS=""; trap - EXIT INT TERM; return 0; fi
  wait
}

cmd_prod() {
  banner
  setup_backend
  setup_frontend
  ensure_env
  ensure_secret_key
  require_free_port "$API_PORT" "server" "--api-port"
  info "Building the UI..."
  (cd "$FRONTEND" && npm run build --silent)
  ok "UI built (served by the API from frontend/dist)"
  trap cleanup EXIT INT TERM
  local h; h="$(display_host)"
  info "Starting AgentForge on http://$h:$API_PORT (production mode)..."
  # one worker: the scheduler and live run streams are in-process (scale out with a job queue)
  ENV=production \
  CORS_ORIGINS="http://$h:$API_PORT" \
  PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://$h:$API_PORT}" \
    start_proc api "$BACKEND" "$VENV/bin/uvicorn" app.main:app --host "$HOST" --port "$API_PORT" --proxy-headers --no-server-header
  wait_http "http://127.0.0.1:$API_PORT/api/health" "Server" 60 || true
  printf "\n  %sApp%s   http://%s:%s\n" "$B" "$N" "$h" "$API_PORT"
  printf "  %sNote%s  /docs is disabled in production mode\n" "$DIM" "$N"
  if [ "$DETACH" = 1 ]; then
    printf "\n  Running in the background. %s./startup.sh stop%s to stop.\n\n" "$B" "$N"
    PIDS=""; trap - EXIT INT TERM; open_url "http://$h:$API_PORT"; return 0
  fi
  printf "\n  Press %sCtrl+C%s to stop.\n\n" "$B" "$N"
  open_url "http://$h:$API_PORT"
  wait
}

cmd_docker() {
  banner
  command -v docker >/dev/null 2>&1 || die "Docker is not installed (https://docs.docker.com/get-docker/)"
  PY="$(find_python || command -v python3)"
  ensure_env
  ensure_secret_key
  info "Building and starting containers (app + Postgres + Redis)..."
  cd "$ROOT"
  if [ "$DETACH" = 1 ]; then
    docker compose up --build -d
    wait_http "http://127.0.0.1:8000/api/health" "AgentForge" 120 || true
    ok "Running at http://localhost:8000  (docker compose logs -f app · docker compose down)"
  else
    docker compose up --build
  fi
}

cmd_setup() {
  banner
  setup_backend
  setup_frontend
  ensure_env
  ok "Setup complete. Start with: ./startup.sh"
}

cmd_test() {
  banner
  setup_backend
  setup_frontend
  info "Backend tests..."
  (cd "$BACKEND" && "$VENV/bin/python" -m pytest -q)
  info "Frontend type-check..."
  (cd "$FRONTEND" && npx tsc -p tsconfig.json)
  ok "All checks passed"
}

cmd_doctor() {
  banner
  local p
  if p="$(find_python)"; then ok "Python: $("$p" --version) ($p)"; else warn "Python 3.10+ not found"; fi
  if command -v node >/dev/null 2>&1; then ok "Node: $(node -v)"; else warn "Node.js not found"; fi
  if [ -x "$VENV/bin/python" ]; then ok "Backend virtualenv: present"; else warn "Backend virtualenv missing - run ./startup.sh setup"; fi
  if [ -d "$FRONTEND/node_modules" ]; then ok "Frontend packages: present"; else warn "Frontend packages missing - run ./startup.sh setup"; fi
  if [ -f "$BACKEND/.env" ]; then ok "backend/.env: present"; else warn "backend/.env missing (created automatically on first start)"; fi
  for port in "$API_PORT" "$UI_PORT"; do
    if port_in_use "$port"; then warn "Port $port is in use"; else ok "Port $port is free"; fi
  done
  local found=0 k
  for k in ANTHROPIC_API_KEY OPENAI_API_KEY GROQ_API_KEY GEMINI_API_KEY OPENROUTER_API_KEY DEEPSEEK_API_KEY MISTRAL_API_KEY; do
    if [ -n "${!k:-}" ] || { [ -f "$BACKEND/.env" ] && grep -Eq "^$k=.+" "$BACKEND/.env"; }; then ok "Model key: $k"; found=1; fi
  done
  [ "$found" = 1 ] || warn "No model API key found - agents use the offline mock model until you add one (Settings → Models or backend/.env)"
  if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'import playwright' 2>/dev/null; then ok "Playwright: installed (JS rendering enabled)"; else info "Playwright not installed (optional: ./startup.sh setup --browser)"; fi
  if command -v docker >/dev/null 2>&1; then ok "Docker: $(docker --version | cut -d, -f1)"; else info "Docker not installed (optional)"; fi
}

cmd_stop() {
  local any=0 f pid
  for f in "$RUN_DIR"/*.pid; do
    [ -e "$f" ] || continue
    pid="$(cat "$f")"
    if kill -0 "$pid" 2>/dev/null; then
      # stop the process and its children (uvicorn reloader, vite)
      pkill -TERM -P "$pid" 2>/dev/null || true
      kill "$pid" 2>/dev/null || true
      ok "Stopped $(basename "$f" .pid) (pid $pid)"
      any=1
    fi
    rm -f "$f"
  done
  [ "$any" = 1 ] || info "Nothing to stop"
}

cmd_logs() {
  ls "$RUN_DIR"/*.log >/dev/null 2>&1 || die "No logs yet - start with ./startup.sh --detach"
  tail -n 50 -f "$RUN_DIR"/*.log
}

cmd_reset() {
  local data="$BACKEND/data"
  [ -d "$data" ] || { info "No local data to delete"; return 0; }
  if [ "$YES" != 1 ]; then
    printf "%sThis deletes the local database, encryption key and all local AgentForge data in backend/data.%s\nContinue? [y/N] " "$Y" "$N"
    read -r answer
    case "$answer" in y|Y|yes|YES) ;; *) info "Cancelled"; return 0 ;; esac
  fi
  if port_in_use "$API_PORT"; then die "Stop the running server first (./startup.sh stop or Ctrl+C)"; fi
  rm -rf "$data"
  ok "Local data deleted. The next account you register becomes the platform admin."
}

case "$CMD" in
  dev) cmd_dev ;;
  prod) cmd_prod ;;
  docker) cmd_docker ;;
  setup) cmd_setup ;;
  test) cmd_test ;;
  doctor) cmd_doctor ;;
  stop) cmd_stop ;;
  logs) cmd_logs ;;
  reset) cmd_reset ;;
  help) usage ;;
esac
