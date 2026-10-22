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
- ``adriano migrate`` -- apply the database migrations (``alembic
  upgrade head``) under a PostgreSQL advisory lock, so concurrent runs
  (replicas, init containers) are safe. Exit code 0 on success, 2 when
  the database is unreachable or a migration fails.
- ``adriano serve`` -- the container command: when
  ``ADRIANO_MIGRATE_ON_START`` is true (the default), run the same
  locked migration first (exit code 2 if it fails), then replace this
  process with Uvicorn serving ``app.main:app`` on ``0.0.0.0:8000``
  with ``ADRIANO_WORKERS`` workers (and ``ADRIANO_FORWARDED_ALLOW_IPS``
  as ``--forwarded-allow-ips`` when set).

Outbound TLS: ``check-config``, ``poll``, ``seed-synthetic`` and
``serve`` build the shared outbound TLS context (:mod:`app.tls`) before
doing anything else, so an unloadable ``ADRIANO_EXTRA_CA_CERTS`` entry
stops them with exit code 2 (``serve`` before migrating). ``migrate``
and ``mint-dev-token`` make no outbound HTTPS calls and do not load
it: a broken CA mount must not block the schema migration (the server
container still refuses to start). Every command except
``mint-dev-token`` logs to stderr at INFO, which includes the list of
extra CA certificates.

Scheduling is external (cron, Kubernetes CronJob); see
``docs/developer/decisions/0008-external-poll-job.rst``. This module
only phrases results; the work is done by :mod:`app.services`.

Public API: :func:`main`, :func:`run`.
"""

import argparse
import asyncio
import logging
import os
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
from app.errors import ConfigurationError, NotFoundError
from app.services.polling import PollOutcome
from app.services.registrations import sync_registrations
from app.services.seed_synthetic import (
    SeedConfig,
    looks_like_dev_database,
    seed_catalog,
)
from app.storage.port import PollStatus
from app.storage.postgres.migrations import upgrade_to_head
from app.tls import ssl_context_from_settings

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_USAGE = 2

#: Commands that can make outbound HTTPS calls (OIDC, network
#: sources); they load the outbound TLS context first.
OUTBOUND_COMMANDS = frozenset(
    {"check-config", "poll", "seed-synthetic", "serve"}
)

#: Address and port ``adriano serve`` binds (the image's EXPOSE).
SERVE_HOST = "0.0.0.0"
SERVE_PORT = 8000


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
    commands.add_parser(
        "migrate", help="apply the database migrations (advisory-locked)"
    )
    commands.add_parser(
        "serve",
        help="migrate (unless ADRIANO_MIGRATE_ON_START=false), then run "
        "the web server",
    )
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


def _load_outbound_tls(settings: Settings) -> int:
    """
    Build the outbound TLS context, so a bad CA file fails early.

    :param settings: Application settings.
    :returns: Exit code: :data:`EXIT_OK`, or :data:`EXIT_USAGE` when
        an ``ADRIANO_EXTRA_CA_CERTS`` entry cannot be loaded.
    """
    try:
        ssl_context_from_settings(settings)
    except ConfigurationError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return EXIT_USAGE
    return EXIT_OK


def _print_database_error(exc: SQLAlchemyError) -> None:
    """
    Explain a database failure on stderr.

    :param exc: The error.
    """
    print(
        f"error: database unavailable or not migrated "
        f"({type(exc).__name__}); check ADRIANO_DATABASE_URL and run "
        f"`adriano migrate` (development: `task db:up && task migrate`)",
        file=sys.stderr,
    )


def _migrate(settings: Settings, out: TextIO) -> int:
    """
    Run ``migrate``.

    :param settings: Application settings.
    :param out: Output stream.
    :returns: Exit code.
    """
    try:
        upgrade_to_head(str(settings.database_url))
    except SQLAlchemyError as exc:
        print(
            f"error: migration failed ({type(exc).__name__}: {exc}); "
            "check ADRIANO_DATABASE_URL and that the database is "
            "reachable",
            file=sys.stderr,
        )
        return EXIT_USAGE
    except ConfigurationError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return EXIT_USAGE
    print("database migrated to head", file=out)
    return EXIT_OK


def _exec(argv: list[str]) -> None:
    """
    Replace the current process with *argv* (never returns).

    :param argv: Program and arguments; ``argv[0]`` is the executable.
    """
    os.execv(argv[0], argv)


def uvicorn_argv(settings: Settings) -> list[str]:
    """
    Build the Uvicorn command line of ``adriano serve``.

    Uvicorn runs with this interpreter, so it always comes from the
    same environment as the application.

    :param settings: Application settings.
    :returns: The argument vector, executable first.
    """
    argv = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        SERVE_HOST,
        "--port",
        str(SERVE_PORT),
        "--workers",
        str(settings.workers),
    ]
    if settings.forwarded_allow_ips:
        argv += ["--forwarded-allow-ips", settings.forwarded_allow_ips]
    return argv


def _serve(settings: Settings, out: TextIO) -> int:
    """
    Run ``serve``: optionally migrate, then exec Uvicorn.

    :param settings: Application settings.
    :param out: Output stream.
    :returns: Exit code (only when the migration fails; otherwise the
        process is replaced).
    """
    if settings.migrate_on_start:
        code = _migrate(settings, out)
        if code != EXIT_OK:
            return code
    out.flush()
    _exec(uvicorn_argv(settings))
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
        _print_database_error(exc)
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
        _print_database_error(exc)
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
    if args.command == "mint-dev-token":
        return _mint(settings, args, stream)
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    if args.command in OUTBOUND_COMMANDS:
        code = _load_outbound_tls(settings)
        if code != EXIT_OK:
            return code
    if args.command == "check-config":
        return _check_config(settings, stream)
    if args.command == "seed-synthetic":
        return _seed_synthetic(settings, args, stream)
    if args.command == "migrate":
        return _migrate(settings, stream)
    if args.command == "serve":
        return _serve(settings, stream)
    return _poll(settings, args.source, stream)


def run() -> None:
    """Console-script entry point (``adriano``)."""
    sys.exit(main())
