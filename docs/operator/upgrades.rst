Upgrading
=========

An upgrade may change the database schema.
A schema change runs once, before the new backend starts, and cannot
be undone by starting the old images again.
The only way back is restoring a backup.

Upgrade steps
-------------

#. Read what changed in the release you upgrade to.
#. **Back up the database** (:doc:`backup-restore`).
#. Build or pull the images of the new release
   (:ref:`operator/install:Obtaining the images`).
#. Validate your catalog file against the new release:

   .. code-block:: sh

      docker compose run --rm --no-deps backend adriano check-config

#. Pause the poll schedule.
#. Apply the update:

   .. code-block:: sh

      docker compose up -d

   Compose runs the schema update (``migrate``) first and starts the
   new backend only if it succeeded.
   While it runs, the old backend keeps serving; plan a short
   maintenance window anyway, since the old backend may not work
   against the new schema.
#. Verify as after a fresh install
   (:ref:`operator/install:Verification`), then resume the poll
   schedule.

Running the schema update yourself
----------------------------------

Outside Compose, or to run it separately:

.. code-block:: sh

   docker compose run --rm migrate

On other platforms, run the new backend image once with the command
``alembic upgrade head`` and the database owner's credentials.
Rules:

- Run it **exactly once per deployment**, before any new backend
  container starts.
- It is safe to run again: when the schema is current, it does
  nothing.
- Never start new backend replicas before it has finished
  successfully.

If the update fails
-------------------

``backend`` does not start, and ``docker compose ps -a`` shows
``migrate`` exited with a non-zero code.

#. Read the reason: ``docker compose logs migrate``.
#. Fix it (usually database connectivity, credentials or missing
   privileges of the owner) and run ``docker compose up -d`` again.
#. If the release itself cannot be applied, restore the backup and
   go back to the previous images.
