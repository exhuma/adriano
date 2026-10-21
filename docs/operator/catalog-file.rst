The catalog file
================

The catalog file (``catalog.yaml``) says three things:

- which **sources** Adriano indexes (``sources``),
- who may **approve** decisions (``approval_policy``),
- what each identity-provider **role** may do (``rbac``).

It is read once, when the backend starts.
After editing it, validate it, then restart the backend
(``docker compose restart backend``).
Scheduled polls read it again on every run.

A complete example
------------------

.. code-block:: yaml

   sources:
     - id: gitlab-platform
       type: gitlab
       base_url: https://gitlab.example.com
       token_env: ADRIANO_GITLAB_TOKEN_PLATFORM
       scope:
         groups: [platform]
         include_subgroups: true
       path: doc/decisions
       published_ref: "@project-default"
       intake: [poll, push]
       push_tokens_env: [ADRIANO_PUSH_TOKEN_PLATFORM]

     - id: central
       type: filesystem
       root: /srv/adr
       scope:
         projects: [architecture]
       path: doc/decisions
       published_ref: main
       intake: [poll]

   approval_policy:
     id: global
     version: 1
     required: true
     reviewers:
       users: ["https://idp.example.com/realms/adr|3f1c0d2e-subject"]
       roles: [adr-reviewer]
     allow_self_approval: false

   rbac:
     roles:
       adr-admin: [read, operate]
       adr-reader: [read]
       adr-reviewer: [read]

Validating the file
-------------------

Run the check after every change, before restarting:

.. code-block:: sh

   docker compose run --rm --no-deps backend adriano check-config

It needs no database.
It prints every source with its state, the approval policy, the
configured roles, the sign-in mode and every problem found,
then exits with 0 when there is no error (warnings are allowed)
and 1 otherwise.
See :doc:`cli` for the full output.

A problem in the file never stops Adriano.
Instead:

- An invalid source entry disables only that source.
  The reason is shown by ``check-config``, in the start-up log and
  on the Sources page.
- A missing or invalid ``approval_policy`` blocks every approval
  decision until it is fixed (``/healthz`` reports
  ``policy: missing`` or ``policy: invalid``).
- A missing or invalid ``rbac`` section grants nobody any
  permission (``/healthz`` reports ``rbac: empty``).
- Unknown top-level sections are ignored, with a warning.

Sources
-------

``sources`` is a list.
Each entry is one *registration*: one place Adriano indexes records
from.
The common fields are below; the type-specific fields are in
:doc:`sources`.

``id`` : required
   Stable name of the registration: letters, digits, ``.``, ``_`` and
   ``-``, up to 64 characters, starting with a letter or digit.
   It appears in the UI, in CI pushes and in the approval history.
   **Do not rename it**: a renamed registration is a new source,
   and the records and approvals of the old name stay attached to
   the old one.
``type`` : required
   ``gitlab`` or ``filesystem``.
``path`` : optional, default ``doc/decisions``
   Folder that holds the decision records inside each project.
   It may not leave the project (no ``..``).
   Files below it (also in sub-folders) are indexed when their name
   looks like ``2024-01-10-use-postgresql.md``.
``published_ref`` : required
   Which version counts as *published*.
   For GitLab, a branch name, or ``"@project-default"`` for each
   project's own default branch.
   For a folder, a free label such as ``main``.
   CI may not push candidates for this ref.
``scope`` : optional for folders, required for GitLab
   Which projects belong to this registration (see :doc:`sources`).
``intake`` : optional, default ``[poll]``
   ``poll`` indexes the source on a schedule;
   ``push`` lets CI push draft records (candidates) for it.
   Use ``[poll, push]`` for both.
``push_tokens_env`` : optional
   Names of the environment variables that hold this registration's
   CI push tokens (:doc:`ci-push`).
   Several names allow rotating tokens one at a time.

Order matters
~~~~~~~~~~~~~

If two registrations contain the same file
(same project and path), the one listed **first** owns it;
the later one skips it and reports an ``ownership_conflict`` warning
in its poll result.

Removing a registration
~~~~~~~~~~~~~~~~~~~~~~~

A registration you delete from the file is disabled at the next
start or poll, never deleted.
Its records stay browsable, and its approval history is kept.

Approval policy
---------------

There is one policy for the whole catalog.
How reviewers use it is described in the :doc:`user guide
</user/index>`.

``id`` : required
   Name of the policy.
   It is recorded with every decision.
``version`` : required, a whole number of at least 1
   Recorded with every decision.
   Raise it when you change who may approve, so the history shows
   which rules applied.
``required`` : optional, default ``true``
   ``false`` means no record needs approval at all; every record
   shows as not requiring review.
``reviewers.users`` : optional
   Individual reviewers, each written as ``issuer|subject``:
   the issuer of their tokens and their user ID at the identity
   provider, separated by ``|``.
   An email address or display name does not work.
``reviewers.roles`` : optional
   Role names (from the roles claim) whose holders may review.
``allow_self_approval`` : optional, default ``false``
   With ``false``, a reviewer cannot decide a record whose recorded
   author has the reviewer's email address.
   Only CI pushes that send an ``author`` record one
   (:doc:`ci-push`); polled records have no author,
   so this check cannot stop self-approval for them.

With ``required: true`` and no reviewers at all, nobody can decide;
``check-config`` warns about it.

.. note::

   Being a reviewer does not grant ``read``.
   Give reviewers a role with ``read`` in ``rbac`` too, or they
   cannot open the catalog.

Role permissions (``rbac``)
---------------------------

``rbac.roles`` maps each role name, exactly as it appears in the
roles claim of the access token
(:envvar:`ADRIANO_OIDC_ROLES_CLAIM`), to a list of permissions:

``read``
   Browse and search the catalog.
``operate``
   Start polls ("Poll now" on the Sources page) and see the
   problem details and recovery hints on that page.

Permissions do not include each other: give operators both
``read`` and ``operate``.
A role not listed grants nothing.
Reviewing is not a permission here; it comes from
``approval_policy.reviewers`` only.
