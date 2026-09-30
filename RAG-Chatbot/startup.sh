#!/usr/bin/env bash
# Start the RAG backend (FastAPI) and frontend (Next.js) together.
#   ./startup.sh            backend http://localhost:8002   frontend http://localhost:3002
#   Ctrl+C stops both.
# Override ports:  BACKEND_PORT=9000 FRONTEND_PORT=4000 ./startup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BE_DIR="$ROOT/rag-be"
FE_DIR="$ROOT/rag-ui"
BACKEND_PORT="${BACKEND_PORT:-8002}"
FRONTEND_PORT="${FRONTEND_PORT:-3002}"

# --- backend environment ------------------------------------------------------
if [ ! -d "$BE_DIR/.venv" ]; then
  echo "▶ Creating Python venv (rag-be/.venv)…"
  if command -v uv >/dev/null 2>&1; then uv venv --seed "$BE_DIR/.venv"; else python3 -m venv "$BE_DIR/.venv"; fi
fi
# shellcheck disable=SC1091
source "$BE_DIR/.venv/bin/activate"

# install dependencies only when something is missing (first run takes a few minutes: torch, chromadb…)
if ! python -c "import fastapi, uvicorn, chromadb, sentence_transformers, pypdf, psycopg" >/dev/null 2>&1; then
  echo "▶ Installing backend dependencies (first run only)…"
  if command -v uv >/dev/null 2>&1; then uv pip install -r "$BE_DIR/requirements.txt"; else python -m pip install -r "$BE_DIR/requirements.txt"; fi
fi

# --- frontend dependencies -----------------------------------------------------
if [ ! -d "$FE_DIR/node_modules" ]; then
  echo "▶ Installing frontend dependencies (first run only)…"
  (cd "$FE_DIR" && npm install --no-audit --no-fund)
fi

# refuse to start if a port is taken (otherwise one half silently fails)
for p in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if lsof -ti :"$p" >/dev/null 2>&1; then
    echo "✗ Port $p is already in use. Stop that process or set BACKEND_PORT / FRONTEND_PORT." >&2
    exit 1
  fi
done

# --- run both, stop both on exit -----------------------------------------------
PIDS=()
cleanup() {
  echo; echo "▶ Stopping…"
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "▶ Backend  → http://localhost:$BACKEND_PORT   (API docs: /docs)"
(cd "$BE_DIR" && CORS_ORIGINS="http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT" \
  exec uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload) &
PIDS+=($!)

echo "▶ Frontend → http://localhost:$FRONTEND_PORT"
# BACKEND_URL tells the Next.js /api proxy where the backend is
(cd "$FE_DIR" && BACKEND_URL="http://localhost:$BACKEND_PORT" exec npx next dev -p "$FRONTEND_PORT") &
PIDS+=($!)

# exit as soon as either process dies, so a crash is never hidden
while kill -0 "${PIDS[0]}" 2>/dev/null && kill -0 "${PIDS[1]}" 2>/dev/null; do sleep 1; done
echo "✗ A process exited; shutting down." >&2
exit 1
