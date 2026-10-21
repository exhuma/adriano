Searching the catalog
=====================

Use search to find a decision, narrow a long list, or list everything
that still needs a review.
Searching only reads what the catalog has already collected, so it
is fast and never contacts a team's repository.

.. figure:: /_static/screenshots/search-landing.png
   :alt: The catalog search page listing decision records with their
      source, project and status chips below a row of filter
      controls.

   The search page, with the filter controls above the results.

Find a decision
---------------

#. Open **Catalog** in the top bar.
#. Type words from the title or text into **Search decision
   records**.
   Results update a moment after you stop typing.
#. Select a result to open it.

When you search for words, the results are sorted by how well they
match.
Without words, they are sorted alphabetically by title.

Each result shows its title, source and project, and a few chips:

* **Candidate** with the branch name, if it is a proposal rather than
  the published version.
* The approval state, such as "Pending approval" or "Accepted".
  For a correction it reads "Reported" or "Verified" instead.
* **Erratum**, if the result is a correction.
* The number of problems found in the file, such as "1 error".

.. figure:: /_static/screenshots/search-query-candidate.png
   :alt: Search results for "Redis" showing one record marked
      Candidate with its branch name and a Pending approval chip.

   A search for "Redis" finds a candidate from a branch.

Filtering
---------

The row of controls under the search field narrows the list.
All filters combine: a result must match every one.

Source and Project
   Show only decisions from one source or one project.

All, Published, Candidate
   Show everything, only the published decisions, or only the
   proposals.

Show
   Choose **Decisions** (the default), **Errata** or **Both**.
   Errata are corrections to decisions; see :doc:`errata`.

Sort by
   **Title A–Z**, **Recently changed**, or **Relevance** (offered
   only once you have typed something).

Needs approval
   Show only what is not accepted yet: pending, rejected or changed
   since acceptance.
   Reviewers use this to find their work; see :doc:`reviewing`.

A line above the list tells you how many records match, for example
"Showing 1–20 of 57 records".
Long lists are split into pages.

Every active filter appears as a chip above the list.
Select the chip's close button to remove that filter, or select
**Clear filters** to remove all of them.

.. figure:: /_static/screenshots/search-filters-active.png
   :alt: Search results narrowed by three filters, each shown as a
      closable chip above the list, next to a Clear filters button.

   Three active filters, shown as chips.

Show errata
-----------

Errata are hidden by default so that the list stays focused on
decisions.
Set **Show** to **Errata** to list only corrections, or to **Both**
to see them mixed in.

.. figure:: /_static/screenshots/search-show-errata.png
   :alt: Search results listing three erratum records, each with an
      Erratum chip and a Reported or Verified status.

   **Show** set to **Errata**.

Share a search
--------------

Your query, filters and sort order are part of the page address.
Copy the address from your browser to share the exact same view with
a colleague, or bookmark it.
The browser's back and forward buttons also step through your
searches.

Nothing found?
--------------

If the list is empty, the page says "No matches for your filters".
Remove a filter or shorten your words.
If the catalog says "No indexed records yet", nothing has been
collected yet; ask an operator to check the
:doc:`sources-page`.

On a phone
----------

The same controls are available on a small screen.
The filters stack above the results and the top bar collapses into a
menu button.

.. figure:: /_static/screenshots/mobile-search.png
   :alt: The search page on a phone, with the filters stacked above a
      single column of results.
   :width: 240px

   Search on a phone.

Next: :doc:`reading-a-record`.
