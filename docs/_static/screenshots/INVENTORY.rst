Screenshot inventory
====================

Working list for documentation authors.
This file is excluded from the build.
Only the images listed here may be used in the site.

All images show the current UI (after the phase 11 UI fixes).
The demo-walkthrough shots were captured on 2026-10-21 against the
sample catalog with dev sign-in, at 1280 px wide unless noted.
The ``after-*`` review shots are 1920 px wide.
Dev sign-in presets used: Reader (Carol), Reviewer (Bob),
Operator (Dave); the 1920 px shots show "Reviewer Example" and
"Operator Example".
Every screen shows the "DEV LOGIN" chip, because they were
taken with dev sign-in; mention this when a guide is about real
OIDC sign-in.

Nothing is flagged "older UI, recapture later":
every kept image matches the current frontend
(checked against the app bar, record sidebar, decision dialogs and
the Sources problem sub-row in ``frontend/src``).

Sign-in
-------

signin-dev-signin.png
   Shows the signed-out screen "Sign in to browse the decision
   catalog" with the single "Dev sign-in" button.
   Light theme, 1920x1080, no user signed in.
   Suits: user guide (getting started); operator guide (dev
   sign-in note).
   Alt: The adriano sign-in screen with a shield icon, the heading
   "Sign in to browse the decision catalog" and a Dev sign-in button.

Search
------

search-landing.png
   Shows the catalog search page with an empty query, signed in as
   Carol (reader).
   Includes the Source and Project selects, the All/Published/Candidate
   toggle, the Show and Sort by selects and the Needs approval switch.
   Light theme, 1280x800.
   Suits: user guide (searching); first screenshot of the user guide.
   Alt: The catalog search page listing decision records with their
   source, project and status chips below a row of filter controls.

search-filters-active.png
   Shows the search page filtered to source central, project platform
   and published records.
   Closable chips and a "Clear filters" button are visible; the
   count line reads "3 filters active".
   Reader (Carol), light theme, 1280x800.
   Suits: user guide (searching, filtering).
   Alt: Search results narrowed by three filters, each shown as a
   closable chip above the list, next to a Clear filters button.

search-query-candidate.png
   Shows a search for "Redis" with a single result, a candidate from
   branch ``feature/redis-cache`` with "Candidate" and
   "Pending approval" chips.
   Sort by switched to Relevance.
   Reader (Carol), light theme, 1280x800.
   Suits: user guide (searching; published versus candidate).
   Alt: Search results for "Redis" showing one record marked
   Candidate with its branch name and a Pending approval chip.

search-needs-approval.png
   Shows the "Needs approval" switch on, with one filter chip and the
   count line "17 records that need approval".
   Reviewer (Bob), light theme, 1280x800.
   Suits: user guide (reviewing; finding work to review).
   Alt: The search page with the Needs approval switch turned on and
   a matching chip above a list of records awaiting a decision.

search-show-errata.png
   Shows the Show select set to Errata, listing three errata
   with "Erratum", "Reported" and "Verified" chips.
   Reviewer (Bob), light theme, 1280x800.
   Suits: user guide (errata).
   Alt: Search results listing three erratum records, each with an
   Erratum chip and a Reported or Verified status.

Records
-------

record-pending-reviewer.png
   Shows a published decision awaiting review, as a reviewer.
   Sidebar "About this decision" with status chip and Accept/Reject
   buttons, Approval card with digest and empty decision history,
   Metadata, Provenance and Related decisions cards.
   A "last indexed ... older than the freshness threshold" banner is
   visible (an artefact of the capture, but it illustrates the stale
   banner too).
   Reviewer, light theme, 1920x1082.
   Suits: user guide (reading a record; reviewing).
   Alt: A decision record page with the document on the left, and on
   the right a sidebar showing Pending approval status with Accept and
   Reject buttons.

record-legacy-warnings.png
   Shows a record written in an older format.
   Two warnings under "Validation issues" (legacy alias, unverified
   sign-off) and the "2 warnings" chip in the title.
   Reader (Carol), light theme, 1280x900.
   Suits: user guide (understanding warnings and errors).
   Alt: A decision record with a Validation issues card listing two
   warnings about legacy fields above the decision text.

record-blocked-invalid-yaml.png
   Shows a record that cannot be decided because its header is not
   valid.
   "1 error" chip, a validation issue with the parser message, status
   "Blocked" and the text "This content can't be decided until its
   problems are fixed."
   Reader (Carol), light theme, 1280x900.
   Suits: user guide (understanding errors); operator guide
   (diagnosing bad content).
   Alt: A record page with a red error chip, a validation issue about
   invalid YAML and a Blocked approval status.

record-reader-no-decision.png
   Shows a pending candidate as a reader: no Accept or Reject
   buttons, the muted note "Only reviewers can approve this."
   Candidate chip with branch name in the title.
   Reader (Carol), light theme, 1280x900.
   Suits: user guide (roles; why there is no Accept button).
   Alt: A candidate record page where the Approval card shows
   Pending approval and the note Only reviewers can approve this
   instead of buttons.

record-stale-banner.png
   Shows a record page after the source failed to poll.
   Banner: "The last poll of central failed ... this is the last
   successfully indexed revision and may not be the current
   published revision."
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (trusting what you see); operator guide
   (effects of a failed poll).
   Alt: A record page with a warning banner saying the last poll of
   the source failed and the content may be out of date.

record-obsolete-with-errata.png
   Shows a decision that is obsolete: banner "This decision is
   obsolete, see ...", header line "1 erratum - View errata", and the
   start of the Errata section with a Reported, Technical erratum.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (errata; superseded decisions).
   Alt: A decision page with a banner saying it is obsolete and a link
   to its replacement, and an Errata section below the text.

Reviewing
---------

review-accept-dialog.png
   Shows the "Accept ..." confirmation dialog: short digest with copy
   button, "Show full digest", optional comment and Cancel/Accept.
   Reviewer (Bob), light theme, 1280x800, page dimmed behind it.
   Suits: user guide (reviewing: accepting).
   Alt: A dialog titled Accept with the record name, the short content
   digest, a comment box and Cancel and Accept buttons.

review-accepted-candidate.png
   Shows a candidate after acceptance: status "Accepted - candidate",
   the note that this exact content was already decided, a decision
   history table, and the "Decision recorded: accepted." message.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (reviewing; what happens after accepting).
   Alt: A record page whose status reads Accepted - candidate, with a
   decision history table listing the acceptance.

review-accepted-published.png
   Shows the same decision after it was published: status
   "Accepted - published" and an "Other revisions" card linking to the
   accepted candidate.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (candidates and published versions).
   Alt: A record page with the status Accepted - published and a card
   listing another revision that was accepted as a candidate.

review-changed-since-acceptance.png
   Shows a decision whose content changed after acceptance: status
   "Changed since acceptance", Accept/Reject back in the sidebar, and
   the banner "a different revision of this ADR was accepted; the
   published content needs its own decision" at the bottom.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (reviewing changed content).
   Alt: A record page with the status Changed since acceptance and
   Accept and Reject buttons in the sidebar.

review-diff.png
   Shows the Approval card (Changed since acceptance), a one-row
   decision history, and the Diff card with added lines highlighted
   between the last accepted and the current revision.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (reviewing: reading the diff).
   Alt: A Diff card showing the lines added between the last accepted
   revision and the current content.

review-reject-dialog.png
   Shows the "Reject ..." dialog with a filled-in comment and the
   confirmation checkbox "I confirm I want to reject this exact
   content." ticked.
   Reviewer (Bob), light theme, 1280x800.
   Suits: user guide (reviewing: rejecting).
   Alt: A dialog titled Reject with a comment explaining the reason, a
   ticked confirmation checkbox and Cancel and Reject buttons.

review-rejected.png
   Shows a candidate after rejection: status "Rejected", the note that
   this exact content was already decided, and the "Decision
   recorded: rejected." message.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (reviewing; what a rejection means).
   Alt: A candidate record page with a red Rejected status chip and a
   note that this exact content cannot be decided again.

Errata
------

erratum-section-on-decision.png
   Shows the Errata section on a decision, scrolled: the "Original
   text - says" and "Corrected text - should say" blocks and notes
   of one erratum, then the decision's Approval card.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (errata).
   Alt: An erratum entry with labelled blocks for the original text,
   the corrected text and notes.

erratum-page-reviewer.png
   Shows an erratum's own page: banner "This is an erratum for ...",
   original and corrected text, and the sidebar "About this erratum"
   with "Verify erratum" and "Reject erratum" buttons.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (errata; verifying an erratum).
   Alt: An erratum page with the original and corrected text and a
   sidebar offering Verify erratum and Reject erratum buttons.

erratum-page-reader.png
   Shows an editorial erratum as a reader: "Reported" status, the
   note "Only reviewers can approve this.", and no buttons.
   Reader (Carol), light theme, 1920x1132.
   Suits: user guide (errata; reader view).
   Alt: An erratum page for a reader showing the Reported status and
   a note that only reviewers can approve it.

erratum-proposed-on-decision.png
   Shows a decision with a proposed erratum: header line "1 proposed
   erratum - View errata" and a "Proposed errata" group with a
   "Reported - Proposed (branch ...)" chip.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (errata coming from a branch).
   Alt: A decision page with a Proposed errata group listing an
   erratum that comes from a feature branch.

erratum-verify-dialog.png
   Shows the "Verify ... erratum" dialog with the short digest and
   Cancel/Verify buttons, over the erratum page.
   Reviewer (Bob), light theme, 1280x800.
   Suits: user guide (verifying an erratum).
   Alt: A dialog titled Verify with the erratum name, its content
   digest, a comment box and Cancel and Verify buttons.

erratum-verified.png
   Shows an erratum right after verification: status "Verified -
   Proposed (branch ...)", the text "This erratum was verified for
   this exact content." and a decision history row.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (errata).
   Alt: An erratum page with a green Verified status and a decision
   history entry for the verification.

erratum-verified-on-decision.png
   Shows the target decision listing the erratum with a green
   "Verified - Proposed" chip in the Proposed errata group.
   Reviewer (Bob), light theme, 1280x900.
   Suits: user guide (errata).
   Alt: The proposed errata group on a decision, where the erratum now
   carries a green Verified chip.

Sources (operators)
-------------------

sources-operator-ok.png
   Shows the Sources page for a healthy source: table with
   Registration, Type, Intake, Published ref, Status (OK), Last
   attempt, Last success and a "Poll now" button, plus "Poll all".
   Operator (Dave), light theme, 1280x800.
   Suits: operator guide (monitoring and polling sources).
   Alt: The Sources table with one filesystem source marked OK, with
   Poll now and Poll all buttons.

sources-operator-config-problem.png
   Shows two sources: one stale, one "Disabled" with a "Configuration
   problem" row: "The access token's environment variable is not
   set", Details naming the variable, and a recovery hint.
   Operator, light theme, 1920x1080.
   Suits: operator guide (troubleshooting a GitLab source).
   Alt: The Sources table where a GitLab source is Disabled, with a
   Configuration problem message and a hint to set the token variable
   and restart.

sources-poll-failed.png
   Shows a failed poll: status "Failed", the problem "Couldn't reach
   the source", the Details line and the hint "Check connectivity to
   the source and the credentials or path in catalog.yaml, then poll
   again."
   Operator (Dave), light theme, 1280x800.
   Suits: operator guide (runbook: a source fails to poll).
   Alt: The Sources table with a red Failed status and a message below
   the row explaining the source could not be reached and how to fix
   it.

sources-zoom-200.png
   Shows the Sources page at 200 percent zoom (narrow layout): app
   bar collapsed to a menu button, the table reduced to Registration,
   Status, Last attempt, Last success, Action, with the problem row
   still readable.
   Operator, light theme, 1366x1004 (captured at 200% zoom).
   Suits: accessibility note (the UI reflows when zoomed).
   Alt: The Sources page at 200 percent zoom, with the table still
   readable without horizontal scrolling.

Mobile
------

mobile-search.png
   Shows the search page at 390 px: collapsed app bar with menu
   button and "DEV" chip, stacked filters, and result chips wrapping.
   Reader, light theme, 390x2210 (full-page, tall).
   Suits: user guide (using adriano on a phone).
   Alt: The search page on a phone, with the filters stacked above a
   single column of results.

mobile-menu.png
   Shows the app menu open on a phone: Catalog, Sources, the signed-in
   user, the Theme choice (Light, Dark, System with a tick) and Sign
   out.
   Reader (Carol), light theme, 390x2210 (full-page, tall).
   Suits: user guide (changing the theme; signing out on a phone).
   Alt: The phone app menu listing Catalog, Sources, theme options
   Light, Dark and System, and a Sign out entry.

mobile-record-with-errata.png
   Shows an obsolete decision with an erratum at 390 px: sidebar cards
   move below the document, Accept/Reject are in the Approval card.
   Reviewer, light theme, 390x2965 (full-page, very tall).
   Suits: user guide (phone; errata).
   Alt: A decision record on a phone with the document, errata and
   approval card stacked in one column.

Theme
-----

theme-dark-record.png
   Shows a record page in the dark theme with a stale banner.
   Reviewer, dark theme, 1920x1082.
   Suits: user guide (changing the theme).
   Alt: A decision record page in the dark theme with light text on a
   dark background and a blue Accept button.

Missing screens
---------------

No screenshot exists for these; recapture them if a guide needs them:

- Dev sign-in dialog (the preset buttons Reader, Reviewer, Operator).
- Real OIDC sign-in and the sign-out confirmation.
- The user menu opened on desktop (theme choice on a wide screen).
- A record with a decision-history table of several decisions on
  desktop (only partly visible in the review shots).
- Backend degraded or offline status chip in the app bar.
- Not-found page and auth-blocking screen (access denied).
- Empty search result ("no results") in the current UI; only an
  old pre-fix shot existed and it was not kept.
- Sources page as a reader (the note about who can poll).
- A source with status "partial" and a multi-item problem list.
- Light-theme search with sort set to "Recently changed".
- A sign-in with a GitLab or OIDC-backed deployment (operator view of
  configuration); there is no UI for configuration itself.
