#!/bin/sh
# Render config.js from config.template.js using only the documented
# runtime-config environment variables (module-runtime-config-spa
# "the container entrypoint renders the global from env vars").
#
# Runs automatically: the base nginx image's docker-entrypoint.sh
# executes every executable *.sh file under /docker-entrypoint.d/
# before starting nginx.
set -eu

export API_BASE_URL="${API_BASE_URL:-}"
export OIDC_AUTHORITY="${OIDC_AUTHORITY:-}"
export OIDC_CLIENT_ID="${OIDC_CLIENT_ID:-}"
export OIDC_REDIRECT_URI="${OIDC_REDIRECT_URI:-}"
export OIDC_POST_LOGOUT_REDIRECT_URI="${OIDC_POST_LOGOUT_REDIRECT_URI:-}"
export OIDC_SCOPE="${OIDC_SCOPE:-}"

# Explicit variable list: substitute only the documented placeholders,
# never every `$NAME`-shaped token that might appear in the template.
envsubst \
  '${API_BASE_URL} ${OIDC_AUTHORITY} ${OIDC_CLIENT_ID} ${OIDC_REDIRECT_URI} ${OIDC_POST_LOGOUT_REDIRECT_URI} ${OIDC_SCOPE}' \
  < /usr/share/nginx/html/config.template.js \
  > /usr/share/nginx/html/config.js

echo "40-render-app-config.sh: rendered /usr/share/nginx/html/config.js"
