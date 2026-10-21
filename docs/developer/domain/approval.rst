Approval
========

Approval is a formal accept or reject decision by an eligible reviewer
on one exact content revision.
Decisions are stored in the database, never in the Markdown files
(:doc:`/developer/decisions/0007-approval-outside-markdown`).
The rules live in :mod:`app.domain.approval` (pure),
:mod:`app.services.decisions` (the write path) and
:mod:`app.services.approval_view` (the detail page's approval block).

The policy
----------

There is one global policy, the ``approval_policy`` section of
``catalog.yaml``:

.. code-block:: yaml

   approval_policy:
     id: global
     version: 1
     required: true
     reviewers:
       users: ["https://idp.example.com|subject-123"]  # issuer|subject
       roles: [adr-reviewer]
     allow_self_approval: false

``id`` and ``version``
   Recorded with every decision, so history shows which policy applied.

``required``
   ``false`` means approval is not needed anywhere
   (state ``not_required``).

``reviewers``
   A caller is eligible when their ``issuer|subject`` is listed in
   ``users`` or one of their token roles is listed in ``roles``
   (:py:obj:`app.domain.approval.is_eligible`).
   Eligibility is independent of RBAC:
   ``read`` never implies review,
   and being a reviewer grants no ``read`` or ``operate``.
   (A reviewer still needs ``read`` to reach the decision endpoint.)

``allow_self_approval``
   When ``false``, a reviewer may not decide a record they authored;
   see `Self-approval`_.

A missing or invalid policy does not stop startup.
It gives every record the state ``policy_missing``,
is reported by ``/healthz`` and the UI,
and every decision is refused until it is fixed.
It is never treated as "approval not required".

States
------

The state belongs to a record's **current digest**,
evaluated from all decision events of its logical identity
``(source_id, project, record_key)``.
:py:obj:`app.domain.approval.evaluate` applies these rules in order:

.. mermaid::

   flowchart TD
     start(["record with current digest"])
     p{"policy configured<br/>and valid?"}
     r{"policy required?"}
     e{"decision for this<br/>identity and digest?"}
     a{"that decision<br/>is accepted?"}
     o{"any acceptance of<br/>another digest?"}
     pm["policy_missing<br/>needs approval"]
     nr["not_required<br/>no approval needed"]
     ac["accepted<br/>no approval needed"]
     rj["rejected<br/>needs approval"]
     cs["changed_since_acceptance<br/>needs approval"]
     pe["pending<br/>needs approval"]

     start --> p
     p -- "no" --> pm
     p -- "yes" --> r
     r -- "no" --> nr
     r -- "yes" --> e
     e -- "yes" --> a
     a -- "yes" --> ac
     a -- "no" --> rj
     e -- "no" --> o
     o -- "yes" --> cs
     o -- "no" --> pe

The "Needs approval" filter returns every state except ``accepted`` and
``not_required``.
:py:obj:`app.storage.postgres.search.approval_join` mirrors the same rules in
SQL so the filter paginates correctly;
``tests/storage/test_approval_parity.py`` keeps the two in step.

``approvable`` does not change the state.
A record without a valid UUID, or with bad encoding, shows ``pending``
(or ``changed_since_acceptance``) with a reason and cannot be decided;
the UI labels it "Blocked".

Candidates, published rows and promotion
----------------------------------------

Approval always evaluates a stored revision, never a live source read.
For a published row that is the latest successfully polled content,
so the UI shows its freshness next to the state
(see `Freshness`_).

Acceptance before publication
   A reviewer may accept a candidate while it is still on a feature
   branch; the UI shows "Accepted — candidate" with its ref.
   An accepted candidate is authoritative for implementation.

Promotion
   Decisions are keyed by identity and digest, not by row.
   When a poll later finds the same digest on the published ref,
   the published row is ``accepted`` ("Accepted — published") with the
   full history.
   Nothing is copied or re-decided.

Divergence
   If the published digest differs from an accepted candidate's,
   both rows stay.
   The published row shows ``changed_since_acceptance``
   and a divergence notice linking to the accepted revision;
   a candidate whose published sibling differs links to it too.
   Acceptance never moves across digests.

Competing candidates
   Several candidates of one identity on different refs are separate
   rows with independent states.
   The detail page lists the others with their states;
   deciding one never affects another digest.

Across projects
   The same UUID in another project or registration is another
   identity (flagged ``duplicate_uuid``); promotion never crosses it.

Recording a decision
--------------------

``POST /api/v1/records/{id}/decisions`` with
``{action, comment?, expected_digest?}``
(``comment`` up to 2,000 characters).
:py:obj:`app.services.decisions.decision_blocker` checks, in order,
and the same function gives the detail page its ``can_decide`` flag
and reason:

1. the record exists, else 404 ``record_not_found``;
2. the policy is configured, else 409 ``policy_missing``;
3. the policy requires approval, else 409 ``approval_not_required``;
4. the caller is eligible, else 403 ``not_eligible``;
5. the record is approvable, else 409 ``not_approvable``;
6. it is not a self-approval, else 403 ``self_approval``;
7. ``expected_digest``, when sent, equals the current digest,
   else 409 ``digest_changed`` (a reviewer never decides content they
   did not see);
8. no decision exists yet for this identity and digest,
   else 409 ``already_decided``.

The event is appended with ``ON CONFLICT DO NOTHING`` against
``uq_decision_event_identity_digest``, so two concurrent decisions on
one digest produce exactly one event and one 409.
The server sets the event id and ``created_at``;
the event also stores the actor's ``issuer``, ``subject``,
display name and email, the policy id and version,
and provenance (record id, kind, ref, path and source URL at decision
time).

One decision per digest means a rejection is final for that content.
Changed content has a new digest and a fresh ``pending`` or
``changed_since_acceptance`` state.

Self-approval
-------------

With ``allow_self_approval: false``, a decision is refused when the
record's ``author`` equals the reviewer's verified email
(case-insensitive) or the reviewer's ``issuer|subject``.

``author`` is known only for candidates whose CI push supplied it.
Neither source adapter provides one:
the filesystem has no such concept,
and the GitLab adapter does not fetch per-file commit authors
(it would cost one slow request per changed file).
The check therefore cannot block self-approval of polled records.
This is a documented limit of the policy, not a security guarantee.

Diffs
-----

``GET /api/v1/records/{id}/diff`` (:mod:`app.services.diff`) is a unified
diff between two stored revisions, labelled with both digests.
The default base is the identity's last decided revision other than the
current one (latest acceptance, else latest rejection,
:py:obj:`app.domain.approval.last_decided`),
else the row's ``previous_digest``,
else there is no prior revision.
Only digests related to the record can be requested;
any other digest answers 404 ``unknown_revision``,
so the endpoint cannot read arbitrary snapshots.

Freshness
---------

A registration is stale when it has never polled successfully,
its last poll failed or was partial,
or its last successful poll is older than
``ADRIANO_STALE_AFTER_MINUTES`` (default 120)
(:py:obj:`app.services.sources_view.is_stale`).
The UI then shows a banner next to a published record's state and never
claims that the indexed revision is the current published content.
The approval state itself is still evaluated normally against what was
last indexed.

Errata
------

An erratum is approved exactly like a decision, on its own identity and
digest; the corrected decision is never touched.
The UI words the states as a report:

* ``pending`` and ``policy_missing``: Reported
* ``accepted``: Verified
* ``rejected``: Rejected
* ``changed_since_acceptance``: Changed since verification
* ``not_required``: Published (no review required)

See :doc:`errata` for how errata are counted on a decision.
