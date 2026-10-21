#!/usr/bin/env bash
# Fail unless every package manifest carries the release tag's version.
#
# Usage: scripts/check_version_sync.sh [TAG]
#
# TAG defaults to $GITHUB_REF_NAME and has the CalVer form
# vYYYY.M.D[-alpha.N|-beta.N|-rc.N] (module-calver-release-channels).
# Each manifest is compared in its ecosystem's canonical form:
#
#   frontend/package.json    npm keeps the tag verbatim (2026.6.15-rc.1)
#   backend/pyproject.toml   PEP 440 (2026.6.15rc1)
#
# Manifest paths can be overridden with NPM_MANIFEST / PY_MANIFEST
# (used by the self-tests). Needs python3 (3.11+ for tomllib).
set -euo pipefail

tag="${1:-${GITHUB_REF_NAME:-}}"
npm_manifest="${NPM_MANIFEST:-frontend/package.json}"
py_manifest="${PY_MANIFEST:-backend/pyproject.toml}"

if [ -z "$tag" ]; then
  echo "::error::no tag given: pass vYYYY.M.D[-alpha.N] as argument" \
    "or set GITHUB_REF_NAME"
  exit 2
fi

version="${tag#v}"
calver='^[0-9]{4}\.[1-9][0-9]?\.[1-9][0-9]?(-(alpha|beta|rc)\.[1-9][0-9]*)?$'
if ! printf '%s' "$version" | grep -Eq "$calver"; then
  echo "::error::tag '$tag' is not a CalVer tag; expected" \
    "vYYYY.M.D or vYYYY.M.D-(alpha|beta|rc).N, e.g. v2026.6.15-rc.1"
  exit 2
fi

# npm keeps the tag form verbatim; PEP 440 maps -alpha. -> a,
# -beta. -> b and -rc. -> rc.
pep440="$(printf '%s' "$version" |
  sed -E 's/-alpha\./a/; s/-beta\./b/; s/-rc\./rc/')"

npm_version="$(python3 -c '
import json, sys
print(json.load(open(sys.argv[1]))["version"])
' "$npm_manifest")"
py_version="$(python3 -c '
import sys, tomllib
with open(sys.argv[1], "rb") as handle:
    print(tomllib.load(handle)["project"]["version"])
' "$py_manifest")"

status=0
if [ "$npm_version" != "$version" ]; then
  echo "::error file=$npm_manifest::$npm_manifest version" \
    "($npm_version) != tag ($version); set \"version\" to $version"
  status=1
fi
if [ "$py_version" != "$pep440" ]; then
  echo "::error file=$py_manifest::$py_manifest version" \
    "($py_version) != expected ($pep440, the PEP 440 form of $version);" \
    "set version = \"$pep440\""
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "Version sync OK: tag $tag, npm $npm_version, python $py_version"
fi
exit "$status"
