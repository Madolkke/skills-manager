from __future__ import annotations

Role = str
Permission = str

VALID_ROLES: set[Role] = {"admin", "owner", "maintainer", "evaluator", "reviewer", "viewer"}

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    "admin": {
        "role.manage",
        "skill.delete",
        "skill.edit",
        "skill.version.create",
        "eval.manage",
        "eval.run",
        "tag.protected.manage",
        "verification.accept",
        "saved_view.manage",
        "review.manage",
        "review.respond",
        "publish.request",
    },
    "owner": {"role.manage", "skill.delete", "skill.edit", "skill.version.create", "eval.manage", "eval.run", "verification.accept", "saved_view.manage", "review.manage", "publish.request"},
    "maintainer": {"skill.edit", "skill.version.create", "eval.manage", "eval.run", "verification.accept", "saved_view.manage", "review.manage", "publish.request"},
    "evaluator": {"eval.run"},
    "reviewer": {"review.respond"},
    "viewer": set(),
}

PERMISSION_LABELS: dict[Permission, str] = {
    "role.manage": "owner or admin",
    "skill.delete": "owner or admin",
    "skill.edit": "maintainer, owner, or admin",
    "skill.version.create": "maintainer, owner, or admin",
    "eval.manage": "maintainer, owner, or admin",
    "eval.run": "evaluator, maintainer, owner, or admin",
    "tag.protected.manage": "admin",
    "verification.accept": "maintainer, owner, or admin",
    "saved_view.manage": "maintainer, owner, or admin",
    "review.manage": "maintainer, owner, or admin",
    "review.respond": "reviewer",
    "publish.request": "maintainer, owner, or admin",
}


def role_allows(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def permission_label(permission: Permission) -> str:
    return PERMISSION_LABELS.get(permission, "authorized role")
