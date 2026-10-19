# syntax=docker/dockerfile:1
#
# Multi-stage build for the adriano frontend: a Vue 3 / Vuetify SPA
# built once (module-runtime-config-spa "build once, configure at
# runtime") and served by an unprivileged nginx.
#
# VITE_DEV_AUTH is NEVER set in this build. `npm run build` runs
# `vite build` and then `scripts/check-no-dev-auth.sh`, which fails
# the build if any dev-login code leaked into `dist/` regardless of
# how any build arg is set -- so there is deliberately no ARG for it
# here.

FROM node:24-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:alpine AS runtime

COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY --chown=nginx:nginx config.template.js \
    /usr/share/nginx/html/config.template.js
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --chmod=755 docker-entrypoint.d/40-render-app-config.sh \
    /docker-entrypoint.d/40-render-app-config.sh

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 CMD ["curl", "-fsS", "http://127.0.0.1:8080/config.js"]
