Kubernetes
==========

This page deploys Adriano to Kubernetes from the example manifests
in ``deploy/kubernetes/`` of the release, using ``kubectl`` and
kustomize.
The manifests are an example to adapt, not a Helm chart.
Their YAML is checked against the Kubernetes API schemas, but they
have not been run against a particular cluster or ingress controller.

Read :doc:`index` first; it explains what you deploy, how to
register the identity provider client and which image tags exist.

Prerequisites
-------------

- A Kubernetes cluster, ``kubectl`` with the built-in kustomize
  (``kubectl apply -k``) and an ingress controller.
- A PostgreSQL database reachable from the cluster, with TLS.
- The things listed in :doc:`index`: an identity provider client and
  a record source.
- A TLS certificate for the host name, as a ``kubernetes.io/tls``
  Secret, or cert-manager to create it.

The manifests contain no namespace.
Create one and pass it to every ``kubectl`` command:

.. code-block:: sh

   kubectl create namespace adriano
   kubectl config set-context --current --namespace adriano

What the manifests create
-------------------------

``secret.yaml``, ``configmap.yaml``
   The configuration (`Configuration`_).
``deployment.yaml``
   The web UI and API: two replicas and an init container that
   applies database migrations.
``service.yaml``, ``ingress.yaml``
   The cluster-internal address and the public TLS entry point.
``cronjob.yaml``
   The poll schedule.
``poddisruptionbudget.yaml``
   Keeps one pod serving during node drains.
``kustomization.yaml``
   Ties them together and pins the image version.

Configuration
-------------

Secret
~~~~~~

``secret.yaml`` holds only placeholders.
Replace them with your values, or better, create the Secret named
``adriano`` from an external secret manager or with Sealed Secrets,
so real values never sit in Git.
It needs these keys:

.. literalinclude:: ../../../deploy/kubernetes/secret.yaml
   :language: yaml

- Keep ``sslmode=require`` (or ``verify-full``) in the database
  address when the database is outside the cluster.
- Add one key for every secret your catalog file names
  (:ref:`catalog-secrets`).
  The Secret is used by the Deployment and by the poll job, so
  source access tokens and push tokens are available to both.

ConfigMap
~~~~~~~~~

``configmap.yaml`` holds two ConfigMaps: the non-secret settings
(``adriano``) and the catalog file (``adriano-catalog``).
Set your identity provider values and replace the catalog with your
own (:doc:`../catalog-file`).

.. literalinclude:: ../../../deploy/kubernetes/configmap.yaml
   :language: yaml

``ADRIANO_FORWARDED_ALLOW_IPS`` is ``*`` because the addresses of
ingress controller pods change.
Adriano then trusts the ``X-Forwarded-*`` headers of every peer, so
let only the ingress controller reach the Service, for example with
a NetworkPolicy.
If your controller has fixed addresses, list them instead.

Changes to a ConfigMap or Secret reach the pods only when they
restart:

.. code-block:: sh

   kubectl rollout restart deployment/adriano

Validate the catalog before you apply it.
Save its content as ``catalog.yaml`` and run:

.. code-block:: sh

   docker run --rm \
     -e ADRIANO_CONFIG_FILE=/c/catalog.yaml \
     -e ADRIANO_DATABASE_URL=postgresql://x:x@localhost/x \
     -v "$PWD:/c:ro" ghcr.io/exhuma/adriano:<version> \
     adriano check-config

Deployment
~~~~~~~~~~

.. literalinclude:: ../../../deploy/kubernetes/deployment.yaml
   :language: yaml

Migrations
   The ``migrate`` init container runs ``adriano migrate`` with the
   same image and settings before each new pod serves, and
   :envvar:`ADRIANO_MIGRATE_ON_START` is ``false`` so the serving
   containers do not repeat it.
   Several pods starting together are safe: only one applies the
   migrations while the others wait.
   Leave the setting at its default ``true`` and drop the init
   container if you prefer migrate-on-start; the lock makes that safe
   as well, but a failing migration then shows up as a crash loop of
   the serving pods instead of a failed init container.
Probes
   Start-up and liveness probes only open the port.
   Readiness calls ``/healthz``, which answers HTTP 503 while the
   database is unreachable.
   A database outage therefore takes the pods out of the Service
   without restarting them; a liveness probe on ``/healthz`` would
   restart every pod during the outage and fix nothing.
   The catalog and sign-in state in the response body never fail a
   probe; alert on those (:doc:`../health-and-logging`).
Resources
   Each worker process (:envvar:`ADRIANO_WORKERS`) needs roughly 100
   to 150 MiB of memory, plus a base.
   The example runs two workers in a pod limited to 512 MiB.
   When you raise the worker count, raise the memory limit with it,
   and keep replicas times workers within your database's connection
   limit.
Security
   The pod runs as the image's non-root user (10001) with a read-only
   root filesystem, no capabilities and the default seccomp profile.
   Only ``/tmp`` is writable.
   The catalog is mounted read-only.

Service and ingress
~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../deploy/kubernetes/service.yaml
   :language: yaml

.. literalinclude:: ../../../deploy/kubernetes/ingress.yaml
   :language: yaml

Set the ingress class, the host and the TLS Secret.
The host must match the redirect URIs you registered at the identity
provider.
Terminate TLS at the ingress; Adriano speaks plain HTTP.
Your controller may need annotations of its own, for example for a
larger request body when CI pushes large records (the limit of a push
is 1 MiB of content).

Poll schedule
~~~~~~~~~~~~~

.. literalinclude:: ../../../deploy/kubernetes/cronjob.yaml
   :language: yaml

The ``CronJob`` runs ``adriano poll`` with the same image,
settings, secrets and catalog as the Deployment.
``concurrencyPolicy: Forbid`` stops a slow poll from being
overlapped, and finished jobs are cleaned up after a day.
A job that exits non-zero (a registration is ``partial`` or
``failed``) is marked failed; alert on failed jobs.
Run it once on demand with:

.. code-block:: sh

   kubectl create job --from=cronjob/adriano-poll adriano-poll-now

Set :envvar:`ADRIANO_STALE_AFTER_MINUTES` to a few poll intervals.
Schedule polls once, not once per replica.

Pod disruption budget and kustomization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../../deploy/kubernetes/poddisruptionbudget.yaml
   :language: yaml

.. literalinclude:: ../../../deploy/kubernetes/kustomization.yaml
   :language: yaml

The ``images`` entry sets the version of the Deployment, its init
container and the poll job in one place.
Replace the placeholder with the release you deploy.
Use a full version, not a channel such as ``stable``: a channel tag
moves, so a pod restart could silently run a newer release whose
database changes cannot be undone.

Bring-up
--------

#. Edit the manifests as described above.
#. Apply everything:

   .. code-block:: sh

      kubectl apply -k deploy/kubernetes

#. Wait for the rollout:

   .. code-block:: sh

      kubectl rollout status deployment/adriano

   If the pods stay in ``Init``, read the migration log:
   ``kubectl logs deployment/adriano -c migrate``.
#. Run the first poll, so the catalog has content:

   .. code-block:: sh

      kubectl create job --from=cronjob/adriano-poll adriano-poll-first
      kubectl logs job/adriano-poll-first

   See :doc:`../polling` for what ``partial`` and ``failed`` mean.
#. If CI should push draft records, hand out the push tokens
   (:doc:`../ci-push`).

Verification
------------

#. Pods are ready and the poll job exists:

   .. code-block:: sh

      kubectl get pods,cronjob

#. The health endpoint answers:

   .. code-block:: sh

      curl -fsS https://adriano.example.com/healthz

   A healthy production deployment answers:

   .. code-block:: json

      {"status": "ok", "database": "ok", "config": "ok",
       "policy": "configured", "registrations": "synced",
       "rbac": "configured", "auth": "oidc", "version": "2026.10.1"}

   ``version`` is the release you pinned.
   ``auth`` must be ``oidc``; a value containing ``dev`` means the
   development sign-in is active and must be fixed
   (:doc:`../authentication`).
#. Open the web UI and sign in with a user that has the ``read``
   permission.
#. Check the catalog file inside a running pod:

   .. code-block:: sh

      kubectl exec deployment/adriano -- adriano check-config

Upgrade and rollback
--------------------

An upgrade may change the database schema, and a schema change cannot
be undone by going back to the old image.
Back up the database first (:doc:`../backup-restore`).
Then:

#. Change ``newTag`` in ``kustomization.yaml`` to the new version.
#. ``kubectl apply -k deploy/kubernetes``.
   The init container applies the migrations, then the rolling update
   replaces the pods one by one.
   Pods of the old release keep serving until the new ones are ready,
   so run a release that changes the schema in a maintenance window:
   the old release may not work against the new schema.
#. Verify as above.

To roll back, set ``newTag`` back and apply again, or run
``kubectl rollout undo deployment/adriano`` (the poll job keeps the
new version until you apply the old tag).
That works only while the release you left did not change the
schema.
Migrations only go forward: if the release did change it, restore the
backup taken before the upgrade (:doc:`../backup-restore`) and then
deploy the previous version.
:doc:`../upgrades` has the details.

Several replicas
----------------

Adriano keeps no state between requests, so you can raise
``replicas`` freely; see :doc:`../scaling` for what to watch.
