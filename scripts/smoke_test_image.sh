#!/usr/bin/env bash
# Smoke-test a built adriano image against a throwaway PostgreSQL 18.
#
# Usage: scripts/smoke_test_image.sh IMAGE [BASE_URL] [EXPECTED_VERSION]
#
#   IMAGE             image reference to test, e.g. adriano:local
#   BASE_URL          where the container is published on the host
#                     (default http://127.0.0.1:8000; only the port is
#                     used, the container is bound to 127.0.0.1)
#   EXPECTED_VERSION  when given, /healthz must report exactly this
#                     version (the ADRIANO_VERSION build argument)
#
# Needs docker, curl and python3. The script starts its own PostgreSQL
# container on a private network, starts the image twice (the second
# start must find the migrations already applied) and removes
# everything on exit. On failure it prints `docker logs` of the
# application container.
#
# SMOKE_ASSERT_ONLY=1 skips docker entirely and only runs the HTTP
# assertions against a server already listening at BASE_URL (which
# must have been configured as below); used to check this script
# against a locally started `adriano serve`.
set -euo pipefail

image="${1:?usage: smoke_test_image.sh IMAGE [BASE_URL] [EXPECTED_VERSION]}"
base_url="${2:-http://127.0.0.1:8000}"
expected_version="${3:-}"

host_port="${base_url##*:}"
host_port="${host_port%%/*}"
idp="https://idp.example.test"
client_id="adriano-smoke"
suffix="$$"
network="adriano-smoke-net-$suffix"
db_name="adriano-smoke-db-$suffix"
app_name="adriano-smoke-app-$suffix"
workdir="$(mktemp -d)"
dsn="postgresql://adriano:adriano@$db_name:5432/adriano"

fail() {
  echo "SMOKE FAIL: $*" >&2
  exit 1
}

cleanup() {
  status=$?
  if [ "${SMOKE_ASSERT_ONLY:-0}" != "1" ]; then
    if [ "$status" -ne 0 ]; then
      echo "--- docker logs ($app_name) ---" >&2
      docker logs "$app_name" >&2 || true
    fi
    docker rm -f "$app_name" "$db_name" >/dev/null 2>&1 || true
    docker network rm "$network" >/dev/null 2>&1 || true
  fi
  rm -rf "$workdir"
  exit "$status"
}
trap cleanup EXIT

# A minimal valid catalog: no sources, a policy, two roles.
write_catalog() {
  cat >"$workdir/catalog.yaml" <<'YAML'
sources: []
approval_policy:
  id: smoke
  version: 1
  required: true
  reviewers:
    users: []
    roles: [reviewer]
  allow_self_approval: false
rbac:
  roles:
    reader: [read]
    reviewer: [read]
YAML
  # The container user (uid 10001) must be able to read the mount.
  chmod 0644 "$workdir/catalog.yaml"
}

start_database() {
  docker network create "$network" >/dev/null
  docker run -d --name "$db_name" --network "$network" \
    -e POSTGRES_USER=adriano -e POSTGRES_PASSWORD=adriano \
    -e POSTGRES_DB=adriano postgres:18 >/dev/null
  for _ in $(seq 1 60); do
    if docker exec "$db_name" pg_isready -U adriano -d adriano \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  docker logs "$db_name" >&2 || true
  fail "PostgreSQL did not become ready within 60s"
}

# Start (or restart from scratch) the application container.
start_app() {
  docker rm -f "$app_name" >/dev/null 2>&1 || true
  docker run -d --name "$app_name" --network "$network" \
    -p "127.0.0.1:${host_port}:8000" \
    -v "$workdir/catalog.yaml:/app/catalog.yaml:ro" \
    -e "ADRIANO_DATABASE_URL=$dsn" \
    -e ADRIANO_CONFIG_FILE=/app/catalog.yaml \
    -e "ADRIANO_OIDC_AUTHORITY=$idp/realms/x" \
    -e "ADRIANO_OIDC_CLIENT_ID=$client_id" \
    "$image" >/dev/null
}

wait_healthy() {
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "$base_url/healthz" 2>/dev/null; then
      return 0
    fi
    if [ "${SMOKE_ASSERT_ONLY:-0}" != "1" ] &&
      [ "$(docker inspect -f '{{.State.Running}}' "$app_name")" != true ]; then
      fail "the application container exited during startup"
    fi
    sleep 1
  done
  fail "/healthz did not answer 200 within 60s"
}

# http_get PATH -> sets $status, $headers_file, $body_file
http_get() {
  headers_file="$workdir/headers"
  body_file="$workdir/body"
  status="$(curl -sS -D "$headers_file" -o "$body_file" \
    -w '%{http_code}' "$base_url$1")"
}

# header NAME -> value of the response header (case-insensitive)
header() {
  grep -i "^$1:" "$headers_file" | head -n 1 | cut -d: -f2- |
    tr -d '\r' | sed -E 's/^ +//'
}

json_field() {
  python3 -c '
import json, sys
print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))
' "$body_file" "$1"
}

check_endpoints() {
  http_get /healthz
  [ "$status" = 200 ] || fail "/healthz returned $status, want 200"
  version="$(json_field version)"
  [ -n "$version" ] || fail "/healthz reports no version"
  if [ -n "$expected_version" ] && [ "$version" != "$expected_version" ]; then
    fail "/healthz version '$version' != expected '$expected_version'"
  fi
  [ "$(json_field database)" = ok ] ||
    fail "/healthz database is '$(json_field database)', want ok"

  http_get /config.js
  [ "$status" = 200 ] || fail "/config.js returned $status, want 200"
  grep -q "$client_id" "$body_file" ||
    fail "/config.js does not carry the OIDC client id"
  if grep -qi 'dev' "$body_file"; then
    fail "/config.js mentions a dev key: $(grep -i dev "$body_file")"
  fi

  http_get /
  [ "$status" = 200 ] || fail "/ returned $status, want 200"
  case "$(header content-type)" in
    text/html*) ;;
    *) fail "/ content-type is '$(header content-type)', want text/html" ;;
  esac
  case "$(header content-security-policy)" in
    *"$idp"*) ;;
    *) fail "CSP lacks $idp: '$(header content-security-policy)'" ;;
  esac
  asset="$(grep -oE '/assets/[^"]+' "$body_file" | head -n 1 || true)"
  [ -n "$asset" ] || fail "index.html references no /assets/ file"

  http_get /records/some-id
  [ "$status" = 200 ] || fail "/records/some-id returned $status, want 200"
  case "$(header content-type)" in
    text/html*) ;;
    *) fail "SPA fallback content-type is '$(header content-type)'" ;;
  esac

  http_get /api/v1/me
  [ "$status" = 401 ] ||
    fail "/api/v1/me without a token returned $status, want 401"

  http_get /api/nope
  [ "$status" = 404 ] || fail "/api/nope returned $status, want 404"
  case "$(header content-type)" in
    application/json*) ;;
    *) fail "/api/nope content-type is '$(header content-type)'" ;;
  esac

  http_get "$asset"
  [ "$status" = 200 ] || fail "$asset returned $status, want 200"
  case "$(header cache-control)" in
    *immutable*) ;;
    *) fail "$asset cache-control is '$(header cache-control)'" ;;
  esac
}

if [ "${SMOKE_ASSERT_ONLY:-0}" = "1" ]; then
  wait_healthy
  check_endpoints
  echo "SMOKE OK (assertions only)"
  exit 0
fi

write_catalog
start_database

echo "== first start (migrates an empty database)"
start_app
wait_healthy
check_endpoints
uid="$(docker exec "$app_name" id -u)"
[ "$uid" = 10001 ] || fail "container runs as uid $uid, want 10001"

echo "== second start (migrations already applied)"
start_app
wait_healthy
check_endpoints

echo "SMOKE OK: $image"
