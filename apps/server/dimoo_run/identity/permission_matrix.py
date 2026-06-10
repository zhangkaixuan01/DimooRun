from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.domain.models import (
    ConsoleOperator,
    ConsoleOperatorPermission,
    ConsoleOperatorRole,
    ConsolePermission,
    ConsoleRole,
    ConsoleRolePermission,
)


@dataclass(frozen=True)
class PermissionChange:
    added: list[str]
    removed: list[str]
    unchanged: list[str]


@dataclass(frozen=True)
class RoleImpactRecord:
    operator_id: int
    email: str
    name: str
    current_permissions: list[str]
    preview_permissions: list[str]


@dataclass(frozen=True)
class RoleMatrixPreview:
    role_id: int
    role_name: str
    current_permissions: list[str]
    preview_permissions: list[str]
    change: PermissionChange
    affected_operators: list[RoleImpactRecord]
    affected_service_accounts: list[dict[str, object]]
    warnings: list[dict[str, object]]


def role_matrix_preview(
    session: Session,
    *,
    role_id: int,
    permission_codes: Iterable[str],
    current_operator_id: int | None = None,
) -> RoleMatrixPreview:
    role = session.get(ConsoleRole, role_id)
    if role is None or role.is_deleted:
        raise KeyError(role_id)
    current_permissions = _role_permission_codes(session, role_id)
    preview_permissions = sorted(set(permission_codes))
    change = PermissionChange(
        added=sorted(set(preview_permissions) - set(current_permissions)),
        removed=sorted(set(current_permissions) - set(preview_permissions)),
        unchanged=sorted(set(current_permissions) & set(preview_permissions)),
    )
    operator_rows = list(
        session.execute(
            select(ConsoleOperator.id, ConsoleOperator.email, ConsoleOperator.name)
            .join(ConsoleOperatorRole, ConsoleOperatorRole.operator_id == ConsoleOperator.id)
            .where(
                ConsoleOperatorRole.role_id == role_id,
                ConsoleOperatorRole.is_deleted.is_(False),
                ConsoleOperator.is_deleted.is_(False),
            )
            .order_by(ConsoleOperator.email)
        )
    )
    affected_operators: list[RoleImpactRecord] = []
    warnings: list[dict[str, object]] = []
    for operator_id, email, name in operator_rows:
        current_effective = _operator_effective_permissions(session, operator_id)
        preview_effective = _operator_effective_permissions(
            session,
            operator_id,
            role_permission_overrides={role_id: set(preview_permissions)},
        )
        affected_operators.append(
            RoleImpactRecord(
                operator_id=operator_id,
                email=email,
                name=name,
                current_permissions=current_effective,
                preview_permissions=preview_effective,
            )
        )
        if current_operator_id is not None and operator_id == current_operator_id:
            required = {"admin:read", "identity:role:write"}
            if not required.issubset(preview_effective):
                warnings.append(
                    {
                        "code": "self_lockout_risk",
                        "message": (
                            "Preview removes permissions required to continue role governance "
                            "for the current operator."
                        ),
                        "required_permissions": sorted(required),
                        "missing_permissions": sorted(required - set(preview_effective)),
                    }
                )
    if "*" in current_permissions and "*" not in preview_permissions:
        warnings.append(
            {
                "code": "wildcard_removed",
                "message": "Preview removes wildcard access from the selected role.",
                "required_review": True,
            }
        )
    return RoleMatrixPreview(
        role_id=role.id,
        role_name=role.name,
        current_permissions=current_permissions,
        preview_permissions=preview_permissions,
        change=change,
        affected_operators=affected_operators,
        affected_service_accounts=[],
        warnings=warnings,
    )


def _role_permission_codes(session: Session, role_id: int) -> list[str]:
    return sorted(
        session.scalars(
            select(ConsolePermission.code)
            .join(
                ConsoleRolePermission,
                ConsoleRolePermission.permission_id == ConsolePermission.id,
            )
            .where(
                ConsoleRolePermission.role_id == role_id,
                ConsoleRolePermission.is_deleted.is_(False),
                ConsolePermission.is_deleted.is_(False),
            )
        )
    )


def _operator_effective_permissions(
    session: Session,
    operator_id: int,
    *,
    role_permission_overrides: dict[int, set[str]] | None = None,
) -> list[str]:
    direct = set(
        session.scalars(
            select(ConsolePermission.code)
            .join(
                ConsoleOperatorPermission,
                ConsoleOperatorPermission.permission_id == ConsolePermission.id,
            )
            .where(
                ConsoleOperatorPermission.operator_id == operator_id,
                ConsoleOperatorPermission.is_deleted.is_(False),
                ConsolePermission.is_deleted.is_(False),
                ConsolePermission.status == "active",
            )
        )
    )
    role_ids = list(
        session.scalars(
            select(ConsoleOperatorRole.role_id).where(
                ConsoleOperatorRole.operator_id == operator_id,
                ConsoleOperatorRole.is_deleted.is_(False),
            )
        )
    )
    via_roles: set[str] = set()
    for role_id in role_ids:
        if role_permission_overrides and role_id in role_permission_overrides:
            via_roles.update(role_permission_overrides[role_id])
            continue
        via_roles.update(_role_permission_codes(session, role_id))
    return sorted(direct | via_roles)
