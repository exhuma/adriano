Connecting sources
==================

A *source registration* tells Adriano where decision records live.
There are two types: ``gitlab`` (projects on a GitLab instance) and
``filesystem`` (a folder tree mounted into the container).
The fields every registration shares are in :doc:`catalog-file`;
this page covers what is specific to each type.

In both types, Adriano indexes the Markdown files below the
registration's ``path`` whose names look like
``2024-01-10-use-postgresql.md``.
Adriano only reads from sources; it never writes to them.

GitLab
------

.. code-block:: yaml

   - id: gitlab-platform
     type: gitlab
     base_url: https://gitlab.example.com
     token_env: ADRIANO_GITLAB_TOKEN_PLATFORM
     scope:
       groups: [platform]
       include_subgroups: true
       projects: [shared/architecture]
     path: doc/decisions
     published_ref: "@project-default"
     intake: [poll, push]
     push_tokens_env: [ADRIANO_PUSH_TOKEN_PLATFORM]

``base_url`` : required
   Address of the GitLab instance.
   Only ``https://`` is accepted, without user name, password, query
   or fragment.
   Use the final address: Adriano does not follow redirects.
``token_env`` : required
   Name of the environment variable that holds the access token
   (see :ref:`catalog-secrets`).
   If the variable is not set, the registration is disabled and the
   Sources page says which variable is missing.
``scope`` : required
   Which projects belong to the registration.
   Name at least one group or project; Adriano never indexes
   everything the token can see.

   ``groups``
      Group paths.
      Their projects are included, except archived projects and
      projects only shared with the group.
   ``include_subgroups``
      ``true`` also includes the projects of all sub-groups.
      Default ``false``.
   ``projects``
      Full project paths (``group/sub/project``), included
      individually.

   Upper and lower case do not matter.
``published_ref`` : required
   The branch whose content counts as published:
   a branch name, or ``"@project-default"`` for each project's own
   default branch.

Access token
~~~~~~~~~~~~

Create a personal, group or project access token with:

- the scope ``read_api`` (nothing else is needed; never grant a
  write scope),
- at least the Reporter role on every project in scope, so it can
  read repository files.

A group access token on the scoped group is usually the simplest
choice.
Mind its expiry date: when the token expires or is revoked, polls of
this registration fail (HTTP 401 or 403 from GitLab) and its records
are marked as possibly out of date until you replace the token and
recreate the container (``docker compose up -d adriano``).

What Adriano does with the projects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- A project that is archived, leaves a scoped group, or has no
  default branch any more loses its published records at the next
  poll.
- A project whose published branch is missing keeps its records.
- If a listed group or project cannot be found, or requests keep
  failing, nothing is removed;
  the poll ends as ``partial`` or ``failed``.
  Remove a project you deleted in GitLab from ``scope.projects``
  if you want its records gone.
- Temporary GitLab errors and rate limits are retried a few times
  with increasing waits before a request counts as failed.

TLS
~~~

Adriano always verifies the GitLab server's certificate;
there is no setting to turn that off.
If your GitLab (or identity provider) uses a certificate from an
internal certificate authority, mount a PEM bundle that contains it
into the container and point :envvar:`SSL_CERT_FILE` at it.

Filesystem
----------

.. code-block:: yaml

   - id: central
     type: filesystem
     root: /srv/adr
     scope:
       projects: [architecture, payments]
     path: doc/decisions
     published_ref: main
     intake: [poll]

``root`` : required
   Folder that holds the projects.
   Each folder directly below it is one project.
   A relative path is resolved against the folder that contains the
   catalog file (``/app`` in the bundled stack); prefer an absolute
   path.
``scope.projects`` : optional
   Index only these project folders.
   Without it, every folder below ``root`` is a project.
``published_ref`` : required
   A free label for the published version, such as ``main``.

Mount the folder read-only into the container, for example in a
``docker-compose.override.yml`` (on Kubernetes, add a volume to the
Deployment and to the poll ``CronJob``):

.. code-block:: yaml

   services:
     adriano:
       volumes:
         - /srv/adr:/srv/adr:ro

The container runs as user ID 10001;
the files must be readable by that user.

What to expect:

- If ``root`` is missing or unreadable (for example a volume that
  failed to mount), the poll fails and **nothing is removed**.
- A project folder that disappears from a readable ``root`` loses
  its published records at the next poll.
  So does a project whose ADR folder disappears.
- A file is only read again when its size or modification time
  changes.
- Folder records have no author, so the self-approval check of the
  approval policy cannot apply to them.
