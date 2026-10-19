"""
The ``adriano`` command line (admin processes run as one-off commands).

Commands:

- ``adriano check-config`` -- load ``ADRIANO_CONFIG_FILE`` and print the
  registrations, the approval policy status, the RBAC roles, the
  authentication status (``oidc``, ``dev``, ``oidc+dev`` or
  ``unconfigured``) and every problem. Needs no database. Exit code 0
  without errors (warnings allowed), 1 otherwise.
- ``adriano poll [--source ID]`` -- sync registrations into the database
  and poll every pollable registration (or one). Exit code 0 when every
  polled registration is ``ok``, 1 when any is ``partial``, ``failed`` or
  ``disabled``, 2 for usage errors (unknown ``--source``) or when the
  registrations cannot be synced.
- ``adriano mint-dev-token --sub SUB [--name N] [--email E]
  [--roles a,b] [--minutes N]`` -- print a dev-only HS256 access token
  signed with ``ADRIANO_DEV_SHARED_SECRET`` (exit code 2 when the
  secret is not set). Roles go to ``ADRIANO_OIDC_ROLES_CLAIM``.
- ``adriano seed-synthetic --records N --projects M --source-id ID
  [--seed 42] [--candidates-ratio 0.1] [--decisions-ratio 0.3]
  [--force]`` -- generate and ingest a deterministic synthetic ADR
  corpus for benchmarking (see :mod:`app.services.seed_synthetic`).
  Refuses a database whose name does not look like dev/test/bench
  unless ``--force`` is given. Exit code 2 on usage or database
  errors.

Scheduling is external (cron, Kubernetes CronJob); see
``phases/DECISIONS.md``. This module only phrases results; the work is
done by :mod:`app.services`.

Public API: :func:`main`, :func:`run`.
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from typing import TextIO

from sqlalchemy.exc import SQLAlchemyError

from app.auth.dev import DEFAULT_MINUTES, DevIdentity, mint_dev_token
from app.auth.tokens import auth_status
from app.catalog_config import CatalogConfig, SourceRegistration
from app.composition import (
    build_polling_service,
    build_store_provider,
    load_catalog,
    log_problems,
)
from app.config import Settings, get_settings
from app.domain.frontmatter import JsonValue
from app.errors import NotFoundError
from app.services.polling import PollOutcome
from app.services.registrations import sync_registrations
from app.services.seed_synthetic import (
    SeedConfig,
    looks_like_dev_database,
    seed_catalog,
)
from app.storage.port import PollStatus

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_USAGE = 2


def _parser() -> argparse.ArgumentParser:
    """
    Build the argument parser.

    :returns: The parser.
    """
    parser = argparse.ArgumentParser(
        prog="adriano", description="adriano ADR catalog administration"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "check-config", help="validate catalog.yaml and print its status"
    )
    poll = commands.add_parser(
        "poll", help="poll source registrations into the catalog"
    )
    poll.add_argument("--source", metavar="ID", help="poll only this id")
    mint = commands.add_parser(
        "mint-dev-token",
        help="print a dev-only HS256 token (needs the dev shared secret)",
    )
    mint.add_argument("--sub", required=True, help="token subject")
    mint.add_argument("--name", help="display name")
    mint.add_argument("--email", help="email address")
    mint.add_argument("--roles", default="", help="comma-separated role names")
    mint.add_argument(
        "--minutes",
        type=int,
        default=DEFAULT_MINUTES,
        help=f"lifetime in minutes (default {DEFAULT_MINUTES})",
    )
    _add_seed_synthetic_parser(commands)
    return parser


def _add_seed_synthetic_parser(
    commands: argparse._SubParsersAction,
) -> None:
    """
    Register the ``seed-synthetic`` subcommand's arguments.

    :param commands: Subparsers action of the main parser.
    """
    seed = commands.add_parser(
        "seed-synthetic",
        help="seed a deterministic synthetic ADR corpus (dev/bench only)",
    )
    seed.add_argument(
        "--records", type=int, required=True, help="published records"
    )
    seed.add_argument(
        "--projects", type=int, required=True, help="number of projects"
    )
    seed.add_argument(
        "--source-id",
        required=True,
        help="target registration id (configured in catalog.yaml)",
    )
    seed.add_argument(
        "--seed", type=int, default=42, help="random seed (default 42)"
    )
    seed.add_argument(
        "--candidates-ratio",
        type=float,
        default=0.1,
        help="share of identities with a competing candidate (default 0.1)",
    )
    seed.add_argument(
        "--decisions-ratio",
        type=float,
        default=0.3,
        help="share of identities with a decision event (default 0.3)",
    )
    seed.add_argument(
        "--force",
        action="store_true",
        help="seed even if the database name does not look like dev/bench",
    )


def _mint(settings: Settings, args: argparse.Namespace, out: TextIO) -> int:
    """
    Run ``mint-dev-token``.

    :param settings: Application settings.
    :param args: Parsed arguments.
    :param out: Output stream (receives only the token).
    :returns: Exit code.
    """
    if not settings.dev_shared_secret:
        print(
            "error: ADRIANO_DEV_SHARED_SECRET is not set (dev only; put it "
            "in your local .env)",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if args.minutes < 1:
        print("error: --minutes must be at least 1", file=sys.stderr)
        return EXIT_USAGE
    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    identity = DevIdentity(
        sub=args.sub, name=args.name, email=args.email, roles=roles
    )
    print(mint_dev_token(settings, identity, minutes=args.minutes), file=out)
    return EXIT_OK


def _describe_source(source: SourceRegistration) -> str:
    """
    Phrase one registration for the console.

    :param source: The registration.
    :returns: One line.
    """
    if not source.enabled:
        state = f"DISABLED: {source.config_error}"
    else:
        intake = ", ".join(sorted(source.intake))
        state = f"enabled (intake: {intake}; ref: {source.published_ref})"
    return f"  {source.id} [{source.type or '?'}] {state}"


def _print_config(config: CatalogConfig, out: TextIO) -> None:
    """
    Print the configuration summary.

    :param config: Loaded configuration.
    :param out: Output stream.
    """
    print(f"Configuration file: {config.path} ({config.file_status})", file=out)
    print(f"Registrations ({len(config.sources)}):", file=out)
    for source in config.sources:
        print(_describe_source(source), file=out)
    policy = config.policy
    detail = (
        f"{policy.policy.id} v{policy.policy.version}, "
        f"required={str(policy.policy.required).lower()}"
        if policy.policy is not None
        else policy.message
    )
    print(f"Approval policy: {policy.status} ({detail})", file=out)
    print(
        f"RBAC roles: {', '.join(sorted(config.rbac.roles)) or '-'}", file=out
    )
    print(f"Problems ({len(config.problems)}):", file=out)
    for problem in config.problems:
        print(
            f"  {problem.severity}: {problem.location}: {problem.message}",
            file=out,
        )


def _check_config(settings: Settings, out: TextIO) -> int:
    """
    Run ``check-config``.

    :param settings: Application settings.
    :param out: Output stream.
    :returns: Exit code.
    """
    config = load_catalog(settings)
    _print_config(config, out)
    print(f"Authentication: {auth_status(settings)}", file=out)
    return EXIT_PROBLEMS if config.has_errors else EXIT_OK


def _print_outcome(outcome: PollOutcome, out: TextIO) -> None:
    """
    Print one poll outcome.

    :param outcome: The outcome.
    :param out: Output stream.
    """
    c = outcome.counts
    print(
        f"{outcome.source_id}: {outcome.status} (projects {c.projects}, "
        f"documents {c.documents}, fetched {c.fetched}, unchanged "
        f"{c.unchanged}, created {c.created}, updated {c.updated}, "
        f"deleted {c.deleted}, failed {c.failed})",
        file=out,
    )
    for problem in outcome.problems:
        where = "/".join(p for p in (problem.project, problem.path) if p)
        suffix = f" [{where}]" if where else ""
        print(f"  {problem.code}{suffix}: {problem.message}", file=out)


async def _run_poll(
    settings: Settings, config: CatalogConfig, source_id: str | None
) -> list[PollOutcome]:
    """
    Sync registrations and poll.

    :param settings: Application settings.
    :param config: Loaded configuration.
    :param source_id: Only this registration, or all.
    :returns: The outcomes.
    :raises NotFoundError: If *source_id* is not configured.
    """
    provider = build_store_provider(settings)
    sync_registrations(provider, config)
    service = build_polling_service(provider, config)
    trigger: JsonValue = {"trigger": "cli"}
    if source_id is not None:
        return [await service.poll_source(source_id, trigger=trigger)]
    return await service.poll_all(trigger=trigger)


def _poll(settings: Settings, source_id: str | None, out: TextIO) -> int:
    """
    Run ``poll``.

    :param settings: Application settings.
    :param source_id: Only this registration, or all.
    :param out: Output stream.
    :returns: Exit code.
    """
    config = load_catalog(settings)
    log_problems(config)
    try:
        outcomes = asyncio.run(_run_poll(settings, config, source_id))
    except NotFoundError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return EXIT_USAGE
    except SQLAlchemyError as exc:
        print(
            f"error: database unavailable ({type(exc).__name__}); run "
            f"`task db:up && task migrate`",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if not outcomes:
        print(
            "nothing to poll: no enabled registration with poll intake",
            file=out,
        )
    for outcome in outcomes:
        _print_outcome(outcome, out)
    if all(outcome.status is PollStatus.OK for outcome in outcomes):
        return EXIT_OK
    return EXIT_PROBLEMS


def _seed_synthetic(
    settings: Settings, args: argparse.Namespace, out: TextIO
) -> int:
    """
    Run ``seed-synthetic``.

    :param settings: Application settings.
    :param args: Parsed arguments.
    :param out: Output stream.
    :returns: Exit code.
    """
    if args.records < 1 or args.projects < 1:
        print("error: --records and --projects must be >= 1", file=sys.stderr)
        return EXIT_USAGE
    database_url = str(settings.database_url)
    if not args.force and not looks_like_dev_database(database_url):
        print(
            "error: this database does not look like a dev/test/bench "
            "database; pass --force to seed it anyway",
            file=sys.stderr,
        )
        return EXIT_USAGE
    config = load_catalog(settings)
    log_problems(config)
    provider = build_store_provider(settings)
    seed_config = SeedConfig(
        records=args.records,
        projects=args.projects,
        source_id=args.source_id,
        seed=args.seed,
        candidates_ratio=args.candidates_ratio,
        decisions_ratio=args.decisions_ratio,
    )
    try:
        summary = seed_catalog(
            provider,
            config,
            seed_config,
            progress=lambda message: print(message, file=out),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except SQLAlchemyError as exc:
        print(
            f"error: database unavailable ({type(exc).__name__}); run "
            f"`task db:up && task migrate`",
            file=sys.stderr,
        )
        return EXIT_USAGE
    print(
        f"seeded {summary.published} published, {summary.candidates} "
        f"candidates, {summary.decisions} decisions",
        file=out,
    )
    return EXIT_OK


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    out: TextIO | None = None,
) -> int:
    """
    Run the CLI.

    :param argv: Arguments without the program name (default: argv).
    :param settings: Settings override (default: from the environment).
    :param out: Output stream (default: stdout).
    :returns: Exit code.
    """
    args = _parser().parse_args(argv)
    settings = settings or get_settings()
    stream = out or sys.stdout
    if args.command == "check-config":
        return _check_config(settings, stream)
    if args.command == "mint-dev-token":
        return _mint(settings, args, stream)
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    if args.command == "seed-synthetic":
        return _seed_synthetic(settings, args, stream)
    return _poll(settings, args.source, stream)


def run() -> None:
    """Console-script entry point (``adriano``)."""
    sys.exit(main())
