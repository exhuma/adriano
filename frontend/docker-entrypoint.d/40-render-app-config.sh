#!/bin/sh
# Render config.js from config.template.js using only the documented
# runtime-config environment variables (module-runtime-config-spa
# "the container entrypoint renders the global from env vars"), and
# render the security-headers snippet whose CSP must allow the OIDC
# provider's origin.
#
# Runs automatically: the base nginx image's docker-entrypoint.sh
# executes every executable *.sh file under /docker-entrypoint.d/
# before starting nginx, under `set -e`, so a non-zero exit here stops
# the container instead of serving a half-configured app.
set -eu

log() {
  echo "40-render-app-config.sh: $*"
}

export API_BASE_URL="${API_BASE_URL:-}"
export OIDC_AUTHORITY="${OIDC_AUTHORITY:-}"
export OIDC_CLIENT_ID="${OIDC_CLIENT_ID:-}"
export OIDC_REDIRECT_URI="${OIDC_REDIRECT_URI:-}"
export OIDC_POST_LOGOUT_REDIRECT_URI="${OIDC_POST_LOGOUT_REDIRECT_URI:-}"
export OIDC_SCOPE="${OIDC_SCOPE:-}"

# OIDC_AUTHORITY ends up inside the CSP header and inside config.js,
# so it is validated strictly: scheme http(s), a DNS name or IPv4
# host, an optional port and an optional plain path. Anything else
# (quotes, `;`, spaces, query strings, userinfo, ...) could inject CSP
# directives or break config.js, so it stops the container.
host_part='[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?'
path_part='(/[A-Za-z0-9._~%/-]*)?'
AUTHORITY_PATTERN="^https?://${host_part}(:[0-9]{1,5})?${path_part}\$"

CSP_IDP_SOURCES=""
if [ -n "$OIDC_AUTHORITY" ]; then
  if ! printf '%s' "$OIDC_AUTHORITY" | grep -Eq "$AUTHORITY_PATTERN"; then
    log "ERROR: OIDC_AUTHORITY is not a valid URL" \
      "(expected scheme://host[:port][/path], http or https, no" \
      "query, fragment, credentials, quotes or spaces): refusing" \
      "to start." >&2
    exit 1
  fi
  # Origin = scheme://host[:port]; the path never enters the CSP.
  idp_origin=$(printf '%s' "$OIDC_AUTHORITY" \
    | sed -E 's#^(https?://[^/]+).*$#\1#')
  CSP_IDP_SOURCES=" $idp_origin"
  log "CSP allows the OIDC provider origin $idp_origin"
else
  log "OIDC_AUTHORITY is empty: CSP connect-src/frame-src stay 'self'"
fi
export CSP_IDP_SOURCES

# Explicit variable list: substitute only the documented placeholders,
# never every `$NAME`-shaped token that might appear in the template.
envsubst \
  '${API_BASE_URL} ${OIDC_AUTHORITY} ${OIDC_CLIENT_ID} ${OIDC_REDIRECT_URI} ${OIDC_POST_LOGOUT_REDIRECT_URI} ${OIDC_SCOPE}' \
  < /usr/share/nginx/html/config.template.js \
  > /usr/share/nginx/html/config.js
log "rendered /usr/share/nginx/html/config.js"

envsubst '${CSP_IDP_SOURCES}' \
  < /etc/nginx/adriano-security-headers.conf.template \
  > /etc/nginx/adriano-security-headers.conf
log "rendered /etc/nginx/adriano-security-headers.conf"
