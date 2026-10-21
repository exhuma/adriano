0015: Errata are separate records reviewed like decisions
=========================================================

:Status: Accepted (supersedes the ``kind: erratum`` + ``corrects`` shape)
:Date: 2026-10-20

Context
-------

The first release modelled an erratum as a full ADR with
``kind: erratum`` and ``corrects: <uuid>``,
so errata looked like decisions everywhere.
After reviewing the first release, the product owner asked for
RFC-style errata: small reports shown on the original decision.

Decision
--------

An erratum is its own Markdown file with ``uuid``, ``erratum-for``,
``type`` (``technical`` or ``editorial``) and optional ``section``,
``reported-by`` and ``date``, and body sections "Original text",
"Corrected text" (required) and "Notes".
It is ingested, hashed and reviewed exactly like a decision;
its approval states read as Reported, Verified, Rejected and
Changed since verification.
The old shape is refused with ``legacy_erratum_format``, without an
alias.
The record page was redesigned at the same time: status banners on top,
metadata in a sidebar.

Consequences
------------

* Filing or verifying an erratum never changes the corrected
  decision's digest, state or history.
* Errata are hidden from default search (``record_type=decision``)
  and can be shown with a filter.
* Internally the link is still ``Links.corrects``, so relationships
  and storage did not change shape. See
  :doc:`/developer/domain/errata`.
