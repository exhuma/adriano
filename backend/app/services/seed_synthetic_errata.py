"""
Synthetic erratum generation for the benchmark ADR corpus.

Split out of :mod:`app.services.seed_synthetic_gen` to keep that module
under the project's module-size limit. :func:`build_erratum_document`
is the only entry point that module calls; everything else here is a
private helper over an injected :class:`random.Random`, so a fixed
seed reproduces the exact same erratum (see
:mod:`app.services.seed_synthetic_gen` for the full determinism
contract -- this module makes no calls of its own to
:class:`random.Random` outside the one it is given).

An erratum is a small RFC-style report against an earlier decision --
never a full ADR body (see :mod:`app.domain.errata`): a ``type``
(mostly technical, some editorial), a ``section`` taken from the
target's own headings, a sentence quoted from that section as
"Original text", a "Corrected text" and sometimes "Notes".

Public API: :func:`build_erratum_document`.
"""

import datetime
import random
import re
import uuid

from app.services import seed_synthetic_text as text

__all__ = ["build_erratum_document"]

#: Chance an erratum's ``type`` is "technical" rather than "editorial".
_TECHNICAL_RATIO = 0.8
#: Chance an erratum carries an optional ``reported-by`` address.
_REPORTED_BY_RATIO = 0.6
#: Chance an erratum carries an optional ``## Notes`` section.
_NOTES_RATIO = 0.4
#: Plausible RFC-style clauses explaining an erratum's correction.
_CORRECTION_CLAUSES = (
    "clarified to remove ambiguity",
    "updated to match the agreed scope",
    "corrected for consistency with the rest of the record",
    "reworded after reviewer feedback",
    "narrowed to the cases actually covered",
)
#: Matches a decision body's ATX H2 section headings.
_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def _target_sections(body: str) -> dict[str, str]:
    """
    Split a decision body into its heading -> section-text mapping.

    :param body: Rendered "Context" / "Decision" / "Consequences" body.
    :returns: Each heading's trimmed content; empty if none matched.
    """
    parts = _HEADING_RE.split(body)
    return {
        parts[i].strip(): parts[i + 1].strip()
        for i in range(1, len(parts), 2)
        if i + 1 < len(parts)
    }


def _quote_sentence(rng: random.Random, body: str) -> tuple[str, str]:
    """
    Pick a section heading and a sentence plausibly quoted from it.

    :param rng: Random source.
    :param body: The target decision's rendered Markdown body.
    :returns: The heading (``"Decision"`` as a fallback) and a sentence
        taken from its content.
    """
    sections = _target_sections(body)
    if not sections:
        return "Decision", text.sentence(rng, text.DECISION_SENTENCES)
    heading = rng.choice(list(sections))
    sentences = [s.strip() for s in sections[heading].split(". ") if s.strip()]
    if not sentences:
        return heading, text.sentence(rng, text.DECISION_SENTENCES)
    sentence = rng.choice(sentences)
    if not sentence.endswith((".", "!", "?")):
        sentence += "."
    return heading, sentence


def _erratum_correction(rng: random.Random, original: str) -> str:
    """
    Build a corrected-text sentence, distinct from the quoted original.

    :param rng: Random source.
    :param original: The quoted original sentence.
    :returns: The corrected sentence.
    """
    clause = rng.choice(_CORRECTION_CLAUSES)
    return f"{original.rstrip('.')}, {clause}."


def _erratum_fields(
    rng: random.Random,
    *,
    adr_uuid: uuid.UUID,
    target: uuid.UUID,
    section: str,
    reported_date: datetime.date,
) -> dict[str, object]:
    """
    Build the frontmatter fields of one synthetic erratum.

    :param rng: Random source.
    :param adr_uuid: The erratum's own identity.
    :param target: UUID of the decision it corrects.
    :param section: Section of the target it addresses.
    :param reported_date: The report ``date``.
    :returns: The frontmatter fields.
    """
    fields: dict[str, object] = {
        "uuid": str(adr_uuid),
        "erratum-for": str(target),
        "type": (
            "technical" if rng.random() < _TECHNICAL_RATIO else "editorial"
        ),
        "section": section,
        "date": reported_date.isoformat(),
    }
    if rng.random() < _REPORTED_BY_RATIO:
        fields["reported-by"] = text.reporter_email(rng)
    return fields


def build_erratum_document(
    rng: random.Random,
    *,
    index: int,
    path_prefix: str,
    target: uuid.UUID,
    target_body: str,
    today: datetime.date,
) -> tuple[str, bytes, uuid.UUID]:
    """
    Build one synthetic erratum reporting against an earlier decision.

    The body is a small RFC-style report (``## Original text``,
    ``## Corrected text`` and sometimes ``## Notes``), never a full ADR
    body; see :mod:`app.domain.errata`.

    :param rng: Random source.
    :param index: Global record index (guarantees a unique filename).
    :param path_prefix: ADR directory inside the project.
    :param target: UUID of the decision this erratum corrects.
    :param target_body: The target's rendered Markdown body, quoted from.
    :param today: Anchor date for the report date.
    :returns: The document's path (inside the project), its rendered
        content, and the erratum's own UUID.
    """
    adr_uuid = uuid.UUID(int=rng.getrandbits(128))
    heading, original = _quote_sentence(rng, target_body)
    corrected = _erratum_correction(rng, original)
    report_date = text.decision_date(rng, today)
    fields = _erratum_fields(
        rng,
        adr_uuid=adr_uuid,
        target=target,
        section=heading,
        reported_date=report_date,
    )
    sections = [
        f"## Original text\n\n{original}",
        f"## Corrected text\n\n{corrected}",
    ]
    if rng.random() < _NOTES_RATIO:
        notes = text.sentence(rng, text.CONSEQUENCE_SENTENCES)
        sections.append(f"## Notes\n\n{notes}")
    body = "\n\n".join(sections)
    content = text.render_document(fields, body)
    slug = text.slug(f"erratum {heading}")
    filename = f"{report_date.isoformat()}-{slug}-{index:05d}.md"
    return f"{path_prefix}/errata/{filename}", content, adr_uuid
