Content hashing
===============

Approval binds to a digest of the record's content.
This page specifies the digest so it can be reproduced outside
Adriano, and states what it does not prove.
The reference implementation is ``app.domain.hashing``.

Algorithm ``sha256-v1``
-----------------------

The digest string is ``sha256-v1:`` followed by 64 lowercase hex
characters.
Starting from the exact bytes that were fetched or pushed:

1. Decode as strict UTF-8.
   If that fails, see `Bytes that are not valid UTF-8`_.
2. Remove exactly one leading U+FEFF (byte order mark), if present.
3. Replace every CRLF with LF, then every remaining lone CR with LF.
4. Encode the result as UTF-8 and hash it with SHA-256.

The input is the complete file: frontmatter and body together.
Nothing else enters the hash: no path, ref, commit, project or
registration id.
The algorithm label is stored with every digest,
so the canonicalisation can change later under a new label without
making old evidence ambiguous.

The same steps in plain Python, without Adriano:

.. code-block:: python

   import hashlib

   def sha256_v1(raw: bytes) -> str:
       text = raw.decode("utf-8")  # strict
       if text.startswith("﻿"):
           text = text[1:]
       text = text.replace("\r\n", "\n").replace("\r", "\n")
       digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
       return f"sha256-v1:{digest}"

   assert sha256_v1(b"# Hello\n") == sha256_v1(b"\xef\xbb\xbf# Hello\r\n")

Test vectors
------------

All three inputs below canonicalise to the same text and therefore the
same digest:

* ``b"# Hello\n"``
* ``b"\xef\xbb\xbf# Hello\r\n"`` (BOM and CRLF)
* ``b"# Hello\r"`` (lone CR)

.. code-block:: text

   sha256-v1:90f8ec5669cd34183b9b0fdf8b94f5efb4c3672876330f4aa76088c2b4ad17be

One more trailing newline is a content change:
``b"# Hello\n\n"`` gives

.. code-block:: text

   sha256-v1:ad76f539003e68ef6d47c4e4cab9ce2b5c15c0f55f850bc1b9a5254024c846b4

The bundled sample
``samples/adr-root/platform/doc/decisions/2024-01-10-use-postgresql.md``
gives the digest below, both as committed and with CRLF line endings
and a BOM added:

.. code-block:: text

   sha256-v1:ffb54010060b598206bf9317aad5af478c99c429ba8ffc81c3354acbae0b2a70

``tests/domain/test_hashing.py`` pins these properties
(``test_line_endings_and_bom_do_not_change_digest``,
``test_digest_depends_only_on_bytes``).

Why paths and refs are excluded
-------------------------------

Branch names, commit ids, registration ids and paths are provenance,
stored separately on the row.
Keeping them out of the hash has three effects:

* The same bytes pushed from a feature branch and later polled from the
  published ref have the same digest, so the acceptance carries over
  (promotion, see :doc:`approval`).
* Moving a file, or committing the same bytes in another commit,
  never changes its digest.
* Any content edit, even one character, changes the digest,
  so an earlier approval does not silently apply to new content.

Bytes that are not valid UTF-8
------------------------------

Such a file is still stored.
Its digest is SHA-256 over the raw bytes, labelled
``sha256-raw-v1:<hex>``, because no canonicalisation is possible.
The record gets a ``bad_encoding`` error and cannot be decided until it
is re-saved as UTF-8.

The revision snapshot of such a record holds the text decoded with
U+FFFD replacement characters, so unlike ``sha256-v1`` snapshots it
cannot be re-hashed to its own digest.

What the digest does not prove
------------------------------

The digest identifies a content revision, nothing more.

No authorship
   It says nothing about who wrote the content.
   An ``author`` supplied by CI push is stored separately and is not
   bound to the content.

No publication
   It is computed identically for a candidate on a feature branch and
   for the same bytes on the default branch.
   It does not prove review, merge or publication anywhere.

No tamper evidence for the database
   The digest is a property of the document, not of the rows that
   record decisions about it.
   The append-only triggers on ``decision_event`` stop application bugs
   and ordinary mistakes, but a table owner or superuser can disable
   them.
   Acceptance history must not be presented as cryptographically
   immutable.

Deferred: a signed audit export
-------------------------------

If tamper evidence for the approval history becomes a requirement,
the proposed control is a periodic batch job that selects new
``decision_event`` rows, serialises them deterministically, signs the
result with a key held outside the application database
(for example in an HSM or offline),
and publishes it to write-once storage such as an object store with
object lock.
Verifiers could then check that a decision is included in a signed
export without trusting the live database.
This is not implemented.
