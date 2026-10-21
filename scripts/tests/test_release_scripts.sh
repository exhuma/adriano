#!/usr/bin/env bash
# Self-tests for check_version_sync.sh and derive_channels.sh
# (module-calver-release-channels "Testing"). Run from anywhere:
#
#   scripts/tests/test_release_scripts.sh
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scripts="$here/.."
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

failures=0

pass() { echo "ok   - $1"; }
fail() {
  echo "FAIL - $1"
  failures=$((failures + 1))
}

# write_manifests NPM_VERSION PY_VERSION
write_manifests() {
  printf '{"name": "x", "version": "%s"}\n' "$1" >"$work/package.json"
  printf '[project]\nname = "x"\nversion = "%s"\n' "$2" \
    >"$work/pyproject.toml"
}

# sync TAG -> runs the guard against the manifests in $work
sync() {
  NPM_MANIFEST="$work/package.json" PY_MANIFEST="$work/pyproject.toml" \
    "$scripts/check_version_sync.sh" "$1" 2>&1
}

# expect_sync_ok NAME TAG NPM_VERSION PY_VERSION
expect_sync_ok() {
  write_manifests "$3" "$4"
  if out="$(sync "$2")"; then pass "$1"; else
    fail "$1: $out"
  fi
}

# expect_sync_fail NAME TAG NPM_VERSION PY_VERSION MANIFEST_NAME
expect_sync_fail() {
  write_manifests "$3" "$4"
  if out="$(sync "$2")"; then
    fail "$1: expected failure"
  elif printf '%s' "$out" | grep -q "^::error.*$5"; then
    pass "$1"
  else
    fail "$1: no ::error:: naming $5: $out"
  fi
}

# expect_channels NAME TAG CHANNELS
expect_channels() {
  got="$("$scripts/derive_channels.sh" "$2" 2>&1)"
  if [ "$got" = "$3" ]; then pass "$1"; else
    fail "$1: got '$got', want '$3'"
  fi
}

# Version-sync guard: matching tags pass, with PEP 440 mapping.
expect_sync_ok "stable tag passes" v2026.6.15 2026.6.15 2026.6.15
expect_sync_ok "alpha maps to aN" v2026.6.15-alpha.1 \
  2026.6.15-alpha.1 2026.6.15a1
expect_sync_ok "beta maps to bN" v2026.6.15-beta.2 \
  2026.6.15-beta.2 2026.6.15b2
expect_sync_ok "rc maps to rcN" v2026.6.15-rc.3 2026.6.15-rc.3 2026.6.15rc3

# Version-sync guard: drift in either manifest fails and names it.
expect_sync_fail "npm drift fails" v2026.6.15 2026.6.14 2026.6.15 package.json
expect_sync_fail "python drift fails" v2026.6.15 2026.6.15 2026.6.14 \
  pyproject.toml
expect_sync_fail "python verbatim pre-release fails" v2026.6.15-alpha.1 \
  2026.6.15-alpha.1 2026.6.15-alpha.1 pyproject.toml
expect_sync_fail "npm in PEP 440 form fails" v2026.6.15-alpha.1 \
  2026.6.15a1 2026.6.15a1 package.json

# Version-sync guard: malformed tags and missing argument.
write_manifests 0.1.0 0.1.0
for bad in v1.2.3 v2026.06.15 2026.6 vfoo v2026.6.15-alpha v2026.6.15-x.1; do
  if out="$(sync "$bad")"; then
    fail "malformed tag $bad accepted"
  elif printf '%s' "$out" | grep -q '^::error::'; then
    pass "malformed tag $bad rejected"
  else
    fail "malformed tag $bad: no ::error:: line: $out"
  fi
done
if env -u GITHUB_REF_NAME NPM_MANIFEST="$work/package.json" \
  PY_MANIFEST="$work/pyproject.toml" \
  "$scripts/check_version_sync.sh" >/dev/null 2>&1; then
  fail "missing tag accepted"
else
  pass "missing tag rejected"
fi

# GITHUB_REF_NAME is the default tag.
write_manifests 2026.6.15 2026.6.15
if GITHUB_REF_NAME=v2026.6.15 NPM_MANIFEST="$work/package.json" \
  PY_MANIFEST="$work/pyproject.toml" \
  "$scripts/check_version_sync.sh" >/dev/null 2>&1; then
  pass "GITHUB_REF_NAME is the default tag"
else
  fail "GITHUB_REF_NAME default not honoured"
fi

# Channel derivation per tag class, with the mandatory cascade.
expect_channels "alpha channels" v2026.6.15-alpha.1 "alpha"
expect_channels "beta cascades to alpha" v2026.6.15-beta.2 "beta alpha"
expect_channels "rc is its own channel" v2026.6.15-rc.1 "rc"
expect_channels "stable cascades to all" v2026.6.15 "stable beta alpha"
if "$scripts/derive_channels.sh" v2026.6.15 | grep -qw latest; then
  fail "a channel named latest was produced"
else
  pass "no latest channel is produced"
fi
if "$scripts/derive_channels.sh" notatag >/dev/null 2>&1; then
  fail "channels accepted a malformed tag"
else
  pass "channels reject a malformed tag"
fi

echo
if [ "$failures" -ne 0 ]; then
  echo "$failures check(s) failed"
  exit 1
fi
echo "all checks passed"
