#!/usr/bin/env bash
# Print the moving release channels a tag advances, space-separated.
#
# Usage: scripts/derive_channels.sh [TAG]
#
# TAG defaults to $GITHUB_REF_NAME (module-calver-release-channels).
# Channels cascade by maturity (stable > beta > alpha); rc is separate:
#
#   vYYYY.M.D-alpha.N  ->  alpha
#   vYYYY.M.D-beta.N   ->  beta alpha
#   vYYYY.M.D-rc.N     ->  rc
#   vYYYY.M.D          ->  stable beta alpha
set -euo pipefail

tag="${1:-${GITHUB_REF_NAME:-}}"
if [ -z "$tag" ]; then
  echo "::error::no tag given: pass vYYYY.M.D[-alpha.N] as argument" \
    "or set GITHUB_REF_NAME" >&2
  exit 2
fi

ref="${tag#v}"
calver='^[0-9]{4}\.[1-9][0-9]?\.[1-9][0-9]?(-(alpha|beta|rc)\.[1-9][0-9]*)?$'
if ! printf '%s' "$ref" | grep -Eq "$calver"; then
  echo "::error::tag '$tag' is not a CalVer tag; expected" \
    "vYYYY.M.D or vYYYY.M.D-(alpha|beta|rc).N" >&2
  exit 2
fi

case "$ref" in
  *-alpha.*) channels="alpha" ;;
  *-beta.*) channels="beta alpha" ;;
  *-rc.*) channels="rc" ;;
  *) channels="stable beta alpha" ;; # no pre-release == stable
esac
echo "$channels"
