#!/usr/bin/env python3
"""
HTTP latency benchmark for the adriano search/browse API (phase 09).

stdlib + httpx only, besides minting a dev token in-process through
:mod:`app.auth.dev` -- exactly what ``adriano mint-dev-token`` does,
given ``ADRIANO_DEV_SHARED_SECRET`` in the environment -- when
``--token`` is not given. Run against a backend already started by
``task bench`` (see ``Taskfile.yml``) or by hand; see
``docs/benchmark.md`` for the full method and results.

Scenarios, each run for ``--requests`` after a ``--warmup`` of
discarded requests, at every concurrency in ``--concurrency``:

- ``free_text``: ``GET /api/v1/records?q=<random vocabulary term>``.
- ``filtered``: ``GET /api/v1/records?source=&project=&state=``.
- ``needs_approval``: ``GET /api/v1/records?needs_approval=true``.
- ``detail``: ``GET /api/v1/records/{id}`` for ids collected from an
  initial search page.
- ``sources``: ``GET /api/v1/sources``.

Reports p50/p95/p99/max/mean latency (milliseconds) and error counts
per scenario and concurrency, as a table to stdout and as JSON to
``--out``.

Public API: :func:`main`.
"""

import argparse
import json
import random
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.auth.dev import DevIdentity, mint_dev_token
from app.config import Settings
from app.services.seed_synthetic_text import VOCABULARY

__all__ = ["main"]

_DEFAULT_PAGE_SIZE = 20


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestOutcome:
    """
    Result of one timed HTTP request.

    :param elapsed_ms: Wall-clock time of the request, in milliseconds.
    :param ok: Whether the response was a successful (``2xx``) status.
    """

    elapsed_ms: float
    ok: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ScenarioStats:
    """
    Latency statistics of one scenario at one concurrency.

    :param name: Scenario name.
    :param concurrency: Concurrent workers used.
    :param count: Measured requests (after warm-up).
    :param errors: Requests that did not return ``2xx`` or raised.
    :param p50: 50th percentile latency, milliseconds.
    :param p95: 95th percentile latency, milliseconds.
    :param p99: 99th percentile latency, milliseconds.
    :param max_ms: Maximum latency, milliseconds.
    :param mean_ms: Mean latency, milliseconds.
    """

    name: str
    concurrency: int
    count: int
    errors: int
    p50: float
    p95: float
    p99: float
    max_ms: float
    mean_ms: float

    def as_dict(self) -> dict[str, float | int | str]:
        """
        Convert to a JSON-serialisable mapping.

        :returns: The mapping.
        """
        return {
            "name": self.name,
            "concurrency": self.concurrency,
            "count": self.count,
            "errors": self.errors,
            "p50_ms": round(self.p50, 1),
            "p95_ms": round(self.p95, 1),
            "p99_ms": round(self.p99, 1),
            "max_ms": round(self.max_ms, 1),
            "mean_ms": round(self.mean_ms, 1),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class Scenario:
    """
    One benchmark scenario.

    :param name: Stable, short name.
    :param request: Builds one ``(path, params)`` request; called once
        per request, so it may vary by randomness.
    """

    name: str
    request: Callable[[], tuple[str, dict[str, str]]]


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """
    Nearest-rank percentile of an already-sorted sequence.

    :param sorted_values: Values sorted ascending; must be non-empty.
    :param pct: Percentile in ``[0, 100]``.
    :returns: The value at that percentile.
    """
    index = min(int(pct / 100 * len(sorted_values)), len(sorted_values) - 1)
    return sorted_values[index]


def mint_token(settings: Settings, sub: str, roles: Sequence[str]) -> str:
    """
    Mint a dev-only HS256 token in-process, like ``mint-dev-token``.

    :param settings: Application settings (reads the dev shared
        secret and OIDC audience/issuer/roles-claim settings).
    :param sub: Token subject.
    :param roles: Role names.
    :returns: The encoded token.
    :raises ValueError: If ``ADRIANO_DEV_SHARED_SECRET`` is not set.
    """
    return mint_dev_token(settings, DevIdentity(sub=sub, roles=roles))


def _request(
    client: httpx.Client, path: str, params: dict[str, str]
) -> RequestOutcome:
    """
    Run and time one GET request, never raising.

    :param client: Shared HTTP client (authenticated).
    :param path: Request path.
    :param params: Query parameters.
    :returns: The outcome.
    """
    start = time.perf_counter()
    try:
        response = client.get(path, params=params)
        ok = 200 <= response.status_code < 300
    except httpx.HTTPError:
        ok = False
    elapsed_ms = (time.perf_counter() - start) * 1000
    return RequestOutcome(elapsed_ms=elapsed_ms, ok=ok)


def run_scenario(
    client: httpx.Client,
    scenario: Scenario,
    *,
    requests: int,
    warmup: int,
    concurrency: int,
) -> ScenarioStats:
    """
    Warm up, then measure one scenario at one concurrency.

    :param client: Shared, authenticated HTTP client.
    :param scenario: The scenario to run.
    :param requests: Requests to measure (after warm-up).
    :param warmup: Requests to discard before measuring.
    :param concurrency: Concurrent workers.
    :returns: The latency statistics.
    """
    for _ in range(warmup):
        _request(client, *scenario.request())
    calls = [scenario.request() for _ in range(requests)]
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        outcomes = list(pool.map(lambda call: _request(client, *call), calls))
    latencies = sorted(outcome.elapsed_ms for outcome in outcomes)
    errors = sum(1 for outcome in outcomes if not outcome.ok)
    return ScenarioStats(
        name=scenario.name,
        concurrency=concurrency,
        count=len(outcomes),
        errors=errors,
        p50=_percentile(latencies, 50),
        p95=_percentile(latencies, 95),
        p99=_percentile(latencies, 99),
        max_ms=latencies[-1],
        mean_ms=statistics.fmean(latencies),
    )


def _fetch_facet(client: httpx.Client, source_id: str) -> str | None:
    """
    Pick one project of *source_id* from ``GET /api/v1/facets``.

    :param client: Authenticated HTTP client.
    :param source_id: Registration id to look up.
    :returns: A project path, or ``None`` if the source has none.
    """
    response = client.get("/api/v1/facets")
    response.raise_for_status()
    for source in response.json()["sources"]:
        if source["source_id"] == source_id and source["projects"]:
            return source["projects"][0]["project"]
    return None


def _fetch_sample_ids(
    client: httpx.Client, source_id: str, count: int
) -> list[str]:
    """
    Collect record ids to use for the ``detail`` scenario.

    :param client: Authenticated HTTP client.
    :param source_id: Registration id to search.
    :param count: Desired number of ids.
    :returns: Up to *count* record ids.
    """
    ids: list[str] = []
    page = 1
    while len(ids) < count:
        response = client.get(
            "/api/v1/records",
            params={
                "source": source_id,
                "page": str(page),
                "page_size": str(_DEFAULT_PAGE_SIZE),
            },
        )
        response.raise_for_status()
        body = response.json()
        ids.extend(item["id"] for item in body["items"])
        if page * _DEFAULT_PAGE_SIZE >= body["total"] or not body["items"]:
            break
        page += 1
    return ids[:count] or ["00000000-0000-0000-0000-000000000000"]


def build_scenarios(
    client: httpx.Client, *, source_id: str, project: str | None, seed: int
) -> list[Scenario]:
    """
    Build the fixed scenario list, resolving its fixture data first.

    :param client: Authenticated HTTP client, used to fetch fixtures
        (a project name and sample ids) before timing starts.
    :param source_id: Registration id used by the filtered scenarios.
    :param project: Project path for the ``filtered`` scenario
        (resolved from the facets endpoint when ``None``).
    :param seed: Random seed for picking vocabulary terms per request.
    :returns: The scenarios.
    """
    rng = random.Random(seed)
    resolved_project = project or _fetch_facet(client, source_id)
    sample_ids = _fetch_sample_ids(client, source_id, 50)

    def free_text() -> tuple[str, dict[str, str]]:
        return "/api/v1/records", {"q": rng.choice(VOCABULARY)}

    def filtered() -> tuple[str, dict[str, str]]:
        params = {"source": source_id, "state": "published"}
        if resolved_project:
            params["project"] = resolved_project
        return "/api/v1/records", params

    def needs_approval() -> tuple[str, dict[str, str]]:
        return "/api/v1/records", {"needs_approval": "true"}

    def detail() -> tuple[str, dict[str, str]]:
        return f"/api/v1/records/{rng.choice(sample_ids)}", {}

    def sources() -> tuple[str, dict[str, str]]:
        return "/api/v1/sources", {}

    return [
        Scenario(name="free_text", request=free_text),
        Scenario(name="filtered", request=filtered),
        Scenario(name="needs_approval", request=needs_approval),
        Scenario(name="detail", request=detail),
        Scenario(name="sources", request=sources),
    ]


def print_table(stats: Sequence[ScenarioStats]) -> None:
    """
    Print the results as a fixed-width table to stdout.

    :param stats: Results, in the order to print.
    """
    header = (
        f"{'scenario':<16}{'conc':>5}{'n':>6}{'err':>5}{'p50':>9}"
        f"{'p95':>9}{'p99':>9}{'max':>9}{'mean':>9}"
    )
    print(header)
    print("-" * len(header))
    for row in stats:
        print(
            f"{row.name:<16}{row.concurrency:>5}{row.count:>6}"
            f"{row.errors:>5}{row.p50:>9.1f}{row.p95:>9.1f}"
            f"{row.p99:>9.1f}{row.max_ms:>9.1f}{row.mean_ms:>9.1f}"
        )


def _parser() -> argparse.ArgumentParser:
    """
    Build the argument parser.

    :returns: The parser.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8100")
    parser.add_argument("--token", help="bearer token (else minted)")
    parser.add_argument("--mint-sub", default="bench")
    parser.add_argument("--mint-roles", default="bench-reader")
    parser.add_argument("--source-id", default="synthetic")
    parser.add_argument("--project", default=None)
    parser.add_argument("--requests", type=int, default=400)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--concurrency", default="1,8")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("bench-results.json"))
    return parser


@dataclass(slots=True, kw_only=True)
class _Args:
    """Typed view of the parsed CLI arguments used by :func:`main`."""

    base_url: str
    token: str | None
    mint_sub: str
    mint_roles: str
    source_id: str
    project: str | None
    requests: int
    warmup: int
    concurrency: str
    seed: int
    out: Path


def _resolve_token(args: _Args) -> str:
    """
    Return the bearer token to use: given, or freshly minted.

    :param args: Parsed arguments.
    :returns: The token.
    :raises ValueError: If no token is given and the dev secret is
        not set.
    """
    if args.token:
        return args.token
    roles = [r.strip() for r in args.mint_roles.split(",") if r.strip()]
    return mint_token(Settings(), args.mint_sub, roles)


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run the benchmark and print/write its results.

    :param argv: Arguments without the program name (default: argv).
    :returns: Process exit code (0, or 1 on a setup failure).
    """
    args = _Args(**vars(_parser().parse_args(argv)))
    try:
        token = _resolve_token(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    concurrencies = [int(c) for c in args.concurrency.split(",") if c]
    results: list[ScenarioStats] = []
    with httpx.Client(
        base_url=args.base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    ) as client:
        scenarios = build_scenarios(
            client,
            source_id=args.source_id,
            project=args.project,
            seed=args.seed,
        )
        for concurrency in concurrencies:
            for scenario in scenarios:
                results.append(
                    run_scenario(
                        client,
                        scenario,
                        requests=args.requests,
                        warmup=args.warmup,
                        concurrency=concurrency,
                    )
                )
    print_table(results)
    args.out.write_text(
        json.dumps([row.as_dict() for row in results], indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
