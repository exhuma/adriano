"""
Full-text search and the SQL approval-state expression.

:func:`approval_state` mirrors :func:`app.domain.approval.evaluate` rule
by rule (see that module's docstring) as a SQL expression over
``decision_event``, so the "needs approval" filter is applied before
pagination:

1. no valid policy -> ``policy_missing``;
2. policy not required -> ``not_required``;
3. / 4. latest event for (identity, current digest) is accepted /
   rejected -> ``accepted`` / ``rejected``;
5. an accepted event for the identity exists (necessarily for another
   digest, because rules 3/4 did not apply) ->
   ``changed_since_acceptance``;
6. otherwise ``pending``.

Rules 1 and 2 depend only on the policy and are resolved in Python to a
constant. A parity test compares this expression with the domain
function on a fixture set.

Text queries use ``websearch_to_tsquery`` with the ``simple``
configuration (exact tokens: identifiers, UUIDs, paths) OR'ed with the
``english`` configuration (stemmed body words), matching how the
``record.search`` vector is built by the migration trigger.

Public API: :data:`NEEDS_APPROVAL_STATES`, :func:`approval_state`,
:func:`search`.
"""

from sqlalchemy import (
    ColumnElement,
    Select,
    Table,
    and_,
    case,
    exists,
    func,
    literal,
    literal_column,
    select,
)
from sqlalchemy.orm import Session

from app.domain.approval import ApprovalStateCode, DecisionAction, Policy
from app.storage.port import (
    MAX_PAGE_SIZE,
    SearchFilters,
    SearchPage,
)
from app.storage.postgres import convert
from app.storage.postgres.models import DecisionEventRow
from app.storage.postgres.records import RECORD

DECISION: Table = DecisionEventRow.__table__  # type: ignore[assignment]

#: States for which :func:`app.domain.approval.evaluate` reports
#: ``needs_approval``.
NEEDS_APPROVAL_STATES: frozenset[ApprovalStateCode] = frozenset(
    {
        ApprovalStateCode.POLICY_MISSING,
        ApprovalStateCode.REJECTED,
        ApprovalStateCode.CHANGED_SINCE_ACCEPTANCE,
        ApprovalStateCode.PENDING,
    }
)

_SIMPLE = literal_column("'simple'::regconfig")
_ENGLISH = literal_column("'english'::regconfig")

_SEARCH_COLUMNS = (
    "id",
    "kind",
    "source_id",
    "project",
    "path",
    "ref",
    "adr_uuid",
    "record_key",
    "digest",
    "title",
    "record_kind",
    "decision_date",
    "decision_date_inferred",
    "issues",
)


def approval_state(policy: Policy | None) -> ColumnElement[str]:
    """
    Build the per-row approval-state expression for ``record``.

    :param policy: The configured policy, or ``None`` if missing or
        invalid.
    :returns: A text expression yielding an
        :class:`~app.domain.approval.ApprovalStateCode` value.
    """
    if policy is None:
        return literal(ApprovalStateCode.POLICY_MISSING.value)
    if not policy.required:
        return literal(ApprovalStateCode.NOT_REQUIRED.value)
    event = DECISION.alias("de")
    same_identity = and_(
        event.c.source_id == RECORD.c.source_id,
        event.c.project == RECORD.c.project,
        event.c.record_key == RECORD.c.record_key,
    )
    current_action = (
        select(event.c.action)
        .where(same_identity, event.c.digest == RECORD.c.digest)
        .order_by(event.c.created_at.desc(), event.c.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    accepted_any = exists().where(
        same_identity, event.c.action == DecisionAction.ACCEPTED.value
    )
    return case(
        (
            current_action == DecisionAction.ACCEPTED.value,
            ApprovalStateCode.ACCEPTED.value,
        ),
        (
            current_action == DecisionAction.REJECTED.value,
            ApprovalStateCode.REJECTED.value,
        ),
        (accepted_any, ApprovalStateCode.CHANGED_SINCE_ACCEPTANCE.value),
        else_=ApprovalStateCode.PENDING.value,
    )


def _tsquery(query: str | None) -> ColumnElement | None:
    """
    Build the combined ``simple`` OR ``english`` text query.

    :param query: User text.
    :returns: A ``tsquery`` expression, or ``None`` for a blank query.
    """
    text = (query or "").strip()
    if not text:
        return None
    simple = func.websearch_to_tsquery(_SIMPLE, text)
    english = func.websearch_to_tsquery(_ENGLISH, text)
    return simple.op("||")(english)


def _conditions(
    filters: SearchFilters,
    state: ColumnElement[str],
    tsquery: ColumnElement | None,
) -> list[ColumnElement[bool]]:
    """
    Translate filters into WHERE conditions.

    :param filters: Search filters.
    :param state: Approval-state expression.
    :param tsquery: Text query, if any.
    :returns: Conditions to AND together.
    """
    result: list[ColumnElement[bool]] = []
    if filters.source_id is not None:
        result.append(RECORD.c.source_id == filters.source_id)
    if filters.project is not None:
        result.append(RECORD.c.project == filters.project)
    if filters.kind is not None:
        result.append(RECORD.c.kind == filters.kind.value)
    if filters.needs_approval:
        result.append(state.in_([code.value for code in NEEDS_APPROVAL_STATES]))
    if tsquery is not None:
        result.append(RECORD.c.search.op("@@")(tsquery))
    return result


def _check_bounds(page: int, page_size: int) -> None:
    """
    Validate pagination arguments.

    :param page: 1-based page number.
    :param page_size: Page size.
    :raises ValueError: If out of bounds.
    """
    if page < 1:
        raise ValueError(f"page must be >= 1, got {page}")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(
            f"page_size must be between 1 and {MAX_PAGE_SIZE}, got {page_size}"
        )


def _page_query(
    state: ColumnElement[str],
    conditions: list[ColumnElement[bool]],
    tsquery: ColumnElement | None,
) -> Select:
    """
    Build the ordered result query (without limit/offset).

    :param state: Approval-state expression.
    :param conditions: WHERE conditions.
    :param tsquery: Text query, if any (ranks the hits).
    :returns: The select.
    """
    columns = [RECORD.c[name] for name in _SEARCH_COLUMNS]
    stmt = select(*columns, state.label("approval_state")).where(*conditions)
    order: list[ColumnElement] = []
    if tsquery is not None:
        order.append(func.ts_rank(RECORD.c.search, tsquery).desc())
    order += [func.lower(RECORD.c.title), RECORD.c.id]
    return stmt.order_by(*order)


def search(
    session: Session,
    query: str | None,
    filters: SearchFilters,
    page: int,
    page_size: int,
    policy: Policy | None,
) -> SearchPage:
    """
    Run a filtered, paginated full-text search.

    :param session: Unit-of-work session.
    :param query: Free text, or ``None``/blank for all records.
    :param filters: Filters.
    :param page: 1-based page number.
    :param page_size: Page size, 1 to :data:`MAX_PAGE_SIZE`.
    :param policy: Configured policy, or ``None``.
    :returns: The page.
    :raises ValueError: If *page* or *page_size* is out of bounds.
    """
    _check_bounds(page, page_size)
    state = approval_state(policy)
    tsquery = _tsquery(query)
    conditions = _conditions(filters, state, tsquery)
    total = session.execute(
        select(func.count()).select_from(RECORD).where(*conditions)
    ).scalar_one()
    stmt = (
        _page_query(state, conditions, tsquery)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = session.execute(stmt).mappings()
    return SearchPage(
        items=tuple(convert.search_item(row) for row in rows),
        total=total,
        page=page,
        page_size=page_size,
    )
