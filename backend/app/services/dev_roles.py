"""
Role names of the loaded catalog, for the dev-login presets.

Used only by the dev-only ``GET /auth/dev/roles``
(:mod:`app.routers.auth_dev`, mounted only when dev auth is enabled).
It lists the ``rbac`` roles with their permissions and the role names
the approval policy accepts as reviewers -- never the reviewer users
(``issuer|subject`` pairs), which a sign-in preset cannot use anyway.

Public API: :class:`DevRole`, :class:`DevRoleCatalog`,
:func:`dev_role_catalog`.
"""

from dataclasses import dataclass

from app.catalog_config import CatalogConfig, Permission

__all__ = ["DevRole", "DevRoleCatalog", "dev_role_catalog"]


@dataclass(frozen=True, slots=True)
class DevRole:
    """
    One ``rbac`` role.

    :param name: Role name as it appears in the roles claim.
    :param permissions: Permissions it grants, sorted.
    """

    name: str
    permissions: tuple[Permission, ...]


@dataclass(frozen=True, slots=True)
class DevRoleCatalog:
    """
    The role names a dev sign-in can usefully assert.

    :param roles: ``rbac`` roles, sorted by name.
    :param reviewer_roles: Approval-policy reviewer roles, sorted.
    """

    roles: tuple[DevRole, ...]
    reviewer_roles: tuple[str, ...]


def dev_role_catalog(config: CatalogConfig | None) -> DevRoleCatalog:
    """
    Collect the role names of the loaded catalog.

    :param config: The loaded configuration, or ``None`` when the app
        lifespan did not run.
    :returns: The ``rbac`` roles and the reviewer roles; both empty
        when nothing was loaded. Reviewer roles are empty when the
        policy is missing or invalid.
    """
    if config is None:
        return DevRoleCatalog(roles=(), reviewer_roles=())
    roles = tuple(
        DevRole(name=name, permissions=tuple(sorted(permissions)))
        for name, permissions in sorted(config.rbac.roles.items())
    )
    policy = config.policy.policy
    reviewer_roles = (
        tuple(sorted(policy.reviewer_roles)) if policy is not None else ()
    )
    return DevRoleCatalog(roles=roles, reviewer_roles=reviewer_roles)
