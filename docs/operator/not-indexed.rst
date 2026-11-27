Files that are not indexed
==========================

A file in a source is indexed only when it has a valid ``uuid`` that
no other file holds.
Every other ADR file is listed on the **Not indexed** page, with the
reason, instead of being dropped without a word.
Every signed-in user can open it, so authors can find out why their
file is missing.
This page explains what the list contains and when entries go away;
how users read it is described in :doc:`/user/not-indexed`.

What is listed
--------------

Each entry names the file's registration, project, path and ref and
shows when it was first and last seen, a link to the file at its
source and the content that was rejected.
The reasons are:

No usable header
   The file has no header, or the header is not valid YAML
   (``missing_frontmatter``, ``bad_yaml``).

Missing or invalid UUID
   The header has no ``uuid``, or it is not a UUID
   (``missing_uuid``, ``bad_uuid``).

Duplicate UUID
   Another file already holds the UUID (``duplicate_uuid``).
   The entry links to the record that holds it.

File could not be read
   The source failed to deliver the file (``fetch_failed``).
   The next poll tries again.

Rejected push
   A CI push was refused for a reason about the document: it has no
   usable header or UUID, its UUID differs from ``adr_uuid``, it names
   the published ref, it is too large or not valid UTF-8, or its UUID
   is held by another project or registration
   (``published_ref_not_allowed``, ``content_too_large``,
   ``bad_encoding``, ``uuid_mismatch``, ``duplicate_uuid``).
   Refusals that say nothing about the document, such as a bad token
   or a project outside the ``scope``, are not listed.

An entry made by a poll shows the origin "Polled", one made by a push
"Pushed".

When an entry goes away
-----------------------

Entries clear on their own; there is no button to dismiss one.
An entry is removed when:

* a poll indexes a document at that location, for example after the
  author fixed the file;
* a complete listing no longer contains the file;
* its registration is removed from the catalog file;
* for a pushed entry, a later successful push or a poll indexes a
  document at the same file location, whatever the ref.

A poll never clears a pushed entry just because the file is not in
its listing, since a pushed branch is not part of the published
listing.

An entry that does not clear means the cause still exists.
Open the entry, read the reason and fix the file, or remove it.

Counting entries
----------------

The Sources page shows the number of entries per registration in the
**Not indexed** column; the number links to the list filtered by that
registration.
Entries from a rejected push are counted with their registration.

Read it from a script
---------------------

``GET /api/v1/not-indexed`` returns one page of entries, newest first,
and takes the optional filters ``source_id``, ``project``, ``reason``
(a code from the list above) and ``origin`` (``poll`` or ``push``).
``GET /api/v1/not-indexed/entry`` returns one entry with its rejected
content; pass ``source_id``, ``project``, ``path`` and ``ref`` as
query parameters, since the values contain slashes.
Both need the ``read`` permission.

.. note::

   The list shows the rejected content to every signed-in user.
   A file that cannot be indexed is therefore as visible as an indexed
   one.
