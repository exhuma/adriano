# adriano

<p align="center">
  <img src="https://exhuma.github.io/adriano/_static/identity/adriano.png"
       alt="Adriano: a figure holding a shield" width="480">
</p>

[![docs](https://github.com/exhuma/adriano/actions/workflows/docs.yml/badge.svg)](https://github.com/exhuma/adriano/actions/workflows/docs.yml)

Adriano is a governance catalog for architecture decision records
(ADRs). It indexes ADRs from GitLab and filesystem sources, tells
published decisions from candidates, enforces a reviewer approval
workflow, and tracks errata. The backend is FastAPI on PostgreSQL;
the frontend is Vue 3 and Vuetify.

**Documentation: <https://exhuma.github.io/adriano/>**

- [User guide](https://exhuma.github.io/adriano/user/):
  search, read and review decisions.
- [Operator guide](https://exhuma.github.io/adriano/operator/):
  install, configure and run a deployment.
- [Developer guide](https://exhuma.github.io/adriano/developer/):
  architecture, decisions, API reference and how to contribute.

## Quickstart

Prerequisites: [`uv`](https://docs.astral.sh/uv/),
[Node.js](https://nodejs.org/), [Docker](https://www.docker.com/) and
[`go-task`](https://taskfile.dev/) v3.

Development setup with the sample ADRs:

```sh
cp .env.example .env     # then set, in .env:
                         #   ADRIANO_DEV_AUTH_ENABLED=true
                         #   ADRIANO_DEV_SHARED_SECRET=$(openssl rand -hex 32)
                         #   VITE_DEV_AUTH=true
cp catalog.demo.yaml catalog.yaml
task dev                 # database, migrations, backend and frontend
task poll                # in another terminal: index samples/adr-root
```

Open <http://localhost:5173> and use the "Dev sign-in" chip.

Or run the whole stack in containers:

```sh
task demo                # build, start, poll; serves http://localhost:8180
```

Never enable the dev sign-in in production. See the
[getting started guide](https://exhuma.github.io/adriano/developer/getting-started.html)
for the details, and the
[operator guide](https://exhuma.github.io/adriano/operator/install.html)
for a real deployment.
