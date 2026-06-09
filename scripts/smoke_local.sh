#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-smoke-admin-secret}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

BACKEND_PID=""
FRONTEND_PID=""
COOKIE_JAR="$(mktemp)"

cleanup() {
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    rm -f "$COOKIE_JAR"
}
trap cleanup EXIT INT TERM

wait_for_url() {
    url="$1"
    tries=60
    while [ "$tries" -gt 0 ]; do
        if curl -fsS "$url" >/dev/null 2>&1; then
            return 0
        fi
        tries=$((tries - 1))
        sleep 1
    done
    echo "Timed out waiting for $url" >&2
    return 1
}

cd "$ROOT_DIR/backend"
$PYTHON_BIN manage.py migrate --noinput
$PYTHON_BIN manage.py initadmin
$PYTHON_BIN manage.py runserver "127.0.0.1:$BACKEND_PORT" >/tmp/proxypanel-backend-smoke.log 2>&1 &
BACKEND_PID="$!"

wait_for_url "http://127.0.0.1:$BACKEND_PORT/api/health/"

curl -fsS \
    -b "$COOKIE_JAR" \
    -c "$COOKIE_JAR" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}" \
    "http://127.0.0.1:$BACKEND_PORT/api/auth/login/" >/dev/null
curl -fsS -b "$COOKIE_JAR" "http://127.0.0.1:$BACKEND_PORT/api/auth/me/" >/dev/null

cd "$ROOT_DIR/frontend"
npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" >/tmp/proxypanel-frontend-smoke.log 2>&1 &
FRONTEND_PID="$!"

wait_for_url "http://127.0.0.1:$FRONTEND_PORT/"

echo "Smoke test passed."
