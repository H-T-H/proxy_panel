#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PROJECT_NAME="proxypanel-smoke-$$"
PORT="${PORT:-15173}"
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-smoke-admin-secret}"
DATA_DIR="$(mktemp -d)"
COOKIE_JAR="$(mktemp)"

cleanup() {
    cd "$ROOT_DIR"
    COMPOSE_PROJECT_NAME="$PROJECT_NAME" DATA_DIR="$DATA_DIR" PORT="$PORT" \
        docker compose down --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$DATA_DIR"
    rm -f "$COOKIE_JAR"
}
trap cleanup EXIT INT TERM

wait_for_url() {
    url="$1"
    tries=90
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

api_post() {
    path="$1"
    payload="$2"
    curl -fsS \
        -b "$COOKIE_JAR" \
        -c "$COOKIE_JAR" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "http://127.0.0.1:$PORT$path"
}

cd "$ROOT_DIR"
if [ "${FORCE_BUILD:-0}" = "1" ] || \
    ! docker image inspect proxypanel >/dev/null 2>&1; then
    attempt=1
    until docker compose build; do
        if [ "$attempt" -ge 3 ]; then
            echo "Docker build failed after $attempt attempts." >&2
            exit 1
        fi
        attempt=$((attempt + 1))
        sleep 3
    done
fi

COMPOSE_PROJECT_NAME="$PROJECT_NAME" DATA_DIR="$DATA_DIR" PORT="$PORT" \
    ADMIN_USERNAME="$ADMIN_USERNAME" ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    docker compose up -d

wait_for_url "http://127.0.0.1:$PORT/api/health/"
wait_for_url "http://127.0.0.1:$PORT/"

api_post "/api/auth/login/" "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}" >/dev/null
curl -fsS -b "$COOKIE_JAR" "http://127.0.0.1:$PORT/api/auth/me/" >/dev/null

NODE_RESPONSE="$(api_post "/api/nodes/manual/" '{"node_text":"name: Smoke Node\ntype: ss\nserver: example.com\nport: 8388\ncipher: aes-128-gcm\npassword: secret"}')"
NODE_ID="$(printf '%s' "$NODE_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
USER_RESPONSE="$(api_post "/api/users/" "{\"username\":\"smoke-user\",\"password\":\"smoke-secret\",\"node_ids\":[$NODE_ID]}")"
SUB_PATH="$(printf '%s' "$USER_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["subscription_path"])')"
curl -fsS "http://127.0.0.1:$PORT$SUB_PATH" | grep -q "Smoke Node"

api_post "/api/user-auth/login/" '{"username":"smoke-user","password":"smoke-secret"}' >/dev/null
curl -fsS -b "$COOKIE_JAR" "http://127.0.0.1:$PORT/api/user-auth/me/" | grep -q "smoke-user"
SUBSCRIPTION_INFO="$(curl -fsS -b "$COOKIE_JAR" "http://127.0.0.1:$PORT/api/user/subscription/")"
printf '%s' "$SUBSCRIPTION_INFO" | grep -q "$SUB_PATH"
printf '%s' "$SUBSCRIPTION_INFO" | grep -q "http://127.0.0.1:$PORT$SUB_PATH"
curl -fsS "http://127.0.0.1:$PORT/user/login" | grep -q '<div id="root">'
curl -fsS "http://127.0.0.1:$PORT/user" | grep -q '<div id="root">'

echo "Docker smoke test passed."
