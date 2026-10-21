Backup, restore and retention
=============================

Everything Adriano knows that cannot be rebuilt from the sources is
in its PostgreSQL database: the approval history, the content of
every reviewed revision, and the candidates pushed by CI.
Published records can be indexed again by a poll, but decisions
cannot.
Back the database up.

Backup
------

Back up on a schedule that matches how much decision history you can
afford to lose; daily is a reasonable start.
With the bundled ``db`` service:

.. code-block:: sh

   docker compose exec db pg_dump -U adriano -d adriano \
     --format=custom --file=/tmp/adriano.dump
   docker compose cp db:/tmp/adriano.dump ./adriano-$(date +%F).dump

Replace ``adriano`` with :envvar:`ADRIANO_DB_USER` and
:envvar:`ADRIANO_DB_NAME` if you changed them.
For a managed PostgreSQL, use your provider's backups or run the same
``pg_dump`` against it.
Keep backups away from the Docker host, and test a restore now and
then.

The catalog file and ``.env`` are not in the database;
keep them in your configuration management.

Restore
-------

Stop everything that writes to the database first:
the backend and the scheduled poll.
A write during the restore can corrupt it or be lost.

#. Stop the backend and pause the poll schedule:

   .. code-block:: sh

      docker compose stop backend frontend

#. Restore the dump:

   .. code-block:: sh

      docker compose cp ./adriano-2026-10-19.dump db:/tmp/adriano.dump
      docker compose exec db pg_restore -U adriano -d adriano \
        --clean --if-exists /tmp/adriano.dump

#. Bring the schema up to the version the running release expects
   (needed when the backup is older than the release; harmless
   otherwise):

   .. code-block:: sh

      docker compose run --rm migrate

#. Start the services and resume the poll schedule:

   .. code-block:: sh

      docker compose up -d

#. Run a poll, so published records catch up with the sources.

Never restore a backup taken by a *newer* release into an older one.

Retention
---------

Kept forever
   The approval history and the stored content of each revision are
   the audit trail.
   Adriano never deletes them, and you should not either.
May be pruned
   The log of poll and push runs grows with every poll and push and
   holds no approval evidence.
   Adriano does not prune it.
   When it grows too large, delete old finished runs, for example
   everything older than 90 days:

   .. code-block:: sql

      DELETE FROM intake_run
      WHERE finished_at IS NOT NULL
        AND finished_at < now() - interval '90 days';

   Never delete runs that have not finished.
   Deleting a run also forgets its ``delivery_id``, so a CI retry
   older than your retention would be accepted again as a new push.

Database roles and tamper resistance
------------------------------------

The approval history table refuses changes and deletions,
so application bugs and slips cannot rewrite it.
That protection does not stop the table's **owner** or a database
superuser, who can switch it off.

The bundled stack runs the schema update and the application as the
same owning user.
That is fine for evaluation, but not tamper resistant.
For production, use two users:

- the **owner**, used only by the schema update (``migrate``);
- an **application user** for the backend that owns nothing and may
  only add to the approval history.

Create the application user once, as the owner:

.. code-block:: sql

   CREATE ROLE adriano_app LOGIN PASSWORD '<strong password>';
   GRANT CONNECT ON DATABASE adriano TO adriano_app;
   GRANT USAGE ON SCHEMA public TO adriano_app;
   GRANT SELECT, INSERT, UPDATE, DELETE
     ON source_registration, record, intake_run TO adriano_app;
   GRANT SELECT, INSERT ON revision, decision_event TO adriano_app;

Then give the backend the application user and ``migrate`` the owner
(see :ref:`operator/install:Using your own PostgreSQL` for how to set
different addresses per service).
Re-check the grants after every upgrade:
a table added by a new release needs its own grant,
and a missing one shows up as ``permission denied`` errors in the
backend log.

Even then, the database is not cryptographic evidence:
a database administrator can still rewrite history,
and the content fingerprints Adriano stores prove which text a
decision refers to, not who wrote it or that it was ever published.
If you need tamper-evident records, export the approval history
regularly to write-once storage you control.
