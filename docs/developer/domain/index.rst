Domain model
============

These pages describe what Adriano stores and the rules it applies,
as implemented in :mod:`app.domain` (pure logic) and :mod:`app.storage`
(persistence).
They are written for developers changing that logic.
How authors write ADR and erratum files is covered for authors in
:doc:`/user/index`.

.. mermaid::

   flowchart LR
     file["ADR or erratum file<br/>(bytes from a source or CI)"]
     parsed["ParsedRecord<br/>metadata, links, issues"]
     digest["Digest<br/>sha256-v1"]
     row["record row<br/>published or candidate"]
     rev["revision<br/>canonical snapshot"]
     event["decision_event<br/>accepted or rejected"]
     state["Approval state<br/>of the current digest"]

     file -- "parse_record()" --> parsed
     file -- "content_digest()" --> digest
     parsed -- "upsert" --> row
     digest -- "names" --> rev
     row -- "current digest" --> rev
     event -- "identity + digest" --> state
     row -- "identity + current digest" --> state

.. toctree::
   :maxdepth: 2

   records
   hashing
   approval
   errata
   schema
