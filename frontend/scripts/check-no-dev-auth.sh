#!/usr/bin/env bash
# Prove the dev-login mechanism never ships in a production build
# (module-dev-auth-bypass "Testing: production-build assertion").
#
# The frontend's dev-auth gate (`src/config.ts` `devAuthEnabled`) is
# a build-time literal (`import.meta.env.DEV && VITE_DEV_AUTH ===
# 'true'`); in a production build `import.meta.env.DEV` is always
# `false`, so `App.vue`'s dynamic `import()` of `DevLoginDialog.vue`
# is unreachable and the bundler's dead-code elimination drops it --
# and everything only it imports (`src/auth/devAuth.ts`,
# `src/api/devAuth.ts`, and the `/auth/dev/token` endpoint path) --
# entirely from `dist/`, regardless of how `VITE_DEV_AUTH` is set at
# build time. This script greps the built `dist/` for markers that
# exist ONLY inside that dev-login code path and fails if any are
# found, so a future change that accidentally makes dev login
# reachable from an unconditionally-bundled module is caught here
# rather than by inspection.
#
# Run after `vite build` (wired into the `build` npm script).
set -euo pipefail

dist_dir="${1:-dist}"

if [ ! -d "$dist_dir" ]; then
  echo "check-no-dev-auth: '$dist_dir' does not exist; run the build first." >&2
  exit 1
fi

# Markers unique to the dev-login mechanism: the dev-token endpoint
# path and dialog-only text. Deliberately excludes generic strings
# that legitimately appear elsewhere too (e.g. the "auth
# unconfigured" blocking screen in App.vue also names
# ADRIANO_DEV_SHARED_SECRET as an operator instruction -- that is
# not the dev-login UI/mechanism itself).
markers=(
  "/auth/dev/token"
  "DevLoginDialog"
  "mints a token for any identity"
)

found=0
for marker in "${markers[@]}"; do
  if grep -rl -- "$marker" "$dist_dir" > /dev/null 2>&1; then
    echo "check-no-dev-auth: found dev-login marker '$marker' in '$dist_dir':" >&2
    grep -rl -- "$marker" "$dist_dir" >&2
    found=1
  fi
done

if [ "$found" -ne 0 ]; then
  echo "check-no-dev-auth: dev-login code leaked into the production" \
    "build. See src/config.ts/App.vue's dev-auth gate and" \
    "src/auth/devAuth.ts's isolation docstring." >&2
  exit 1
fi

echo "check-no-dev-auth: no dev-login markers found in '$dist_dir'. OK."
