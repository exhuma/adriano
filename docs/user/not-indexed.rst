Files that are not in the catalog
=================================

Sometimes a decision file is in your team's source but you cannot
find it in the catalog.
The **Not indexed** page lists these files and says why each one is
missing.
Everybody who is signed in can open it.

Select **Not indexed** in the top bar (on a phone, in the menu).

Why a file is listed
--------------------

The catalog identifies a decision by the ``uuid`` in its header
(:doc:`writing-adrs`).
A file it cannot give an identity to is not a decision in the catalog,
so it shows up here instead.
Each entry names one of these reasons:

The header is missing or not valid YAML
   The catalog cannot read the header, for example because a quote is
   not closed.

The decision has no UUID, or it is not valid
   The header has no ``uuid``, or the value is not a UUID.

Another file already holds this UUID
   Two files use the same ``uuid``.
   The file the catalog indexed first keeps it, and the later file is
   listed here.
   The entry has a **View the ADR that holds this UUID** button.
   This usually happens when a file is copied without changing its
   ``uuid``.

The file could not be read from its repository
   The source failed to hand the file over.
   The catalog tries again at the next read.

A pushed file was refused
   A pipeline sent the file as a candidate and the catalog refused it
   for a reason that concerns the file: for example its UUID differs
   from the one the pipeline named, it is held by another project, it
   is too large, or it was sent for the published branch.

Read an entry
-------------

The list shows the newest entries first, a page at a time.
Use **Source**, **Project**, **Reason** and **Found by** to narrow it
down.
The filters are kept in the address of the page, so you can share the
link.

Each entry shows:

* the file's path, with its source, project and ref;
* **Polled** if the catalog found it by reading the source, or
  **Pushed** if a pipeline sent it;
* the reasons, in plain words;
* when the file was first and last seen;
* **Open file in repository**, when the source has a link to the
  file.

Select **Show details** to see the content the catalog rejected,
read-only and exactly as it was received.
For a file that could not be read, the page says the content was not
stored.

Anyone who is signed in sees this content, so do not put anything in
a decision file that should not be seen in the catalog.

How an entry goes away
----------------------

Entries clear on their own; there is nothing to dismiss.
Fix the file and let the catalog read it again, as described in
:doc:`writing-adrs`.
An entry disappears when:

* the catalog reads the file and indexes it;
* the file is gone from its source;
* for a pushed file, the pipeline pushes it again successfully, or the
  file is published and read.

If you open an entry that has just cleared, the page says so.
An entry that stays means the problem is still there.
