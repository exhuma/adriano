#!/usr/bin/env bash
# Push one ADR Markdown file to adriano as a candidate, the way a CI job
# pushes a candidate from a feature branch (see docs/operator.md "CI push
# example" and SPEC.md's push-intake requirements).
#
# Usage:
#   samples/push-candidate.sh <file.md> <project> <ref> [source_id] \
#     [delivery_id]
#
# Example (the "use Redis" candidate demo, against the demo stack):
#   export ADRIANO_PUSH_TOKEN_CENTRAL=<token from .env.demo>
#   samples/push-candidate.sh \
#     samples/candidates/2026-01-05-use-redis-for-caching.md \
#     platform feature/redis-cache
#
# Reads the push token from the environment variable named
# ADRIANO_PUSH_TOKEN_<SOURCE_ID UPPERCASED> (default source id: central,
# matching catalog.demo.yaml's push_tokens_env: [ADRIANO_PUSH_TOKEN_CENTRAL]).
# No token is ever hard-coded or committed here.
#
# Env vars:
#   ADRIANO_API_BASE_URL  Base URL of the running API (default:
#                         http://localhost:8180, the demo frontend's
#                         nginx proxy; point it at a backend port
#                         directly if you published one instead).
set -euo pipefail

file="${1:?usage: push-candidate.sh <file.md> <project> <ref> [source_id] [delivery_id]}"
project="${2:?usage: push-candidate.sh <file.md> <project> <ref> [source_id] [delivery_id]}"
ref="${3:?usage: push-candidate.sh <file.md> <project> <ref> [source_id] [delivery_id]}"
source_id="${4:-central}"
delivery_id="${5:-}"

api_base="${ADRIANO_API_BASE_URL:-http://localhost:8180}"

if [ ! -f "$file" ]; then
  echo "error: no such file: $file" >&2
  exit 1
fi

token_var="ADRIANO_PUSH_TOKEN_$(printf '%s' "$source_id" | tr '[:lower:]' '[:upper:]')"
token="${!token_var:-}"
if [ -z "$token" ]; then
  echo "error: $token_var is not set in the environment" >&2
  echo "       (in the demo stack, see .env.demo for its value)" >&2
  exit 1
fi

# Extract the record's uuid from its YAML frontmatter (first `uuid:` line
# inside the leading --- ... --- block). jq is deliberately not required;
# JSON is built with python3's json.dumps so content escaping (quotes,
# newlines, unicode) is always correct.
adr_uuid="$(python3 - "$file" <<'PY'
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as fh:
    lines = fh.readlines()

if not lines or lines[0].strip() != "---":
    sys.exit("no YAML frontmatter found")

uuid_value = ""
for line in lines[1:]:
    if line.strip() == "---":
        break
    stripped = line.strip()
    if stripped.startswith("uuid:"):
        uuid_value = stripped.split(":", 1)[1].strip()
        break

if not uuid_value:
    sys.exit("no `uuid:` field found in frontmatter")
print(uuid_value)
PY
)"

body="$(python3 - "$file" "$source_id" "$project" "$adr_uuid" "$ref" \
    "$delivery_id" <<'PY'
import json
import sys

file_path, source_id, project, adr_uuid, ref, delivery_id = sys.argv[1:7]

with open(file_path, "r", encoding="utf-8") as fh:
    content = fh.read()

payload = {
    "source_id": source_id,
    "project": project,
    "adr_uuid": adr_uuid,
    "ref": ref,
    "content": content,
}
if delivery_id:
    payload["delivery_id"] = delivery_id

print(json.dumps(payload))
PY
)"

echo "PUT $api_base/api/v1/candidates" \
  "(source=$source_id project=$project ref=$ref uuid=$adr_uuid)" >&2

curl -fsS -X PUT "$api_base/api/v1/candidates" \
  -H "Authorization: Bearer $token" \
  -H "Content-Type: application/json" \
  --data-binary "$body"
echo
