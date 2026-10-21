0014: Derive display status from links
======================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

Status fields in frontmatter drift from reality
("superseded" written in one file, forgotten in the other).

Decision
--------

There is no authored status field.
``updates`` points from the newer decision to the earlier one,
``obsoletes`` from the replacing decision to the replaced one,
and an erratum's ``erratum-for`` points to the decision it corrects.
The reverse relations ("updated by", "obsoleted by", errata of a
decision) and the display status are derived when a record is read.

Consequences
------------

* One source of truth per relationship.
* Display status is shown on the detail page only; computing it for
  every search hit would need the relationship index per request.
* No graph view in the first release; direct links only.
