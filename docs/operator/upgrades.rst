Upgrading
=========

An upgrade may change the database schema.
Adriano applies the change itself, once, before the new release
serves, and it cannot be undone by starting the old image again.
The only way back is restoring a backup.

Upgrade steps
-------------

#. Read what changed in the release you upgrade to.
#. **Back up the database** (:doc:`backup-restore`).
#. Pick the new full version tag (:doc:`deploy/index`).
#. Validate your catalog file against the new release:

   .. code-block:: sh

      docker compose run --rm --no-deps adriano adriano check-config

#. Pause the poll schedule.
#. Roll out the new version, as described for your platform
   (:doc:`deploy/docker-compose` or :doc:`deploy/kubernetes`).
   While the schema update runs, the old release may keep serving;
   plan a short maintenance window anyway, since the old release may
   not work against the new schema.
#. Verify as after a fresh deployment, then resume the poll schedule.

How the schema update runs
--------------------------

By default every container applies pending schema updates before it
starts serving, under a database lock.
Containers that start at the same time are safe: one applies the
update, the others wait for it and find nothing left to do.
When the schema is already current, the step does nothing.

You can take the step out of the serving containers by setting
:envvar:`ADRIANO_MIGRATE_ON_START` to ``false`` and running the
update yourself with the same image:

.. code-block:: sh

   adriano migrate

Do this on Kubernetes (as an init container, see
:doc:`deploy/kubernetes`) or when the update needs the database
owner's credentials while the application runs with a restricted user
(see :doc:`backup-restore`).
``adriano migrate`` exits with ``0`` on success and ``2`` when the
database is unreachable or an update fails.

If the update fails
-------------------

The new container exits (with migrate-on-start) or the migrate step
fails (init container or ``adriano migrate``), and the new release
does not serve.

#. Read the reason in the container log
   (``docker compose logs adriano``, or
   ``kubectl logs deployment/adriano -c migrate``).
#. Fix it (usually database connectivity, credentials or missing
   privileges of the owner) and start the new release again.
#. If the release itself cannot be applied, restore the backup and
   go back to the previous version.
