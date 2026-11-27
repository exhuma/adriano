0024: Documents that cannot be indexed go to a visible list
===========================================================

:Status: Accepted (supersedes :doc:`0013-fallback-identity`)
:Date: 2026-11-27

Context
-------

Without a location-based key, a file without a valid UUID has no
identity and cannot be a record
(:doc:`0023-uuid-is-the-only-identity`).
Dropping it silently would hide content and leave an author with no
explanation for a file that never shows up.

Decision
--------

A document that cannot be indexed is not a record.
Intake writes it to the *not-indexed list*, keyed by its location
(registration, project, path and ref), with:

* the reasons: a missing or invalid UUID, unparseable frontmatter,
  a duplicate of a UUID that another file holds, a file that could not
  be read or fetched, or a rejected push;
* the rejected content, when it could be read and stored;
* the link to the file at its source, and when it was first and last
  seen.

Every signed-in user can read the list, in the web UI and through
``GET /api/v1/not-indexed``.
The Sources page shows the number of entries per registration.

Entries clear only automatically:

* when a poll indexes a document at that location;
* when a complete listing no longer contains the location;
* for a push entry, when a successful push or a poll indexes a
  document at the same file location, whatever the ref;
* when its registration is removed from the configuration, whatever
  the origin of the entry.

A poll never clears a push entry for not listing it, because a pushed
branch is not in the listing.
There is no way to dismiss an entry by hand.

Consequences
------------

* A file that is not in the catalog always has a reason somewhere a
  reader can find it.
* Nobody has to clean the list up, and nobody can hide a problem by
  dismissing it.
  A problem stays until the file is fixed or removed.
* The list shows rejected content to every signed-in user, so
  confidential content in a file that cannot be indexed is as visible
  as content in the catalog.
* Fixing the file is the only remedy; there is no tool to assign an
  identity to a file, which keeps the authored UUID the only source of
  identity.
* Pushes refused for a reason that says nothing about the document
  (authentication, scope, a malformed request, ``candidate_exists``)
  are not listed.
