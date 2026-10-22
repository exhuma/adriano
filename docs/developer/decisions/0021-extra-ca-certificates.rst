0021: One TLS context for outbound HTTPS, with additive extra CAs
==================================================================

:Status: Accepted
:Date: 2026-10-22

Context
-------

Instances behind an internal certificate authority could reach their
identity provider and GitLab only by turning verification off with
``ADRIANO_TLS_VERIFY=false`` (issues #9 and #16).
``SSL_CERT_FILE`` was the documented alternative, but it replaces the
standard set of public authorities.
The three outbound clients also did not trust the same set: the HTTP
clients used the certifi bundle, while the signing-key fetch of the
JWT library used the operating system store.
The image runs as a non-root user with a read-only root filesystem.

Decision
--------

Build one ``ssl.SSLContext`` and use it for all outbound HTTPS:
OIDC discovery, the signing-key fetch and network sources such as
GitLab.

* The base is the certifi bundle, or ``SSL_CERT_FILE`` /
  ``SSL_CERT_DIR`` when set.
* ``ADRIANO_EXTRA_CA_CERTS`` adds certificates to that base.
  It takes comma-separated PEM files (bundles allowed) or directories
  (their ``*.pem`` and ``*.crt`` files).
  The added certificates are logged at INFO with their subjects.
* Start-up validates the setting and fails fast.
  Every process checks that each path exists when it reads its
  settings.
  Every process that makes outbound calls (``check-config``, ``poll``,
  ``seed-synthetic``, ``serve`` and each Uvicorn worker) also parses
  the files, and a bad file stops it with exit code 2 and a message
  that names the file.
* ``ADRIANO_TLS_VERIFY=false`` stays as the explicit stop-gap.
  While it is false, the extra certificates are ignored and a warning
  is logged.

Alternatives considered
-----------------------

``SSL_CERT_FILE`` only
   Needs no code.
   Rejected: it replaces the standard set, so the operator must ship
   a bundle that repeats the public authorities, and that copy goes
   stale when the image updates its own bundle.
The operating system store (``truststore``)
   Combined with ``update-ca-certificates``, which is familiar to
   operators.
   Rejected: updating the system store needs root or a writable
   ``/etc/ssl``, which conflicts with the non-root image and its
   read-only root filesystem.
A combined bundle file in ``/tmp``
   Would let ``SSL_CERT_FILE`` carry the result.
   Rejected: an in-process context needs no file, and a file adds a
   write, a race between workers and a stale-copy problem.

Consequences
------------

* An internal certificate authority can be trusted without turning
  verification off, and public endpoints keep working.
* ``ADRIANO_TLS_VERIFY=false`` remains available, as a documented last
  resort for test and staging instances.
* The signing-key fetch now trusts the same set as the other clients.
  Deployments that relied on the operating system store for it must
  list their authorities in ``ADRIANO_EXTRA_CA_CERTS``.
* The ``adriano migrate`` init container needs the mount too, because
  the path check applies to every process.
  A configured path that is not mounted there fails the deployment
  (:doc:`/operator/deploy/kubernetes`).
* A bad certificate file is found at start-up rather than at the
  first request.
