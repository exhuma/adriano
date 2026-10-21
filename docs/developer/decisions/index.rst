Design decisions
================

Adriano is a catalog of architecture decision records,
so its own key decisions are recorded the same way:
one short entry per decision with its context, the decision itself
and its consequences.

Most decisions were confirmed with the product owner on 2026-10-19,
when the first release was scoped.
Later entries carry their own date.
An entry is changed only when the decision changes;
the status line then says which entry supersedes it.

.. toctree::
   :maxdepth: 1

   0001-governance-first-scope
   0002-modular-monolith
   0003-postgresql-storage-and-search
   0004-reads-from-local-index
   0005-separate-poll-and-push
   0006-content-digest-approval
   0007-approval-outside-markdown
   0008-external-poll-job
   0009-single-config-file
   0010-oidc-resource-server
   0011-dev-auth-bypass
   0012-push-tokens
   0013-fallback-identity
   0014-derived-display-status
   0015-errata-as-records
   0016-filesystem-source
   0017-vuetify-first
   0018-read-time-relationship-issues
   0019-approval-state-derived-on-read
   0020-single-image
