Reading a decision
==================

Open a decision from the search results to read it and to see how far
you can trust it.
This page explains what is on the page and what the banners mean.

.. figure:: /_static/screenshots/record-pending-reviewer.png
   :alt: A decision record page with the document on the left, and on
      the right a sidebar showing Pending approval status with Accept
      and Reject buttons.

   A decision page: banners on top, the document on the left, and the
   "About this decision" sidebar on the right.

Page layout
-----------

Header
   The title, the source and project, and where the text came from.
   If errata exist, a link such as "1 erratum · View errata" jumps to
   them.
   A "2 warnings" or "1 error" chip appears here when the file has
   problems; see `Problems in the file`_.

Banners
   Notices about the decision as a whole; see `Banners`_.

The document
   The decision itself, as its authors wrote it.

Errata
   Below the document, any corrections reported for it.
   See :doc:`errata`.

"About this decision" sidebar
   Everything that is not the document itself.
   On a phone the sidebar moves below the document.

Banners
-------

"This decision is obsolete, see ..."
   A newer decision replaced this one.
   Follow the link and read that one instead.

"This decision was updated, see ..."
   A newer decision changed part of this one.
   Read the newer decision alongside this one.

"This is an erratum for ..."
   Shown on a correction's own page; see :doc:`errata`.

"The last poll of ... failed ..."
   The catalog could not refresh this decision from its source, so
   you are reading the last copy it successfully collected.
   It may be out of date.

"Last indexed ... (older than the freshness threshold)"
   The catalog has not refreshed this decision for a while.
   It is probably still right, but it has not been confirmed
   recently.

"A different revision of this ADR was accepted"
   An earlier version was accepted, but the text changed since.
   The text you are reading needs its own decision.

"The published revision of this ADR differs from this candidate"
   You are reading a proposal that is not the same as what is
   currently published.
   Follow the link to compare.

"Competing candidates"
   Several proposals exist for the same decision.
   A decision on one never affects another.

.. figure:: /_static/screenshots/record-obsolete-with-errata.png
   :alt: A decision page with a banner saying it is obsolete and a
      link to its replacement, and an Errata section below the text.

   An obsolete decision, with a link to its replacement.

.. figure:: /_static/screenshots/record-stale-banner.png
   :alt: A record page with a warning banner saying the last poll of
      the source failed and the content may be out of date.

   A warning that the catalog could not refresh this decision.

The sidebar
-----------

Approval
   The status chip, for example "Pending approval" or "Accepted —
   published", with a one-sentence explanation.
   If you are a reviewer, the **Accept** and **Reject** buttons are
   here too; see :doc:`reviewing`.
   Everyone else sees why they cannot decide, for example "Only
   reviewers can approve this."

Metadata
   The decision's identifier (UUID), its decision date, and its kind
   (decision or erratum).
   Select the copy button to copy the identifier.
   If the author did not write a date, the page says "Not recorded".
   When it can guess a date from the file name, it labels the date
   as inferred.

Provenance
   Where the decision came from: source, project, file path and ref
   (shown as **Path & ref**), a link to the **Source location** where
   available, and when the catalog last refreshed it (**Freshness**).

Related decisions
   Links to decisions this one updates or obsoletes.
   Select a title to open it.
   A link reading "Ambiguous" means more than one decision matches
   and the catalog did not guess.

Referenced by
   Links in the other direction: later decisions that update or
   obsolete this one.

Other revisions
   Other versions of the same decision, such as a candidate from
   another ref next to the published version.

Legacy sign-off (unverified)
   See `Legacy sign-off`_.

Published, candidate and which is current
-----------------------------------------

The title line shows "Candidate" with its ref if you are
looking at a proposal.
A published decision is the version your team has published.
If both exist, **Other revisions** links between them.

After a candidate is published, the published version appears with the
same text.
If a reviewer already accepted that exact text, the published
version is accepted too, and keeps the same decision history.

.. figure:: /_static/screenshots/review-accepted-published.png
   :alt: A record page with the status Accepted - published and a
      card listing another revision that was accepted as a
      candidate.

   A published decision whose candidate was accepted earlier.

Problems in the file
--------------------

The catalog shows every decision it finds, even if the file has
problems, and a problem in one file never affects another.
Problems are listed in a **Validation issues** card next to a chip
in the title:

Warning
   Something to tidy, but the decision still works.
   For example, the file uses an old field name or lists a link to
   a decision that cannot be found.

Error
   Something that stops the catalog from working with the file
   properly.
   For example, the header is not valid or the identifier is
   missing.

A decision with an error shows the status **Blocked**, with the text
"This content can't be decided until its problems are fixed."
Ask the author to fix the file; the page updates the next time the
catalog reads it.
:doc:`writing-adrs` lists the fields that are expected.

.. figure:: /_static/screenshots/record-blocked-invalid-yaml.png
   :alt: A record page with a red error chip, a validation issue
      about invalid YAML and a Blocked approval status.

   A blocked decision, with the problem explained.

Legacy sign-off
---------------

Some older decisions carry a "signed off by" line written by hand in
the file.
The catalog shows it as **Legacy sign-off (unverified)**.
It is only text: nobody checked who wrote it, so it never counts as
an approval.
Only a recorded acceptance by a reviewer does.

.. figure:: /_static/screenshots/record-legacy-warnings.png
   :alt: A decision record with a Validation issues card listing two
      warnings about legacy fields above the decision text.

   Two warnings about older fields on a decision.

Next: :doc:`errata` or :doc:`reviewing`.
