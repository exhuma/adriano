"""
Full-text search and the SQL approval-state expression.

:func:`approval_join` mirrors :func:`app.domain.approval.evaluate` rule
by rule (see that module's docstring) as a set-based SQL expression
over ``decision_event``, so the "needs approval" filter is applied
before pagination:

1. no valid policy -> ``policy_missing``;
2. policy not required -> ``not_required``;
3. / 4. the event for (identity, current digest) is accepted /
   rejected -> ``accepted`` / ``rejected``;
5. an accepted event for the identity exists (necessarily for another
   digest, because rules 3/4 did not apply) ->
   ``changed_since_acceptance``;
6. otherwise ``pending``.

Rules 1 and 2 depend only on the policy and are resolved in Python to a
constant. A parity test compares this expression with the domain
function on a fixture set.

Rules 3/4 join ``decision_event`` on identity and digest directly: the
unique constraint ``uq_decision_event_identity_digest`` (one formal
decision per content hash, see ``phases/DECISIONS.md``) guarantees at
most one event, so that event *is* the domain's "latest event for the
current digest" and the join never duplicates a record row. Rule 5
is an ``EXISTS`` over the identity's accepted events, which
PostgreSQL plans as a hashed subplan (one scan of the accepted events)
when many rows are evaluated and as per-row probes of
``uq_decision_event_identity_digest`` (identity prefix) for a single
page. This replaced two correlated ``ORDER BY ... LIMIT 1`` subqueries
that ran ~20,000 index probes per statement at 20,000 records and
whose cost estimate pushed PostgreSQL into ~0.4-0.8 s of JIT
compilation per statement (see ``docs/benchmark.md``); the new
statements cost far below ``jit_above_cost``, so JIT stays off without
any setting.

Without the "needs approval" filter the state does not restrict the
rows, so the page is selected first and only its rows are joined to
the decision events; with the filter the join precedes ``LIMIT``.

The ``record_kind`` filter (decisions / errata) is a plain WHERE
condition shared by both paths, so it combines with every other filter
including "needs approval".

Text queries use ``websearch_to_tsquery`` with the ``simple``
configuration (exact tokens: identifiers, UUIDs, paths) OR'ed with the
``english`` configuration (stemmed body words), matching how the
``record.search`` vector is built by the migration trigger.

Public API: :data:`NEEDS_APPROVAL_STATES`, :func:`approval_join`,
:func:`search`.
"""

from sqlalchemy import (
    ColumnElement,
    FromClause,
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

_IDENTITY = ("source_id", "project", "record_key")

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
    "links",
)

#: Labels of the sort keys carried by the paged subquery.
_RANK = "search_rank"
_TITLE_KEY = "title_key"


def _same_identity(left: FromClause, right: FromClause) -> ColumnElement:
    """
    Match the logical identity columns of two relations.

    :param left: Relation with ``source_id``, ``project``, ``record_key``.
    :param right: Relation with the same columns.
    :returns: The AND of the three equalities.
    """
    return and_(*(left.c[name] == right.c[name] for name in _IDENTITY))


def approval_join(
    base: FromClause, policy: Policy | None
) -> tuple[FromClause, ColumnElement[str]]:
    """
    Join record rows to the evidence their approval state depends on.

    :param base: ``record`` or a subquery of it exposing the identity
        columns and ``digest``.
    :param policy: The configured policy, or ``None`` if missing or
        invalid.
    :returns: The relation to select from (*base* itself when the
        policy alone decides the state) and the state expression
        yielding an :class:`~app.domain.approval.ApprovalStateCode`
        value per row.
    """
    if policy is None:
        return base, literal(ApprovalStateCode.POLICY_MISSING.value)
    if not policy.required:
        return base, literal(ApprovalStateCode.NOT_REQUIRED.value)
    current = DECISION.alias("current_decision")
    accepted = DECISION.alias("accepted_decision")
    accepted_any = exists().where(
        _same_identity(accepted, base),
        accepted.c.action == DecisionAction.ACCEPTED.value,
    )
    joined = base.outerjoin(
        current,
        and_(
            _same_identity(current, base),
            current.c.digest == base.c.digest,
        ),
    )
    state = case(
        (
            current.c.action == DecisionAction.ACCEPTED.value,
            ApprovalStateCode.ACCEPTED.value,
        ),
        (
            current.c.action == DecisionAction.REJECTED.value,
            ApprovalStateCode.REJECTED.value,
        ),
        (
            accepted_any,
            ApprovalStateCode.CHANGED_SINCE_ACCEPTANCE.value,
        ),
        else_=ApprovalStateCode.PENDING.value,
    )
    return joined, state


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
    filters: SearchFilters, tsquery: ColumnElement | None
) -> list[ColumnElement[bool]]:
    """
    Translate the state-independent filters into WHERE conditions.

    :param filters: Search filters (``needs_approval`` is handled by
        the caller).
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
    if filters.record_kind is not None:
        result.append(RECORD.c.record_kind == filters.record_kind.value)
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


def _sort_keys(tsquery: ColumnElement | None) -> list[ColumnElement]:
    """
    Build the result order over ``record``: rank, title, id.

    :param tsquery: Text query, if any (ranks the hits first).
    :returns: Labelled sort expressions, in order.
    """
    keys: list[ColumnElement] = []
    if tsquery is not None:
        keys.append(func.ts_rank(RECORD.c.search, tsquery).label(_RANK))
    keys += [func.lower(RECORD.c.title).label(_TITLE_KEY), RECORD.c.id]
    return keys


def _key_columns(relation: FromClause, ranked: bool) -> list[ColumnElement]:
    """
    Select the sort keys of :func:`_sort_keys` from a subquery.

    :param relation: Subquery exposing the labelled sort keys.
    :param ranked: Whether a rank key is present.
    :returns: The key columns, in order.
    """
    names = ([_RANK] if ranked else []) + [_TITLE_KEY, "id"]
    return [relation.c[name] for name in names]


def _order(keys: list[ColumnElement], ranked: bool) -> list[ColumnElement]:
    """
    Turn sort keys into ORDER BY expressions (rank descending).

    :param keys: Keys from :func:`_sort_keys` or :func:`_key_columns`.
    :param ranked: Whether the first key is the rank.
    :returns: ORDER BY expressions.
    """
    if not ranked:
        return keys
    return [keys[0].desc(), *keys[1:]]


def _needs_approval_page(
    conditions: list[ColumnElement[bool]],
    tsquery: ColumnElement | None,
    policy: Policy | None,
) -> tuple[Select, Select]:
    """
    Build count and page queries filtered to records needing approval.

    The state join precedes ``LIMIT`` because it restricts the rows.

    :param conditions: State-independent WHERE conditions.
    :param tsquery: Text query, if any.
    :param policy: Configured policy, or ``None``.
    :returns: ``(count query, unpaginated ordered page query)``.
    """
    source, state = approval_join(RECORD, policy)
    needed = state.in_([code.value for code in NEEDS_APPROVAL_STATES])
    where = [*conditions, needed]
    count = select(func.count()).select_from(source).where(*where)
    columns = [RECORD.c[name] for name in _SEARCH_COLUMNS]
    keys = _sort_keys(tsquery)
    ranked = tsquery is not None
    inner = (
        select(*columns, *keys[:-1], state.label("approval_state"))
        .select_from(source)
        .where(*where)
        .subquery("hit")
    )
    page = select(
        *(inner.c[name] for name in _SEARCH_COLUMNS),
        inner.c.approval_state,
    ).order_by(*_order(_key_columns(inner, ranked), ranked))
    return count, page


def _browse_page(
    conditions: list[ColumnElement[bool]],
    tsquery: ColumnElement | None,
    policy: Policy | None,
    limit: int,
    offset: int,
) -> tuple[Select, Select]:
    """
    Build count and page queries without the state filter.

    The page is selected first; only its rows are joined to the
    decision events for their state.

    :param conditions: State-independent WHERE conditions.
    :param tsquery: Text query, if any.
    :param policy: Configured policy, or ``None``.
    :param limit: Page size.
    :param offset: Rows to skip.
    :returns: ``(count query, paginated ordered page query)``.
    """
    count = select(func.count()).select_from(RECORD).where(*conditions)
    keys = _sort_keys(tsquery)
    ranked = tsquery is not None
    columns = [RECORD.c[name] for name in _SEARCH_COLUMNS if name != "id"]
    paged = (
        select(*columns, *keys)
        .where(*conditions)
        .order_by(*_order(keys, ranked))
        .limit(limit)
        .offset(offset)
        .subquery("paged")
    )
    source, state = approval_join(paged, policy)
    page = (
        select(
            *(paged.c[name] for name in _SEARCH_COLUMNS),
            state.label("approval_state"),
        )
        .select_from(source)
        .order_by(*_order(_key_columns(paged, ranked), ranked))
    )
    return count, page


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
    tsquery = _tsquery(query)
    conditions = _conditions(filters, tsquery)
    offset = (page - 1) * page_size
    if filters.needs_approval:
        count, stmt = _needs_approval_page(conditions, tsquery, policy)
        stmt = stmt.limit(page_size).offset(offset)
    else:
        count, stmt = _browse_page(
            conditions, tsquery, policy, page_size, offset
        )
    total = session.execute(count).scalar_one()
    rows = session.execute(stmt).mappings()
    return SearchPage(
        items=tuple(convert.search_item(row) for row in rows),
        total=total,
        page=page,
        page_size=page_size,
    )
