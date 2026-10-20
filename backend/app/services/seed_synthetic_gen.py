"""
Pure generator for the synthetic benchmark ADR corpus.

No I/O, no storage port, no FastAPI: everything here is a plain
function over :mod:`random`, so a fixed seed reproduces the exact same
documents (:func:`generate_published`, :func:`generate_candidates`,
:func:`generate_decisions`). :mod:`app.services.seed_synthetic`
ingests the result through the normal poll/push path. Title and body
text come from :mod:`app.services.seed_synthetic_text`.

Each generator draws from its own :class:`random.Random`, seeded from
``f"{seed}:<phase>"``, so the phases are independent of call order and
of each other's internal consumption of randomness.

Realism, kept deliberately small:

- titles are built from verb/subject/qualifier word lists;
- bodies are "Context" / "Decision" / "Consequences" sections built
  from sentence templates, stretched or trimmed to 300-3000 characters;
- a share of records link ``updates``/``obsoletes`` to an earlier
  record (by UUID, catalog-wide, matching how
  :mod:`app.services.record_relationships` resolves links); a smaller
  share are errata (``erratum-for``), small RFC-style reports against
  an earlier decision -- not a full ADR body (see
  :mod:`app.services.seed_synthetic_errata`, which owns their
  generation);
- a share use the legacy ``deprecates`` alias or a legacy
  ``signed-off-by`` list;
- a share carry one deliberate validation issue (missing ``uuid``, a
  malformed ``decision-date``, or an unknown field), so the seeded
  catalog exercises the same error/warning paths as real content.

Public API: :class:`GeneratedPublished`, :class:`GeneratedCandidate`,
:class:`GeneratedDecision`, :func:`generate_published`,
:func:`generate_candidates`, :func:`generate_decisions`.
"""

import datetime
import random
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.approval import DecisionAction
from app.domain.hashing import content_digest
from app.services import seed_synthetic_text as text
from app.services.seed_synthetic_errata import build_erratum_document

__all__ = [
    "GeneratedCandidate",
    "GeneratedDecision",
    "GeneratedPublished",
    "generate_candidates",
    "generate_decisions",
    "generate_published",
]

#: Chance a record links to an earlier one via ``updates``/``obsoletes``.
LINK_RATIO = 0.15
#: Chance a record is an erratum (``erratum-for``) against an earlier
#: decision, instead of a new decision.
ERRATUM_RATIO = 0.05
#: Of an ``obsoletes`` link, the chance it is spelled as legacy
#: ``deprecates`` instead.
LEGACY_DEPRECATES_RATIO = 0.3
#: Chance a record carries a legacy ``signed-off-by`` list.
LEGACY_SIGNOFF_RATIO = 0.07
#: Chance a record carries one deliberate validation issue.
ISSUE_RATIO = 0.05
#: Share of decided identities whose decision is "accepted".
_ACCEPT_SHARE = 0.8


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneratedPublished:
    """
    One synthetic published ADR document.

    :param project: Owning project path.
    :param path: File path inside the project.
    :param content: Raw Markdown bytes (frontmatter and body).
    :param adr_uuid: The record's UUID, or ``None`` for a deliberately
        broken record with no stable identity (never a link target).
    """

    project: str
    path: str
    content: bytes
    adr_uuid: uuid.UUID | None


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneratedCandidate:
    """
    One synthetic competing candidate of a published identity.

    :param project: Owning project path (matches the published row).
    :param path: File path inside the project (matches the published
        row; candidates are keyed by ``(source, project, key, ref)``).
    :param ref: Branch/ref, distinct from the published ref.
    :param content: Raw Markdown bytes, a small variant of the
        published content.
    :param adr_uuid: The identity's UUID.
    """

    project: str
    path: str
    ref: str
    content: bytes
    adr_uuid: uuid.UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneratedDecision:
    """
    One synthetic accept/reject decision.

    :param project: Owning project path.
    :param adr_uuid: The decided identity's UUID.
    :param digest: Digest of the decided (published) content.
    :param action: Accepted or rejected.
    """

    project: str
    adr_uuid: uuid.UUID
    digest: str
    action: DecisionAction


def _link_fields(
    rng: random.Random, previous: Sequence[uuid.UUID]
) -> dict[str, object]:
    """
    Decide this record's ``updates``/``obsoletes`` relationship, if any.

    :param rng: Random source.
    :param previous: UUIDs of earlier, linkable records.
    :returns: Extra frontmatter fields (empty when none apply).
    """
    if not previous or rng.random() >= LINK_RATIO:
        return {}
    target = str(rng.choice(previous))
    if rng.random() < 0.5:
        return {"updates": [target]}
    if rng.random() < LEGACY_DEPRECATES_RATIO:
        return {"deprecates": target}
    return {"obsoletes": [target]}


def _inject_issue(rng: random.Random, fields: dict[str, object]) -> None:
    """
    Mutate *fields* in place with one deliberate validation issue.

    :param rng: Random source.
    :param fields: Frontmatter fields (already populated).
    """
    choice = rng.choice(("missing_uuid", "bad_date", "unknown_field"))
    if choice == "missing_uuid":
        del fields["uuid"]
    elif choice == "bad_date":
        fields["decision-date"] = "not-a-date"
    else:
        fields["owner"] = "team-unknown"


def _document_fields(
    rng: random.Random,
    *,
    adr_uuid: uuid.UUID,
    decision_date: datetime.date,
    title: str,
    previous: Sequence[uuid.UUID],
) -> dict[str, object]:
    """
    Build the full frontmatter mapping of one record.

    :param rng: Random source.
    :param adr_uuid: The record's UUID.
    :param decision_date: The record's decision date.
    :param title: The record's title.
    :param previous: UUIDs of earlier, linkable records.
    :returns: The frontmatter fields, possibly with a deliberate issue.
    """
    fields: dict[str, object] = {
        "uuid": str(adr_uuid),
        "title": title,
        "decision-date": decision_date.isoformat(),
    }
    fields.update(_link_fields(rng, previous))
    if rng.random() < LEGACY_SIGNOFF_RATIO:
        fields["signed-off-by"] = text.signoff_emails(rng)
    if rng.random() < ISSUE_RATIO:
        _inject_issue(rng, fields)
    return fields


def _published_document(
    rng: random.Random,
    *,
    index: int,
    project: str,
    path_prefix: str,
    previous: list[uuid.UUID],
    bodies: Mapping[uuid.UUID, str],
    today: datetime.date,
) -> tuple[GeneratedPublished, str | None]:
    """
    Generate one published document and its filename.

    A share of calls instead generate an erratum against an earlier
    decision drawn from *bodies* (never against another erratum, since
    those have no comparable body to quote from).

    :param rng: Random source.
    :param index: Global record index (guarantees a unique filename).
    :param project: Owning project path.
    :param path_prefix: ADR directory inside the project.
    :param previous: UUIDs of earlier, linkable records (any kind).
    :param bodies: Rendered bodies of earlier *decisions* only, keyed by
        UUID; erratum targets are drawn from here.
    :param today: Anchor date for decision/report dates.
    :returns: The generated document, and its decision body for later
        erratum quoting (``None`` for an erratum document).
    """
    if bodies and rng.random() < ERRATUM_RATIO:
        target = rng.choice(tuple(bodies))
        path, content, adr_uuid = build_erratum_document(
            rng,
            index=index,
            path_prefix=path_prefix,
            target=target,
            target_body=bodies[target],
            today=today,
        )
        doc = GeneratedPublished(
            project=project, path=path, content=content, adr_uuid=adr_uuid
        )
        return doc, None
    adr_uuid = uuid.UUID(int=rng.getrandbits(128))
    decision_date = text.decision_date(rng, today)
    title = text.title(rng)
    fields = _document_fields(
        rng,
        adr_uuid=adr_uuid,
        decision_date=decision_date,
        title=title,
        previous=previous,
    )
    body = text.body(rng)
    content = text.render_document(fields, body)
    slug = text.slug(title)
    filename = f"{decision_date.isoformat()}-{slug}-{index:05d}.md"
    kept_uuid = adr_uuid if "uuid" in fields else None
    doc = GeneratedPublished(
        project=project,
        path=f"{path_prefix}/{filename}",
        content=content,
        adr_uuid=kept_uuid,
    )
    return doc, body


def generate_published(
    *,
    records: int,
    projects: int,
    seed: int,
    path_prefix: str = "doc/decisions",
    today: datetime.date | None = None,
) -> list[GeneratedPublished]:
    """
    Generate a deterministic synthetic corpus of published documents.

    Records are spread round-robin over *projects* projects. A record
    may link to any earlier record in the sequence (catalog-wide, not
    only within its own project), matching how relationships resolve
    at read time.

    :param records: Number of documents to generate.
    :param projects: Number of projects to spread them across.
    :param seed: Random seed; same inputs always yield the same
        documents.
    :param path_prefix: ADR directory inside each project.
    :param today: Anchor date for decision dates (default: today).
    :returns: The generated documents, in generation order.
    """
    rng = random.Random(f"{seed}:published")
    anchor = today or datetime.date.today()
    project_names = [f"proj-{i:03d}" for i in range(max(projects, 1))]
    previous: list[uuid.UUID] = []
    bodies: dict[uuid.UUID, str] = {}
    result: list[GeneratedPublished] = []
    for index in range(records):
        project = project_names[index % len(project_names)]
        doc, body = _published_document(
            rng,
            index=index,
            project=project,
            path_prefix=path_prefix,
            previous=previous,
            bodies=bodies,
            today=anchor,
        )
        if doc.adr_uuid is not None:
            previous.append(doc.adr_uuid)
            if body is not None:
                bodies[doc.adr_uuid] = body
        result.append(doc)
    return result


def generate_candidates(
    published: Sequence[GeneratedPublished], *, ratio: float, seed: int
) -> list[GeneratedCandidate]:
    """
    Generate a competing candidate for a share of published identities.

    :param published: Published documents (see
        :func:`generate_published`).
    :param ratio: Share of identities (with a valid UUID) to cover.
    :param seed: Random seed.
    :returns: The generated candidates.
    """
    rng = random.Random(f"{seed}:candidates")
    eligible = [doc for doc in published if doc.adr_uuid is not None]
    rng.shuffle(eligible)
    count = round(len(eligible) * ratio)
    result: list[GeneratedCandidate] = []
    for doc in eligible[:count]:
        assert doc.adr_uuid is not None  # narrowed by the filter above
        extra = text.sentence(rng, text.DECISION_SENTENCES)
        content = doc.content + f"\n\n{extra}".encode()
        ref = f"feature/{text.slug(extra)[:24]}-{doc.adr_uuid.hex[:8]}"
        result.append(
            GeneratedCandidate(
                project=doc.project,
                path=doc.path,
                ref=ref,
                content=content,
                adr_uuid=doc.adr_uuid,
            )
        )
    return result


def generate_decisions(
    published: Sequence[GeneratedPublished], *, ratio: float, seed: int
) -> list[GeneratedDecision]:
    """
    Generate an accept/reject decision for a share of published identities.

    The digest matches the published content's digest exactly, so the
    decision binds to the row the seeding ingest writes.

    :param published: Published documents (see
        :func:`generate_published`).
    :param ratio: Share of identities (with a valid UUID) to decide.
    :param seed: Random seed.
    :returns: The generated decisions.
    """
    rng = random.Random(f"{seed}:decisions")
    eligible = [doc for doc in published if doc.adr_uuid is not None]
    rng.shuffle(eligible)
    count = round(len(eligible) * ratio)
    result: list[GeneratedDecision] = []
    for doc in eligible[:count]:
        assert doc.adr_uuid is not None  # narrowed by the filter above
        action = (
            DecisionAction.ACCEPTED
            if rng.random() < _ACCEPT_SHARE
            else DecisionAction.REJECTED
        )
        result.append(
            GeneratedDecision(
                project=doc.project,
                adr_uuid=doc.adr_uuid,
                digest=str(content_digest(doc.content)),
                action=action,
            )
        )
    return result
