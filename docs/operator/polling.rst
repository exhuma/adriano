Polling sources
===============

Adriano does not watch sources by itself.
A *poll* reads every registration with ``poll`` in its ``intake``,
picks up new, changed and removed records, and stores the result.
You schedule polls outside Adriano, and operators can start one from
the web UI at any time.

Only files that changed since the last poll are downloaded again,
so frequent polls are cheap.

Scheduling polls
----------------

Run ``adriano poll`` on a schedule, as a one-off command next to the
running container.
Every 15 minutes is a reasonable start; set
:envvar:`ADRIANO_STALE_AFTER_MINUTES` to a few poll intervals.

cron on the Docker host
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   */15 * * * * docker compose -f /opt/adriano/docker-compose.yml exec -T adriano adriano poll >> /var/log/adriano-poll.log 2>&1

``-T`` is needed because cron has no terminal.

Kubernetes ``CronJob``
~~~~~~~~~~~~~~~~~~~~~~

Run the Adriano image with the command ``["adriano", "poll"]``,
with the same environment, secrets and catalog file mount as the
Deployment.
Set ``concurrencyPolicy: Forbid`` so a slow poll is not overlapped
by the next one.
The example in :doc:`deploy/kubernetes` does exactly this.

Polling one registration
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

   docker compose exec adriano adriano poll --source central

Exit codes
~~~~~~~~~~

``0``
   Every registration polled cleanly (``ok``).
``1``
   At least one registration was ``partial``, ``failed`` or
   ``disabled``.
``2``
   Usage error (unknown ``--source``) or the database is
   unreachable.

Alert on anything but ``0``.
The output prints one line per registration with its counts and the
problems found.

"Poll now" in the web UI
------------------------

Users with the ``operate`` permission see "Poll now" next to each
registration and "Poll all" on the Sources page.
The poll runs in the background; the page refreshes itself a few
times afterwards.
For a long poll, reload the page later to see the final result.
A poll requested while another one is writing the same registration
waits for it, so overlapping polls are safe.

.. figure:: /_static/screenshots/sources-operator-ok.png
   :alt: The Sources table with one filesystem source marked OK, with
         Poll now and Poll all buttons.

   The Sources page as seen by an operator.

Poll results
------------

Each registration ends a poll with one of these statuses, shown on
the Sources page:

``ok``
   Everything was listed and read.
``partial``
   Some projects or files could not be listed or read.
   Everything that was read is stored;
   nothing is removed for the parts that could not be listed.
``failed``
   The source could not be listed at all (unreachable, bad
   credentials, missing folder) or the result could not be saved.
   **The previously indexed content is kept unchanged.**
``disabled``
   The registration is switched off because of a configuration
   problem; it is not polled.
``never``
   Not polled yet.

A failure in one registration never affects the others.

What users see after a failed or partial poll
---------------------------------------------

Records stay browsable.
Record pages of the affected registration show a banner saying the
content may be out of date.
The same banner appears when the last successful poll is older than
:envvar:`ADRIANO_STALE_AFTER_MINUTES`.

.. figure:: /_static/screenshots/record-stale-banner.png
   :alt: A record page with a warning banner saying the last poll of
         the source failed and the content may be out of date.

   A record page after its source failed to poll.

Operators see the problem and a suggested fix below the
registration on the Sources page:

.. figure:: /_static/screenshots/sources-poll-failed.png
   :alt: The Sources table with a red Failed status and a message
         below the row explaining the source could not be reached and
         how to fix it.

   A failed poll on the Sources page.

Fix the cause (credentials, network, mount, permissions), then
poll again.
The banner disappears with the next ``ok`` poll.

When records are removed
------------------------

A published record is removed from the catalog only when a poll
listed its project completely and the file was no longer there.
Candidates pushed by CI are never removed by a poll.
Approval history is never removed.
