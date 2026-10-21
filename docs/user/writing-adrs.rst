Writing decisions and errata
============================

This page is for authors.
It describes the file you write so that Adriano can read it.
A decision is one Markdown file with a short header on top.

How a file reaches the catalog
------------------------------

You do not upload anything.
There are two ways your file gets in:

Published decisions
   Merge the file into your repository's main line.
   The catalog reads its sources regularly and picks the file up on
   the next read.

Proposals (candidates)
   Your team's pipeline can send a file from a branch.
   It then appears as a **Candidate** with the branch name, so
   reviewers can accept it before the branch is merged.

Whichever way it arrives, the catalog never changes your file.
To change a decision, edit the file and let it be collected again.
Reviewers then see "Changed since acceptance" if it was accepted
before.

How sources and pipelines are set up is described in the
:doc:`operator guide </operator/index>`.

Where to put the file
---------------------

Save the file in your repository under ``doc/decisions/``
(subfolders are fine).
The name must start with the date, then a short description:

.. code-block:: text

   doc/decisions/2025-02-20-add-rest-gateway.md

A file whose name does not follow this pattern is ignored.
That is useful for a ``README.md`` that lives next to your
decisions.

The header
----------

The header sits between two lines of three dashes at the very top of
the file.
It is written in YAML.

uuid : required
   A unique identifier for the decision, such as
   ``0b0c2f4e-1a2b-4c3d-8e9f-001122334455``.
   Create it once and never change it; every link to your decision
   uses it.
   Without a valid ``uuid`` the decision is shown but marked
   **Blocked**: it cannot be accepted.

title : optional
   The name shown in the catalog.
   If you leave it out, the first level-one heading of the text is
   used, and otherwise the file name.

decision-date : optional
   The day the decision was made, written ``YYYY-MM-DD``.
   If you leave it out, the catalog shows a warning.
   A date in the file name is shown too, labelled as inferred, but
   it is never used as the decision date.

updates : optional
   A list of identifiers of earlier decisions that this one changes.
   Write it on the **newer** decision.

obsoletes : optional
   A list of identifiers of earlier decisions that this one
   replaces entirely.
   Write it on the **newer** decision.
   The older decision then shows "This decision is obsolete".

Fields that Adriano does not know produce a warning, which usually
points to a typo.

Everything after the header is the decision text.
Write it as ordinary Markdown.
A common outline is *Context*, *Decision* and *Consequences*.

Complete example
----------------

.. code-block:: markdown

   ---
   title: Add a REST gateway in front of gRPC services
   uuid: 1790fef2-54d8-4191-84a1-3b7104c4940c
   decision-date: 2025-02-20
   obsoletes: [70cba06c-46f1-4000-a088-0fe467a12a2c]
   ---
   # Add a REST gateway in front of gRPC services

   ## Context

   External partners occasionally need to call internal services
   that moved to gRPC-only, but cannot adopt a gRPC client.

   ## Decision

   Internal services exposed to partners run a generated REST/JSON
   gateway alongside their gRPC listener.

   ## Consequences

   Services that need external exposure carry a small amount of
   extra generated code.

Older files
-----------

Files written for earlier versions keep working.
The catalog shows a warning, but nothing breaks.

``deprecates``
   An old name for ``obsoletes``.
   It is treated as ``obsoletes``.
   Rename it when you next edit the file.

``signed-off-by``
   An old, hand-written approval line.
   It is shown as **Legacy sign-off (unverified)** and never counts
   as an approval.
   Approval is recorded in the catalog by a reviewer instead.

``kind: decision``
   No longer needed.
   Remove the line.

Writing an erratum
------------------

An erratum is a separate file that points to the decision it
corrects.
It reports a mistake; it does not change the decision.
Save it beside the decisions, for example under
``doc/decisions/errata/``, using the same date-first file name.
The catalog recognises an erratum by its ``erratum-for`` field, not
by the folder.

uuid : required
   The erratum's own identifier, not the decision's.

erratum-for : required
   The identifier of the decision being corrected.

type : required
   ``technical`` if the meaning changes, or ``editorial`` for
   wording only.

section : optional
   Where the problem is, such as ``Consequences``.
   It also forms the title when you give none.

reported-by : optional
   Who found the problem.
   It is shown as text and is not checked.

date : optional
   The day it was reported, as ``YYYY-MM-DD``.

The body has up to three sections, each started by a level-two
heading:

``## Original text``
   The wording as it is now.
   Leave it out when you are adding something new.

``## Corrected text``
   The wording it should have.
   Required.

``## Notes``
   Why the correction is needed.

.. code-block:: markdown

   ---
   uuid: 103eda7f-dafa-4395-a286-db1488b67d49
   erratum-for: 70cba06c-46f1-4000-a088-0fe467a12a2c
   type: technical
   section: Decision
   reported-by: priya.nair@example.com
   date: 2025-05-01
   ---
   ## Original text

   New internal service-to-service APIs are defined with Protocol
   Buffers and served over gRPC.

   ## Corrected text

   New internal service-to-service APIs are defined with Protocol
   Buffers and served over gRPC; all new internal clients, not only
   new servers, must use the generated stubs.

   ## Notes

   This only clarifies the scope of the original record.

Do not put ``updates`` or ``obsoletes`` in an erratum; they are
ignored.
To replace a decision, write a new decision.

Check your file
---------------

Open the decision in the catalog after it has been collected.
The title shows how many warnings and errors the file has, and the
**Validation issues** card explains each one in plain words; see
:doc:`reading-a-record`.
The most common causes are:

* The header is not valid YAML, for example a quote that is not
  closed.
* The ``uuid`` is missing or has a typo.
* A date is not written ``YYYY-MM-DD``.
* A link points to an identifier that does not exist.
* The file is not saved as UTF-8 text.
