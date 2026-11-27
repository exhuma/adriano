Performance
===========

The target is a P95 under one second for search and ordinary browsing
against a representative dataset.
No production dataset was available, so the benchmark uses a
reproducible synthetic corpus.
The measurements below were taken on 2026-10-19
(search sort orders on 2026-10-20).

Result
------

Every scenario meets the target at both sizes and both concurrencies.
The worst observed P95 is 269.7 ms
(the "needs approval" filter, 20,000 records, concurrency 8).

P95 latency in milliseconds, 400 measured requests per cell:

.. list-table::
   :header-rows: 1

   * - Scenario
     - 2k, conc 1
     - 2k, conc 8
     - 20k, conc 1
     - 20k, conc 8
   * - ``free_text``
     - 19.5
     - 89.6
     - 57.9
     - 134.1
   * - ``filtered``
     - 14.1
     - 90.4
     - 15.7
     - 81.9
   * - ``needs_approval``
     - 26.5
     - 109.4
     - 114.1
     - 269.7
   * - ``detail``
     - 18.4
     - 98.3
     - 41.4
     - 96.9
   * - ``sources``
     - 7.0
     - 53.2
     - 7.2
     - 42.7

Scenarios
   ``free_text``: ``GET /api/v1/records?q=<random term>``.
   ``filtered``: source, project and ``state=published``.
   ``needs_approval``: ``needs_approval=true``.
   ``detail``: ``GET /api/v1/records/{id}`` for a random record.
   ``sources``: ``GET /api/v1/sources``.

Method
------

Dataset
   ``adriano seed-synthetic`` (:mod:`app.services.seed_synthetic` and its
   helper modules) generates a deterministic corpus (seed 42) and
   ingests it through ``prepare_document`` and ``ingest_document``,
   the same path poll and push use, never raw SQL.
   Sizes: 2,000 and 20,000 published records over 100 projects.
   About 15 % of records link to an earlier one,
   about 5 % are errata,
   about 7 % carry legacy ``signed-off-by``,
   about 5 % carry a deliberate validation issue,
   10 % of identities get a competing candidate,
   and 30 % get a decision (80 % accepted, 20 % rejected).
   The registration is ``bench/catalog.bench.yaml``.

Environment
   One laptop: Intel Core Ultra 5 125U (14 logical CPUs), 15 GiB RAM,
   Linux 6.17, Python 3.14, PostgreSQL 18 in the ephemeral
   ``task db:up`` container (data directory on ``tmpfs``),
   backend as ``uvicorn --workers 4`` on the host,
   client on the same host.

Client
   ``backend/bench/bench.py`` (httpx) signs in through ``POST /auth/dev/login`` (or reuses
   ``--session``; ``--login-sub`` and ``--login-roles`` pick the
   identity),
   discards warm-up requests (50 were used),
   then times 400 requests per scenario at concurrency 1 and 8,
   and reports p50, p95, p99, max and mean.

Limitations
   Templated titles and bodies make search *latency* meaningful but not
   ranking quality.
   One registration of one source type: no multi-registration
   contention, no GitLab adapter.
   Flat decision history, ASCII-only English text.
   A RAM-backed database and a same-host client are faster than a real
   deployment, which adds disk I/O and network latency.
   Treat the shape of the results (which scenario is slow and why) as
   the evidence, not the exact milliseconds.

Optimisations that got us here
------------------------------

Benchmarking at 20,000 records found two costs; both fixes changed
query shape only, with no schema change.

Detail: fetch only the rows that matter
   The detail request used to build its relationship index from every
   published row: about 780 ms per request, of which about 630 ms was
   Python row conversion, not the database.
   ``CatalogStore.list_relationship_candidates`` now fetches only rows
   that can affect one record's view: those sharing its UUID,
   those it links to, and those linking back to it.
   That cut the cost by about 40 times.
   ``test_relationship_candidates_match_the_full_index_view``
   (``storage/test_records.py``) proves the targeted fetch yields the
   same view as the full one.

Needs approval: set-based joins
   The approval state used to be a ``CASE`` with correlated subqueries
   per row.
   About 39,000 probes per statement pushed the planner's cost estimate
   over PostgreSQL's JIT thresholds, adding 0.4 to 0.8 s of JIT
   compilation per statement (P95 1.85 s at concurrency 1,
   4.16 s at concurrency 8).
   :py:obj:`app.storage.postgres.search.approval_join` now uses one
   ``LEFT JOIN`` on identity and digest
   (the unique constraint guarantees at most one match)
   and one ``EXISTS`` for "accepted elsewhere".
   With the filter, the join runs before ``LIMIT``;
   without it, only the page's rows are joined.
   That is about 16 times faster, and JIT no longer triggers;
   the cost grows roughly linearly, so JIT would return at about
   20 times this catalog size.
   ``storage/test_approval_parity.py`` keeps the SQL equal to the
   Python rule.

Measured and deliberately not done
----------------------------------

Extra indexes for decisions
   A composite index on the decision lookup and a partial index on
   accepted events were tried: the planner ignored the first and the
   second saved about 1 ms.
   The unique constraint's index serves every probe.

``count(*) OVER ()`` for needs approval
   Computing the total in the page query measured about 45 to 55 ms
   against about 70 ms for two statements,
   but needs a separate path for pages past the end.
   Not worth it at this headroom.

An index for the "recently changed" sort
   ``sort=recent`` orders by ``updated_at``, then title, then id.
   Every sort is one scan plus a top-N heapsort
   (30 to 60 ms for browse and needs approval, 110 to 155 ms with a text
   query).
   A trial index on ``(updated_at DESC, lower(title), id)`` sped up only
   ``recent`` browsing without a query or filter (35 ms to 0.6 ms) and
   would add write cost to every upsert.
   Add it in a migration only if a real catalog makes that path slow.

Materialised approval state
   Not needed; the state is still derived on read
   (:doc:`decisions/0019-approval-state-derived-on-read`).

Rerunning the benchmark
-----------------------

The benchmark resets and reseeds the ephemeral **development** database
(never the test database), so run it only where losing that data is
fine.
Prerequisites: Docker, uv and go-task, as for local development.

.. code-block:: sh

   # 20,000 records / 100 projects, concurrency 1 and 8
   task bench -- --requests 400 --warmup 50

``task bench`` reseeds the default size itself, starts the backend with
four workers on port 8100 and a throwaway dev secret, runs
``backend/bench/bench.py`` and stops the backend again.
Arguments after ``--`` go to ``bench.py``
(``uv run --project backend python backend/bench/bench.py --help``).
For another size, seed first and then run the client against a backend
started the same way:

.. code-block:: sh

   task bench:seed -- --records 2000 --projects 100
