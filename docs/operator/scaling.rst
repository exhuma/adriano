Running several replicas
========================

The backend keeps no state of its own between requests;
everything lives in the database.
You can run as many backend replicas as you need behind a load
balancer, and the web container can be replicated the same way.

What is safe
------------

Concurrent polls
   Two polls of the same registration, from any replica, the CLI or
   "Poll now", never corrupt it: the second one waits until the first
   has written its result.
   Polls of different registrations run independently.
Concurrent decisions
   If two reviewers decide the same revision at the same moment,
   the first decision is recorded and the second reviewer gets an
   "already decided" answer (HTTP 409); nothing is overwritten.
Sign-in
   Sessions live in the browser, so no sticky sessions are needed.

What you must take care of
--------------------------

- Run the schema update **once per deployment, before any replica of
  the new version starts** (:doc:`upgrades`).
  In Kubernetes, use a ``Job`` or an init step that runs once,
  not an init container in every backend pod.
- Every replica reads the catalog file at start-up.
  Give all replicas the same file and the same secrets, and restart
  all of them after a change; otherwise replicas disagree about
  sources and permissions.
- Each replica runs :envvar:`ADRIANO_WORKERS` worker processes,
  and each worker keeps its own database connections.
  Keep replicas times workers within your database's connection
  limit.
- Schedule polls once (one cron entry or one ``CronJob``),
  not once per replica.
- "Poll now" runs inside the replica that received the request.
  Restarting that replica during a poll stops the poll;
  the registration keeps its previous content, and the next poll
  catches up.
