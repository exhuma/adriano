"""
Operator-triggered polls (``POST /api/v1/sources[/{id}]/poll``).

:func:`select_poll_targets` validates the request up front (so the HTTP
layer can answer 404/409 before accepting); :func:`run_polls` then runs
:class:`~app.services.polling.PollingService` to completion. It is
**blocking** (the polling service makes synchronous database calls) and
is meant to run in a worker thread, e.g. as a FastAPI background task
of a plain ``def``; it starts its own event loop with
:func:`asyncio.run`.

Concurrency: each registration's write phase takes the per-registration
advisory lock, so a triggered poll that overlaps a running one (cron,
CLI or another trigger) waits for the lock and then applies its own
consistent result. Progress and outcome are visible through
``GET /api/v1/sources`` (``last_attempt_at``, ``last_status``).

Public API: :func:`select_poll_targets`, :func:`run_polls`.
"""

import asyncio
import logging
from collections.abc import Sequence

from app.catalog_config import CatalogConfig
from app.domain.frontmatter import JsonValue
from app.errors import ConflictError, NotFoundError
from app.services.polling import PollingService

__all__ = ["run_polls", "select_poll_targets"]

logger = logging.getLogger(__name__)


def select_poll_targets(
    config: CatalogConfig, source_id: str | None
) -> list[str]:
    """
    Resolve which registrations a poll request covers.

    :param config: Loaded configuration.
    :param source_id: One registration id, or ``None`` for all.
    :returns: Pollable registration ids, in configuration order.
    :raises NotFoundError: If *source_id* is not configured.
    :raises ConflictError: If nothing requested can be polled
        (disabled registration, push-only intake, or no pollable
        registration at all).
    """
    if source_id is None:
        targets = [s.id for s in config.sources if s.pollable]
        if not targets:
            raise ConflictError(
                "nothing to poll: no enabled registration has poll intake",
                code="not_pollable",
            )
        return targets
    source = config.get_source(source_id)
    if source is None:
        raise NotFoundError(
            f"no source registration {source_id!r}", code="unknown_source"
        )
    if not source.pollable:
        reason = source.config_error or "poll intake is not enabled"
        raise ConflictError(
            f"source {source_id!r} cannot be polled: {reason}",
            code="not_pollable",
        )
    return [source_id]


async def _poll(
    service: PollingService, source_ids: Sequence[str], trigger: JsonValue
) -> None:
    """
    Poll each registration in turn, logging every outcome.

    :param service: The polling service.
    :param source_ids: Registration ids.
    :param trigger: Who triggered the poll (stored with the run).
    """
    for source_id in source_ids:
        outcome = await service.poll_source(source_id, trigger=trigger)
        logger.info("triggered poll %s: %s", source_id, outcome.status)


def run_polls(
    service: PollingService, source_ids: Sequence[str], trigger: JsonValue
) -> None:
    """
    Run the polls to completion (blocking; call from a worker thread).

    Errors are logged, never raised: the HTTP response was already
    sent, and the outcome is recorded on the registration.

    :param service: The polling service.
    :param source_ids: Registration ids from :func:`select_poll_targets`.
    :param trigger: Who triggered the poll (no secrets).
    """
    try:
        asyncio.run(_poll(service, source_ids, trigger))
    except Exception:
        logger.exception("triggered poll of %s failed", list(source_ids))
