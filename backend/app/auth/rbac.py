"""
Authorization rules: role permissions and reviewer eligibility.

Permissions (``read``, ``operate``) come from the ``rbac`` section of
``catalog.yaml`` (:class:`~app.catalog_config.RbacConfig`). A missing or
invalid ``rbac`` section grants nothing (deny by default); the loader
reports it as a configuration problem (``check-config``) and
``/healthz`` reports ``rbac: empty``.

Reviewing is **not** a permission: eligibility comes from the approval
policy (:func:`app.domain.approval.is_eligible`). Read permission never
implies review. :func:`reviewer_eligibility` phrases the result for
``GET /api/v1/me`` and for the decision endpoint (phase 07).

Public API: :class:`Permission` and :class:`RbacConfig` (re-exported
from :mod:`app.catalog_config`), :class:`ReviewerEligibility`,
:func:`permissions_for`, :func:`reviewer_eligibility`.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.catalog_config import Permission, PolicyConfig, RbacConfig
from app.domain.approval import PolicyStatus, is_eligible

__all__ = [
    "Permission",
    "RbacConfig",
    "ReviewerEligibility",
    "permissions_for",
    "reviewer_eligibility",
]


def permissions_for(
    rbac: RbacConfig | None, roles: Iterable[str]
) -> frozenset[Permission]:
    """
    Collect the permissions a caller's roles grant.

    :param rbac: The role mapping, or ``None`` when no configuration
        was loaded (grants nothing).
    :param roles: Role names from the verified token.
    :returns: The granted permissions.
    """
    if rbac is None:
        return frozenset()
    return rbac.permissions_for(roles)


@dataclass(frozen=True, slots=True)
class ReviewerEligibility:
    """
    Whether a caller may record approval decisions, and why.

    :param eligible: ``True`` if the policy lists the caller.
    :param reason: Readable explanation (no secrets).
    """

    eligible: bool
    reason: str


def reviewer_eligibility(
    policy: PolicyConfig | None,
    *,
    issuer: str,
    subject: str,
    roles: Iterable[str],
) -> ReviewerEligibility:
    """
    Evaluate reviewer eligibility under the configured approval policy.

    :param policy: The policy status, or ``None`` when no configuration
        was loaded.
    :param issuer: Caller's verified token issuer.
    :param subject: Caller's verified token subject.
    :param roles: Caller's verified roles.
    :returns: Eligibility with a reason.
    """
    if policy is None or policy.policy is None:
        status = PolicyStatus.MISSING if policy is None else policy.status
        return ReviewerEligibility(
            False,
            f"the approval policy is {status}; nobody can record decisions",
        )
    if is_eligible(policy.policy, issuer, subject, roles):
        return ReviewerEligibility(
            True, "listed as a reviewer by the approval policy"
        )
    return ReviewerEligibility(
        False,
        "not a reviewer: the approval policy lists neither this user "
        "nor any of their roles",
    )
