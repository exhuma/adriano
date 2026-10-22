Concepts
========

This page explains the words you meet in the catalog.
Read it once; every other page assumes it.

What the catalog holds
----------------------

Adriano collects **decisions** that your teams have written down.
A decision, also called an **ADR** (architecture decision record),
is a short document that says what was decided, why, and what
follows from it.

Teams keep these documents in their own sources, for example a Git
project or a shared folder.
Adriano reads them from there and shows them in one searchable
place.
It never changes the originals.

Each decision belongs to a **source** (where it was read from) and a
**project** (the team or system it is about).
You can filter by both when you search.

Published and candidate
-----------------------

A decision can exist in two forms:

Published
   The version your team has published.
   This is the decision as it stands today.

Candidate
   A proposal that is sent from another ref (for example a branch)
   and is not published yet.
   A candidate shows its ref, so you can see where it comes from.

The same decision can have both a published version and one or more
candidates.
Each one is reviewed on its own.

Approval
--------

A **reviewer** decides whether a decision is accepted.
Approval always applies to the exact text the reviewer saw.
The catalog fingerprints the text and records that fingerprint (the
**digest**) with the decision.
If even one word changes later, the fingerprint changes and the
earlier approval no longer covers the new text.

A decision is always in one of these states:

Pending approval
   Nobody has decided on this text yet.

Accepted
   A reviewer accepted exactly this text.
   You see "Accepted — published" or "Accepted — candidate",
   depending on the form.

Rejected
   A reviewer rejected exactly this text.

Changed since acceptance
   An earlier version was accepted, but the text is different now,
   so the new text needs its own decision.

Blocked
   The file has a problem, such as a missing identifier, so it
   cannot be decided until the author fixes it.

Approval not required
   Your administrators turned approval off for this catalog.

.. mermaid::

   stateDiagram-v2
      state "Pending approval" as Pending
      state "Accepted" as Accepted
      state "Rejected" as Rejected
      state "Changed since acceptance" as Changed
      state "Blocked" as Blocked

      [*] --> Pending: record appears in the catalog
      [*] --> Blocked: record has an error
      Blocked --> Pending: author fixes the file
      Pending --> Accepted: reviewer accepts
      Pending --> Rejected: reviewer rejects
      Accepted --> Changed: text is edited
      Changed --> Accepted: reviewer accepts the new text
      Changed --> Rejected: reviewer rejects the new text
      Rejected --> Pending: text is edited
      Pending --> Pending: text is edited

If edited text goes back to exactly what was accepted, the earlier
acceptance applies again.
A decision rejected, then edited, returns to "Pending approval" if it
was never accepted, and to "Changed since acceptance" if it was.

The state of one version never affects another.
Accepting a candidate does not accept the published version, unless
both contain exactly the same text.
In that case, once the candidate is published, the
published version is accepted automatically.

Where this appears in the catalog
---------------------------------

In search results the chips are shortened: "Accepted",
"Pending approval", "Rejected", "Changed" and "Blocked".
On the decision page you see the full wording.

The filter **Needs approval** shows every decision that is not
accepted: pending, rejected, changed since acceptance, and, if your
administrators have not set up approval yet, all of them.
See :doc:`searching`.

Relationships and lifecycle
---------------------------

Decisions refer to each other.
A newer decision can **update** an earlier one, or **obsolete** it
(replace it entirely).
The catalog works out the consequences for you:

Active
   Nothing replaces or updates this decision.

Updated
   A newer decision updates it.
   The page tells you which one.

Obsoleted
   A newer decision replaces it.
   Read the replacement instead.

See :doc:`reading-a-record`.

Errata
------

An **erratum** (plural: **errata**) is a correction to a decision
that was already approved.
It does not rewrite the decision.
Instead it says "this passage reads X, but should read Y", and the
decision's page lists it.

Errata are reviewed too, with their own words:

Reported
   Someone has reported the correction; nobody has checked it yet.

Verified
   A reviewer confirmed the correction.

Rejected
   A reviewer decided the correction is wrong.

Changed since verification
   The report was edited after it was verified, so the new text
   needs a new check.

.. mermaid::

   stateDiagram-v2
      state "Reported" as Reported
      state "Verified" as Verified
      state "Rejected" as ErrRejected
      state "Changed since verification" as ErrChanged

      [*] --> Reported: erratum appears in the catalog
      Reported --> Verified: reviewer verifies
      Reported --> ErrRejected: reviewer rejects
      Verified --> ErrChanged: erratum text is edited
      ErrChanged --> Verified: reviewer verifies the new text
      ErrChanged --> ErrRejected: reviewer rejects the new text
      ErrRejected --> Reported: erratum text is edited

An erratum can also be **Technical** (it changes the meaning) or
**Editorial** (wording only, such as a typo).

Reviewing or rejecting an erratum never changes the approval of the
decision it corrects.
See :doc:`errata`.

Next steps
----------

* Find decisions: :doc:`searching`.
* Review a decision: :doc:`reviewing`.
