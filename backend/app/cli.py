"""
The ``adriano`` command line (admin processes run as one-off commands).

Commands:

- ``adriano check-config`` -- load ``ADRIANO_CONFIG_FILE`` and print the
  registrations, the approval policy status and every problem. Needs no
  database. Exit code 0 without errors (warnings allowed), 1 otherwise.
- ``adriano poll [--source ID]`` -- sync registrations into the database
  and poll every pollable registration (or one). Exit code 0 when every
  polled registration is ``ok``, 1 when any is ``partial``, ``failed`` or
  ``disabled``, 2 for usage errors (unknown ``--source``) or when the
  registrations cannot be synced.

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
    return parser


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
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    return _poll(settings, args.source, stream)


def run() -> None:
    """Console-script entry point (``adriano``)."""
    sys.exit(main())
