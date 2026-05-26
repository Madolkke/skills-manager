from __future__ import annotations

Role = str
Permission = str

VALID_ROLES: set[Role] = {"owner", "maintainer", "evaluator", "viewer"}

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    "owner": {"role.manage", "verification.accept"},
    "maintainer": {"verification.accept"},
    "evaluator": set(),
    "viewer": set(),
}

PERMISSION_LABELS: dict[Permission, str] = {
    "role.manage": "owner",
    "verification.accept": "owner or maintainer",
}


def role_allows(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def permission_label(permission: Permission) -> str:
    return PERMISSION_LABELS.get(permission, "authorized role")
