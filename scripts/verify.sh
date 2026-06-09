#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

cd "$ROOT_DIR"

docker compose config >/dev/null
docker build --target frontend-test -t proxypanel-frontend-test .
docker compose build
docker run --rm proxypanel python manage.py check
docker run --rm proxypanel python manage.py makemigrations --check --dry-run
docker run --rm proxypanel pytest -q

echo "Verification passed."
