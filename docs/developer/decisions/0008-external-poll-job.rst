0008: Schedule polling outside the web workers
==============================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

Timers inside web workers multiply with replicas and workers and are
hard to observe.
Operators still need a manual refresh.

Decision
--------

Scheduled polling runs as ``adriano poll`` from cron or a Kubernetes
CronJob.
Operators with the ``operate`` permission can also trigger a poll with
``POST /api/v1/sources/poll`` or ``/sources/{id}/poll``;
the request is answered with 202 and the same polling service runs in
a background worker thread.

Consequences
------------

* No timers in the backend; replicas stay interchangeable.
* Overlapping polls of one registration serialize on its advisory lock.
* Progress and outcome are visible through ``GET /api/v1/sources``
  and the ``intake_run`` log.
