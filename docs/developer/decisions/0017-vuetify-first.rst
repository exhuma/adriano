0017: Vuetify, and Vuetify first
================================

:Status: Accepted
:Date: 2026-10-19, extended 2026-10-20

Context
-------

The catalog's screens need list, filter and table-like components,
and Material Design is acceptable for an internal governance tool.
A desktop UI review later found contrast, alignment and prominence
defects, many caused by hand-written CSS fighting the component
library.

Decision
--------

Use Vuetify (``stack-fastapi-vuetify``) rather than headless components
with plain CSS.
Express every visual change with Vuetify's own mechanisms, stopping at
the first that works:

1. theme colours and variables (``plugins/vuetify.ts``);
2. global ``defaults`` and aliases in ``createVuetify``;
3. ``<v-defaults-provider>`` for one region;
4. component props and utility classes;
5. Vuetify SASS settings.

Custom scoped CSS is the last resort, may use only theme variables,
and each rule carries a comment saying why steps 1 to 5 could not
express it.
Further rules from the same review:
one page width for every route,
status chips only when they differ from the default,
strong colour only for issues and rejection,
the light/dark/system theme following the OS by default,
and the MD3 type scale with self-hosted Roboto.

Consequences
------------

* Frontend guard tests fail on retired MD2 typography classes,
  literal colours in style blocks, unjustified style rules,
  and theme text pairs below 4.5:1 contrast.
* The rule is repeated in the repository's ``CLAUDE.md``.
