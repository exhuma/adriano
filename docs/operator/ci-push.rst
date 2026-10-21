Pushing candidates from CI
==========================

Polling only sees the published branch.
To show a decision record while it is still under review,
for example on a merge-request branch, a CI job can *push* it to
Adriano as a **candidate**.
Reviewers can then accept or reject it before it is merged.
When the identical file later appears on the published branch,
the next poll recognises it and the earlier decision carries over.

Pushes never change published records and never touch the approval
history.

Setting up a registration for pushes
------------------------------------

#. Allow pushes and name the token variables in the catalog file:

   .. code-block:: yaml

      - id: gitlab-platform
        # ... other fields ...
        intake: [poll, push]
        push_tokens_env: [ADRIANO_PUSH_TOKEN_PLATFORM]

#. Generate a token and add it to the container environment
   (:envvar:`ADRIANO_BACKEND_ENV_FILE`, ``.env`` by default):

   .. code-block:: sh

      echo "ADRIANO_PUSH_TOKEN_PLATFORM=$(openssl rand -hex 32)" >> .env

#. Recreate the container: ``docker compose up -d adriano``
   (Kubernetes: update the Secret, then
   ``kubectl rollout restart deployment/adriano``).
#. Check with ``adriano check-config``: there must be no warning
   ``push token env var ... is not set``.
#. Store the same token as a masked, protected CI variable in the
   projects (or group) that push, for example
   ``ADRIANO_PUSH_TOKEN``.

A push token is valid for its own registration only and gives no
read access to the catalog.

Rotating a token
~~~~~~~~~~~~~~~~

List two variable names, so old and new token are valid at the same
time:

#. Add ``ADRIANO_PUSH_TOKEN_PLATFORM_NEXT`` to ``push_tokens_env``
   and to the environment, then recreate the container.
#. Switch the CI variable to the new token.
#. Remove the old name and its variable, then recreate the container
   again.

The push request
----------------

``PUT /api/v1/candidates`` with the push token as bearer token and a
JSON body:

``source_id`` : required
   The registration ``id``.
``project`` : required
   The project path, as Adriano knows it (for GitLab, the full
   project path).
   It must be inside the registration's ``scope``.
``adr_uuid`` : required
   The ``uuid`` from the record's frontmatter.
   It must match the content.
``ref`` : required
   The branch the content comes from.
   It may not be the registration's ``published_ref``.
``content`` : required
   The complete Markdown file, at most 1 MiB.
``path`` : optional
   The file's path inside the project, ending in ``.md``.
   Send it, so the candidate shows the right location and the title
   or date can be taken from the file name.
``delivery_id`` : optional
   A unique ID of this CI run, such as the pipeline ID.
   A retried job with the same ID gets the earlier answer instead of
   a second submission.
``author`` : optional
   The author's email address.
   Send it if the approval policy forbids self-approval: it is the
   only way Adriano can tell that a reviewer is the author.

``PUT`` creates the candidate or replaces the previous content for
the same project, record and branch.
``POST`` with the same body only creates, and answers
``409 candidate_exists`` if the candidate is already there.

Example script
~~~~~~~~~~~~~~

The source tree ships ``samples/push-candidate.sh``, which builds the
JSON body correctly (including escaping) and sends it:

.. code-block:: sh

   export ADRIANO_API_BASE_URL=https://adriano.example.com
   export ADRIANO_PUSH_TOKEN_CENTRAL=<push token>
   samples/push-candidate.sh \
     doc/decisions/2026-01-05-use-redis-for-caching.md \
     platform feature/redis-cache central "$CI_PIPELINE_ID" \
     doc/decisions/2026-01-05-use-redis-for-caching.md

Its arguments are the file, project, branch, and optionally the
registration ID, delivery ID and path.
It reads the token from ``ADRIANO_PUSH_TOKEN_<REGISTRATION ID>``
(upper case); a registration ID containing ``-`` or ``.`` therefore
needs your own script.

GitLab CI job
~~~~~~~~~~~~~

.. code-block:: yaml

   push-adr-candidate:
     stage: review
     rules:
       - if: '$CI_COMMIT_BRANCH != $CI_DEFAULT_BRANCH'
         changes: [doc/decisions/**/*.md]
     script:
       - |
         python3 - <<'PY'
         import json, os, pathlib, urllib.request

         path = pathlib.Path("doc/decisions/2026-01-05-use-redis-for-caching.md")
         body = json.dumps({
             "source_id": "gitlab-platform",
             "project": os.environ["CI_PROJECT_PATH"],
             "adr_uuid": "b87a5fc5-a48f-49cb-a029-ac1f7c56c717",
             "ref": os.environ["CI_COMMIT_REF_NAME"],
             "content": path.read_text(encoding="utf-8"),
             "path": str(path),
             "delivery_id": os.environ["CI_PIPELINE_ID"],
             "author": os.environ["GITLAB_USER_EMAIL"],
         }).encode("utf-8")
         req = urllib.request.Request(
             "https://adriano.example.com/api/v1/candidates",
             data=body,
             method="PUT",
             headers={
                 "Authorization": f"Bearer {os.environ['ADRIANO_PUSH_TOKEN']}",
                 "Content-Type": "application/json",
             },
         )
         print(urllib.request.urlopen(req, timeout=10).read().decode())
         PY

Pushing an erratum
~~~~~~~~~~~~~~~~~~

An erratum (a correction to a published decision) is pushed the same
way.
Use the erratum file's own ``uuid`` as ``adr_uuid``, not the uuid of
the decision it corrects,
and send its real ``path`` (for example under ``errata/``),
so the candidate sits where the erratum will be once published.

What the answer means
---------------------

``201``
   A new candidate was created.
``200``
   The candidate already existed and was replaced or was unchanged;
   with ``"deduplicated": true``, the ``delivery_id`` was seen before
   and nothing was submitted again.

A successful answer looks like this:

.. code-block:: json

   {"record_id": "0b6c2f4e-...", "digest": "sha256-v1:a0b7e2...",
    "created": true, "updated": false, "deduplicated": false,
    "issues": [], "catalog_path": "/records/0b6c2f4e-..."}

``catalog_path`` is the record's page in the web UI.
``issues`` lists problems in the file that do not block the push,
such as a broken link; reviewers see them too.

Errors carry a ``code`` and a ``hint``:

``401 not_authenticated``
   No token was sent.
``401 invalid_push_token``
   The token is not a push token of this registration, or the
   registration is unknown, disabled or has no token set.
``403 push_disabled``
   The registration does not have ``push`` in ``intake``.
``403 project_out_of_scope``
   The project is not in the registration's ``scope``.
``409 candidate_exists``
   ``POST`` only: the candidate already exists; use ``PUT``.
``413 payload_too_large``, ``413 content_too_large``
   The request or the file is too large (file limit 1 MiB).
``422 invalid_request``
   The body is not valid JSON, misses a field or has an unknown one.
``422 published_ref_not_allowed``
   ``ref`` is the published branch; candidates come from other
   branches.
``422 invalid_document``
   The file has no usable frontmatter or uuid; the answer lists the
   problems.
``422 uuid_mismatch``
   ``adr_uuid`` differs from the uuid in the file.
``422 bad_encoding``
   The content is not valid text.

.. note::

   With ``published_ref: "@project-default"``, Adriano does not know
   each project's default branch when a push arrives,
   so a push from the default branch is accepted as a candidate.
   Limit the CI job to other branches, as in the example above.
