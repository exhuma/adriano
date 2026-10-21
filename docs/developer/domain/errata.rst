Errata
======

An erratum is a short, RFC-style report about a problem in an existing
decision.
It is a record of its own, with its own UUID, digest and approval
history, and it never changes the decision it corrects
(:doc:`/developer/decisions/0015-errata-as-records`).
The parser is ``app.domain.errata``; reading errata for a decision is
``app.services.errata_view`` and ``app.services.record_relationships``.
How authors write an erratum file is covered in :doc:`/user/index`.

Model
-----

A file is an erratum because its frontmatter has ``erratum-for``,
not because of where it lives
(the recommended location is ``doc/decisions/errata/``).
It goes through the same discovery, poll and push intake, hashing and
storage as a decision; ``record_kind`` is then ``erratum``.

Frontmatter
   ``uuid`` (its own identity), ``erratum-for`` (UUID of the corrected
   decision), ``type`` (``technical`` or ``editorial``), and optionally
   ``section``, ``reported-by`` (free text, never treated as an
   identity), ``date`` and ``title``.
   Without a ``title`` it is titled "Erratum: <section>",
   else "Erratum: <humanised filename slug>".

Body
   Split on ATX H2 headings "Original text", "Corrected text"
   (required) and "Notes",
   matched case-insensitively with an optional trailing colon.
   Headings inside fenced code blocks are content.
   Text before the first heading or under any other H2 is kept as notes
   with a warning; a repeated heading appends to its section with a
   warning.
   Known limits: a setext heading does not start a section,
   and an unclosed code fence swallows every later heading.

Storage
   The link is stored as ``links.corrects``
   (the internal name predates the ``erratum-for`` spelling).
   ``record.erratum`` (JSONB, migration ``0003``) holds the type,
   section, reporter, date and the sanitized HTML of the three
   sections; the raw Markdown stays in the revision snapshot.
   The partial expression index ``ix_record_links_corrects`` serves the
   reverse lookup "errata of this decision".

Rules
-----

The corrected decision is never touched
   Filing, verifying or rejecting an erratum changes neither the
   decision's digest, nor its approval state, nor its history.

Resolution uses the normal link tiers
   ``erratum-for`` resolves like any link: same project first, then
   same registration, then global.
   An erratum belongs to a decision when its link resolves to a row of
   that decision's identity, so it shows on the published row and on
   candidate revisions alike.
   An ambiguous link belongs to no decision.

Errata correct decisions only
   An erratum never lists errata of its own.
   If ``erratum-for`` resolves to another erratum the link is kept but
   flagged ``erratum_target_is_erratum``.

Errata are not decisions in search
   Search defaults to ``record_type=decision``;
   ``erratum`` or ``all`` include them.
   Facet counts cover decisions only.
   An erratum hit carries the title of the decision it corrects.

The old shape is refused
   ``kind: erratum`` or any ``corrects`` key yields
   ``legacy_erratum_format``; there is no alias.

Counting errata on a decision
-----------------------------

The detail page's ``errata_summary`` counts **published** errata by the
approval state of each erratum's own identity and digest:

* ``verified``: ``accepted``, and also ``not_required``,
  because both stand as published without further action
  (the notice therefore reads "verified or not requiring review");
* ``reported``: ``pending`` and ``policy_missing``;
* ``rejected``: ``rejected``;
* ``changed``: ``changed_since_acceptance``.

``total`` is the sum of these four.
Candidate errata are proposals and are counted separately as
``proposed``.
The decision events of all errata of a record are read with one query,
so the detail request does not grow with the number of errata.

Issue codes
-----------

``erratum_without_target`` : error
   ``erratum-for`` is missing or not a valid UUID; the erratum is not
   linked.

``erratum_targets_itself`` : error
   ``erratum-for`` equals the erratum's own ``uuid``.

``bad_erratum_type`` : error
   ``type`` is missing or not ``technical`` or ``editorial``.

``erratum_missing_corrected_text`` : error
   No non-empty "Corrected text" section.

``erratum_unknown_section_heading`` : warning
   Text before the first heading or under an unknown heading;
   kept as notes.

``erratum_duplicate_section`` : warning
   A section heading appears more than once; the parts are joined.

``erratum_relationship_ignored`` : warning
   ``updates``, ``obsoletes`` or ``deprecates`` on an erratum;
   they are dropped.

``erratum_target_is_erratum`` : warning
   Computed when read: ``erratum-for`` resolves to another erratum.

None of these block a decision on the erratum;
like any record, only a missing UUID or bad encoding does.
