0013: Keep records without a valid UUID, never invent one
=========================================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

Legacy files may lack a UUID or carry a malformed one.
Dropping them would hide content; generating a UUID could be mistaken
for a maintainer-authored identity.

Decision
--------

Store such a record under the fallback key
``src:<source_id>/<project>/<path>``,
disable its UUID-based relationships,
report the issue, and refuse decisions on it until the UUID is fixed.

Consequences
------------

* Every file under the ADR path that matches the filename pattern is
  browseable.
* Moving such a file changes its identity, which is why it cannot
  carry approval evidence.
* Identity-conflict remediation tooling is deferred.
