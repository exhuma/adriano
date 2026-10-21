0016: A filesystem source type beside GitLab
============================================

:Status: Accepted (authorised deviation from the specification)
:Date: 2026-10-19

Context
-------

The specification names GitLab as the only required source type.
Demonstrating the product end to end would then need a real GitLab
instance.

Decision
--------

Add a ``filesystem`` source type: each immediate subdirectory of a
configured root is a project, the change token is ``mtime_ns:size``.
It implements the same adapter protocol as ``gitlab``.

Consequences
------------

* ``task demo`` and the samples work without external systems.
* No other layer treats it differently.
* Filesystem records have no author, so the self-approval check cannot
  block them. (GitLab-polled records have no author either; see
  :doc:`/developer/domain/approval`.)
