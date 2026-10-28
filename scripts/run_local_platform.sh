#!/bin/sh
# Local platform workflow (Termux-compatible; no Render dependency).
#
# Starts the platform application server (which serves both the API and the
# built SPA), waits for readiness, optionally runs the local publication -> 
# snapshot proof with an EPHEMERAL service key, and shuts down children via trap.
#
# The service key exists only in this process environment. It is never
# written to disk, logged, or committed.
#
# Usage:
#   sh scripts/run_local_platform.sh [--skip-proof] [--skip-spa-build]
#
set -u

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PORT="${PORT:-8000}"
PERSISTENCE_DIR="${PERSISTENCE_DIR:-$ROOT/.data-local-proof}"
SKIP_PROOF=0
SKIP_SPA_BUILD=0

for arg in "$@"; do
  case "$arg" in
    --skip-proof) SKIP_PROOF=1 ;;
    --skip-spa-build) SKIP_SPA_BUILD=1 ;;
    *) echo "[FAIL] Unknown argument: $arg"; exit 2 ;;
  esac
done

command -v python3 >/dev/null 2>&1 || { echo "[FAIL] python3 not found."; exit 1; }

if [ "$SKIP_SPA_BUILD" -eq 0 ]; then
  command -v npm >/dev/null 2>&1 || { echo "[FAIL] npm not found; run with --skip-spa-build if web/dist already exists."; exit 1; }
  echo "[RUN] Building SPA bundle (web/dist)..."
  (cd "$ROOT/web" && npm run build) || { echo "[FAIL] SPA build failed."; exit 1; }
fi

if [ ! -f "$ROOT/web/dist/index.html" ]; then
  echo "[FAIL] web/dist/index.html missing. Build the SPA first, or omit --skip-spa-build."
  exit 1
fi

# Ephemeral shared key: generated in-memory, exported only to this process tree.
if [ -n "${PROJECT1_SERVICE_KEY:-}" ]; then
  echo "[RUN] Using pre-configured PROJECT1_SERVICE_KEY from environment (not displayed)."
else
  PROJECT1_SERVICE_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export PROJECT1_SERVICE_KEY
fi

mkdir -p "$PERSISTENCE_DIR"

echo "[RUN] Starting platform server on port $PORT (persistence: $PERSISTENCE_DIR)..."
cd "$ROOT"
APP_ENV="development" PORT="$PORT" HOST="${HOST:-127.0.0.1}" \
  PERSISTENCE_DIR="$PERSISTENCE_DIR" \
  python3 -m src.platform.server &
SERVER_PID=$!

cleanup() {
  echo "[RUN] Shutting down server (pid $SERVER_PID)..."
  kill "$SERVER_PID" 2>/dev/null
  wait "$SERVER_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

ready=0
i=0
while [ "$i" -lt 60 ]; do
  if python3 - "$PORT" <<EOF >/dev/null 2>&1
import urllib.request, sys
urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/health", timeout=2)
EOF
  then ready=1; break; fi
  i=$((i+1))
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  echo "[FAIL] Server did not become ready within 60s."
  exit 1
fi
echo "[OK] Server ready at http://127.0.0.1:$PORT (UI: /, API: /api/v1/snapshot)"

if [ "$SKIP_PROOF" -eq 0 ]; then
  echo "[RUN] Running local publication -> snapshot proof with this run's ephemeral key..."
  python3 scripts/verify_local_signal_path.py \
    --base-url "http://127.0.0.1:$PORT" \
    --symbol "${PROOF_SYMBOL:-XAUUSD}" \
    --timeframe "${PROOF_TIMEFRAME:-1H}" \
    --decision "${PROOF_DECISION:-buy}" || {
      echo "[FAIL] Publication proof failed; server kept running for inspection until Ctrl+C."
      wait "$SERVER_PID"
    }
fi

echo "[OK] Platform running. Open http://127.0.0.1:$PORT then press Ctrl+C to stop."
wait "$SERVER_PID"
