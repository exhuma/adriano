"""
Word lists and text rendering for the synthetic benchmark ADR corpus.

Pure, no I/O: title/body/slug text pieces built from fixed word lists
and sentence templates over an injected :class:`random.Random`, used
by :mod:`app.services.seed_synthetic_gen`. Split out to keep that
module under the project's module-size limit.

Public API: :data:`VOCABULARY`, :data:`CONTEXT_SENTENCES`,
:data:`DECISION_SENTENCES`, :data:`CONSEQUENCE_SENTENCES`,
:func:`sentence`, :func:`body`, :func:`title`, :func:`slug`,
:func:`decision_date`, :func:`signoff_emails`, :func:`reporter_email`,
:func:`render_document`.
"""

import datetime
import random
import re
from collections.abc import Sequence

import yaml

__all__ = [
    "CONSEQUENCE_SENTENCES",
    "CONTEXT_SENTENCES",
    "DECISION_SENTENCES",
    "QUALIFIERS",
    "VERBS",
    "VOCABULARY",
    "body",
    "decision_date",
    "render_document",
    "reporter_email",
    "signoff_emails",
    "slug",
    "sentence",
    "title",
]

_MIN_BODY_CHARS = 300
_MAX_BODY_CHARS = 3000

VERBS = (
    "Use",
    "Adopt",
    "Migrate to",
    "Replace",
    "Introduce",
    "Deprecate",
    "Standardize on",
    "Evaluate",
    "Retire",
    "Consolidate",
    "Switch to",
    "Extend",
    "Harden",
    "Automate",
)

#: Also used as the benchmark's free-text search vocabulary.
VOCABULARY = (
    "PostgreSQL",
    "Redis",
    "Kafka",
    "GraphQL",
    "gRPC",
    "Kubernetes",
    "Terraform",
    "feature flags",
    "circuit breakers",
    "event sourcing",
    "the monolith",
    "microservices",
    "OAuth2",
    "rate limiting",
    "blue-green deployments",
    "canary releases",
    "the message queue",
    "distributed tracing",
    "the API gateway",
    "multi-tenancy",
    "connection pooling",
    "read replicas",
    "the cache layer",
    "structured logging",
    "feature toggles",
    "the job scheduler",
    "idempotency keys",
    "the retry policy",
    "schema migrations",
    "the search index",
)

QUALIFIERS = (
    "for the payments pipeline",
    "in the platform service",
    "for search indexing",
    "for background jobs",
    "for the admin console",
    "for observability",
    "for the billing system",
    "for the notification service",
    "across all services",
    "for the checkout flow",
    "for the reporting pipeline",
    "",
)

CONTEXT_SENTENCES = (
    "The current approach does not scale past {n} requests per second.",
    "Operators reported repeated incidents during peak traffic.",
    "The team evaluated {count} alternatives before this proposal.",
    "Maintenance cost has grown with every new integration.",
    "Latency under load regularly exceeded the agreed budget.",
    "The existing solution is difficult to test in isolation.",
)
DECISION_SENTENCES = (
    "We will adopt this approach for all new services.",
    "Existing services migrate incrementally over the next quarter.",
    "A rollback plan is documented in the operations runbook.",
    "The change is gated behind a feature flag during rollout.",
    "We chose this option for its operational simplicity.",
    "The decision was reached after a cross-team review.",
)
CONSEQUENCE_SENTENCES = (
    "This increases operational complexity in the short term.",
    "Existing dashboards must be updated to reflect the change.",
    "On-call runbooks need a new section for this component.",
    "Some teams will need training before the next release.",
    "Future proposals should revisit this decision annually.",
    "No immediate action is required from downstream consumers.",
)

_LEGACY_DOMAINS = ("example.com", "example.org", "example.net")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def sentence(rng: random.Random, pool: Sequence[str]) -> str:
    """
    Render one random sentence template.

    :param rng: Random source.
    :param pool: Candidate templates.
    :returns: The filled-in sentence.
    """
    template = rng.choice(pool)
    return template.format(
        n=rng.randrange(100, 5000), count=rng.randrange(2, 7)
    )


def _section(rng: random.Random, heading: str, pool: Sequence[str]) -> str:
    """
    Render one Markdown section of 2-4 random sentences.

    :param rng: Random source.
    :param heading: Section heading text.
    :param pool: Candidate sentence templates.
    :returns: The rendered section, including its heading.
    """
    sentences = " ".join(
        sentence(rng, pool) for _ in range(rng.randrange(2, 5))
    )
    return f"## {heading}\n\n{sentences}\n"


def body(rng: random.Random) -> str:
    """
    Build a realistic ADR body, 300-3000 characters.

    :param rng: Random source.
    :returns: The Markdown body (without frontmatter).
    """
    sections = (
        _section(rng, "Context", CONTEXT_SENTENCES),
        _section(rng, "Decision", DECISION_SENTENCES),
        _section(rng, "Consequences", CONSEQUENCE_SENTENCES),
    )
    text = "\n".join(sections)
    filler = CONTEXT_SENTENCES + DECISION_SENTENCES + CONSEQUENCE_SENTENCES
    while len(text) < _MIN_BODY_CHARS:
        text += " " + sentence(rng, filler)
    if len(text) > _MAX_BODY_CHARS:
        text = text[:_MAX_BODY_CHARS].rsplit(". ", 1)[0] + "."
    return text


def title(rng: random.Random) -> str:
    """
    Build a realistic ADR title from the word lists.

    :param rng: Random source.
    :returns: The title.
    """
    parts = (rng.choice(VERBS), rng.choice(VOCABULARY), rng.choice(QUALIFIERS))
    return " ".join(part for part in parts if part)


def slug(text: str) -> str:
    """
    Turn a title or sentence into a filename/ref-safe slug.

    :param text: The text.
    :returns: A lowercase, hyphenated slug, at most 60 characters.
    """
    cleaned = _SLUG_RE.sub("-", text.lower()).strip("-")
    return cleaned[:60] or "adr"


def decision_date(rng: random.Random, today: datetime.date) -> datetime.date:
    """
    Pick a decision date within the last ~6 years of *today*.

    :param rng: Random source.
    :param today: Anchor date.
    :returns: The date.
    """
    return today - datetime.timedelta(days=rng.randrange(0, 2200))


def signoff_emails(rng: random.Random) -> list[str]:
    """
    Build 1-2 fake legacy sign-off addresses.

    :param rng: Random source.
    :returns: The addresses.
    """
    count = rng.randrange(1, 3)
    return [
        f"reviewer{rng.randrange(1, 999)}@{rng.choice(_LEGACY_DOMAINS)}"
        for _ in range(count)
    ]


def reporter_email(rng: random.Random) -> str:
    """
    Build one fake erratum ``reported-by`` address.

    :param rng: Random source.
    :returns: The address.
    """
    return f"reporter{rng.randrange(1, 999)}@{rng.choice(_LEGACY_DOMAINS)}"


def render_document(fields: dict[str, object], body_text: str) -> bytes:
    """
    Render frontmatter and body to the raw document bytes.

    Shared by decision and erratum generation
    (:mod:`app.services.seed_synthetic_gen` and
    :mod:`app.services.seed_synthetic_errata`).

    :param fields: Frontmatter fields.
    :param body_text: Markdown body.
    :returns: The encoded document.
    """
    front = yaml.safe_dump(fields, sort_keys=False, default_flow_style=False)
    return f"---\n{front}---\n{body_text}".encode()
