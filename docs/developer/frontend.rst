Frontend
========

The frontend is a Vue 3 single-page application built with Vite,
TypeScript and Vuetify 4.
It lives in ``frontend/`` and talks to the backend only through the
HTTP API (:doc:`http-api`).
Business rules stay in the backend; the frontend does presentation and
user-experience checks only.

Structure
---------

Everything below is under ``frontend/src``.

``views/``
   One component per route: ``SearchView`` (the landing page, with
   search terms and filters kept in the query string so a result list
   is shareable by URL), ``RecordView``, ``SourcesView``,
   ``AuthCallbackView`` and ``NotFoundView``.
   Routes are declared in ``router/index.ts`` and load lazily.

``components/``
   Reusable pieces.
   The ``record/`` and ``search/`` subfolders hold the parts of the
   record page and the search page.

``composables/``
   Stateful logic shared by components, for example ``useAuth``,
   ``useSearchQuery``, ``useRecordDetailView`` and
   ``useThemePreference``.

``api/``
   The HTTP client and one module per resource.

``types/``
   TypeScript types.
   ``openapi.ts`` is generated; see below.

``utils/``
   Pure helpers.
   ``utils/labels/`` maps backend enum values to an icon and text
   pair, so a status is never conveyed by colour alone.

``auth/``
   OIDC set-up, the dev sign-in and the re-authentication guard.

``plugins/vuetify.ts``
   The Vuetify instance: theme, global defaults and aliases.

``config.ts``
   The typed runtime configuration.

API client and generated types
------------------------------

Every request goes through the client in ``api/index.ts``, which
attaches the bearer token, shapes errors into ``ApiError`` and routes
401 responses to the re-authentication guard.
Components never call ``fetch`` directly.

``src/types/openapi.ts`` is generated from the backend's OpenAPI
document and must not be edited by hand.
Regenerate it after changing a backend route or schema:

.. code-block:: sh

   cd frontend
   npm run gen:types

``scripts/gen-types.mjs`` fetches ``/openapi.json`` from the running
dev backend (``OPENAPI_URL``, default http://localhost:8100) and
refreshes the committed snapshot ``frontend/openapi.json``.
When the backend is not running it falls back to that snapshot.
Commit the snapshot and the generated types together.
The hand-written modules in ``types/`` re-export or narrow the
generated types.

State management
----------------

There is no Pinia.
Shared state lives in module-level singletons exposed by composables
(``useAuth``, ``useThemePreference`` and others) as read-only refs.
Anything stored in the browser is a convenience only: every access to
``localStorage`` is wrapped in ``try``/``catch`` so that a blocked
store never breaks the application.

Authentication flow
-------------------

``main.ts`` calls ``initAuth()`` from ``composables/useAuth.ts``
before anything can issue a request.
It wires the API client's token provider and its 401 handler.

OIDC (``auth/oidc.ts``)
   Authorization Code with PKCE through ``oidc-client-ts``.
   It is configured only when runtime configuration supplies an
   authority and a client id.
   The signed-in user, including its tokens, is kept in memory, never
   in ``localStorage``, so a page reload signs the user out.
   Only the short-lived PKCE state survives the redirect round trip,
   in ``sessionStorage``.
   ``/auth/callback`` is the registered redirect target.

Dev sign-in (``auth/devAuth.ts``, ``auth/devPresets.ts``)
   Reached only through the dynamically imported ``DevLoginDialog``,
   which is gated by a build-time literal (``import.meta.env.DEV``
   and ``VITE_DEV_AUTH``).
   In a production build the bundler removes the dialog and
   everything only it imports.
   ``npm run build`` verifies this with
   ``scripts/check-no-dev-auth.sh``, which fails the build when
   dev-login markers appear in ``dist/``.

Re-authentication guard (``auth/reauthGuard.ts``)
   A 401 normally means the session expired and one redirect to the
   identity provider fixes it.
   A token can also be valid yet rejected by the backend, for example
   because of its audience, and redirecting again would loop.
   The guard allows one redirect per failure episode, counted in
   ``sessionStorage``, and then shows a blocking error instead.

Runtime configuration
---------------------

One built image must run in any environment, so deployment settings
are not baked into the bundle.
``config.ts`` is the only module that reads ``window.__APP_CONFIG__``
or ``import.meta.env``; components import named values from it.

In the container, the nginx entrypoint
``docker-entrypoint.d/40-render-app-config.sh`` renders
``config.template.js`` into ``config.js`` by substituting environment
variables, and ``index.html`` loads it before the bundle.
The variables are ``API_BASE_URL``, ``OIDC_AUTHORITY``,
``OIDC_CLIENT_ID``, ``OIDC_REDIRECT_URI``,
``OIDC_POST_LOGOUT_REDIRECT_URI`` and ``OIDC_SCOPE``.
The entrypoint validates ``OIDC_AUTHORITY`` strictly, because it is
also placed into the content security policy, and refuses to start on
an invalid value.
Operators find the consequences in :doc:`/operator/index`.

In development, ``public/config.js`` is an empty stub, and
``config.ts`` falls back to ``VITE_*`` variables such as
``VITE_API_BASE_URL``.
The Vite dev server proxies ``/api``, ``/healthz`` and ``/auth/dev``
to the backend (``VITE_DEV_PROXY_TARGET``, default
http://localhost:8100).

The dev-login switch ``VITE_DEV_AUTH`` is deliberately not part of the
runtime configuration.
It is a build-time literal, so no container setting can turn dev login
on in a deployed image.
Never add it to ``config.template.js``.

UI route and Vuetify first
--------------------------

The frontend uses Vuetify rather than a hand-built component set with
plain CSS.
The catalog needs data-table-like lists and filters, and Material
Design is an acceptable look for an internal governance tool, so
ready-made components outweigh hand-written ARIA primitives.

Vuetify first
^^^^^^^^^^^^^

Before writing custom CSS, use Vuetify's own mechanisms, in this
order, and stop at the first one that can express the change:

1. **Theme** in ``plugins/vuetify.ts``: colours, theme variables such
   as ``border-opacity`` and the emphasis opacities, and the theme
   selection.
2. **Global defaults** in ``createVuetify({ defaults })``:
   per-component prop defaults, component aliases and nested
   defaults.
3. **Scoped defaults** with ``<v-defaults-provider>`` for one region.
4. **Component props and utility classes** for spacing, flex,
   typography, position and visibility (``d-sr-only``), plus layout
   components such as ``v-container``.
5. **Vuetify SASS settings** through the ``styles.configFile`` option
   of ``vite-plugin-vuetify``, only for values Vuetify exposes as SASS
   variables and steps 1 to 4 cannot reach.
6. **Custom scoped CSS** as a last resort.
   It may use theme variables only, such as
   ``rgb(var(--v-theme-primary))``, and each rule needs a comment
   saying why steps 1 to 5 could not express it.

Related rules:

- No hex, ``rgb`` or named colours outside ``plugins/vuetify.ts``.
- No global stylesheet or design-token file outside the Vuetify theme.
- Set a prop at the call site only when that instance has to differ
  from the global default.

``tests/style-blocks.test.ts`` enforces the colour and comment rules
for every ``<style>`` block.

Theming and dark mode
^^^^^^^^^^^^^^^^^^^^^

``plugins/vuetify.ts`` defines a ``light`` and a ``dark`` theme and
sets ``defaultTheme: "system"``, which follows the operating system.
``useThemePreference`` lets a user choose light, dark or system through
the user menu, applies the choice with ``useTheme().change()`` and
remembers it in ``localStorage``.

Status colours double as text colours on a tonal tint, so they are
darkened in the light theme until they reach a contrast ratio of at
least 4.5:1 on both the surface and the 12% tint.
``tests/plugins/vuetify.test.ts`` checks every pair in both themes;
when you change a theme colour, run it.

Global defaults give the app one look: flat bordered cards, small
tonal chips, text fields with ``hideDetails: "auto"`` and a single
page width through ``VContainer.maxWidth``.

Accessibility conventions
^^^^^^^^^^^^^^^^^^^^^^^^^

- Never convey meaning by colour alone.
  Status chips carry an icon and text from ``utils/labels/``; when the
  text is hidden at small widths, an ``aria-label`` and screen-reader
  text keep it.
- A "Skip to main content" link is the first focusable element.
- Dynamic updates such as copy confirmations, diff summaries and the
  health indicator are announced through ``role="status"`` with
  ``aria-live="polite"``.
- Hide text visually with ``d-sr-only``, not with custom CSS.
- Tables get a caption, and card titles are real headings.
- Use Vuetify's focus styles; only add a theme-variable rule where a
  control lacks a visible focus ring.
- Write error and recovery messages for people: say what happened and
  what to do next.
