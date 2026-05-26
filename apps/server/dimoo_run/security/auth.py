RESOURCE_ACTIONS: frozenset[str] = frozenset(
    {
        "agent:read",
        "agent:create",
        "agent:update",
        "agent:delete",
        "agent:deploy",
        "agent:invoke",
        "run:read",
        "run:cancel",
        "run:retry",
        "run:read_input",
        "run:read_output",
        "trace:read",
        "trace:read_prompt",
        "trace:read_tool_args",
        "trace:export",
        "task:read",
        "tool:read",
        "tool:call",
        "tool:approve",
        "secret:read",
        "secret:create",
        "secret:update",
        "secret:delete",
        "policy:read",
        "policy:create",
        "policy:update",
        "policy:delete",
        "artifact:read",
        "artifact:create",
        "artifact:delete",
        "dataset:read",
        "dataset:create",
        "dataset:update",
        "dataset:delete",
        "experiment:read",
        "experiment:create",
        "experiment:run",
        "schedule:read",
        "schedule:create",
        "schedule:update",
        "schedule:delete",
        "batch:read",
        "batch:create",
        "replay:create",
        "memory:read",
        "memory:create",
        "memory:update",
        "memory:delete",
        "catalog:read",
        "catalog:create",
        "catalog:update",
        "catalog:delete",
        "prompt:read",
        "prompt:create",
        "prompt:update",
        "prompt:delete",
        "model_gateway:read",
        "model_gateway:create",
        "model_gateway:update",
        "model_gateway:delete",
        "model_gateway:use",
        "published_surface:read",
        "published_surface:create",
        "published_surface:update",
        "published_surface:delete",
        "extension:read",
        "extension:create",
        "extension:update",
        "extension:delete",
        "alert:read",
        "alert:create",
        "alert:update",
        "alert:delete",
        "backup:read",
        "backup:create",
        "backup:restore",
        "audit:read",
        "user:manage",
        "service_account:manage",
        "role:manage",
    }
)

READ_ONLY_PERMISSIONS: frozenset[str] = frozenset(
    permission for permission in RESOURCE_ACTIONS if permission.endswith(":read")
)


class RBACPolicy:
    def __init__(self) -> None:
        self.role_permissions: dict[str, frozenset[str]] = {
            "owner": RESOURCE_ACTIONS,
            "admin": frozenset(
                permission
                for permission in RESOURCE_ACTIONS
                if permission.startswith(("agent:", "published_surface:"))
                or permission in {"user:manage", "role:manage", "service_account:manage"}
            ),
            "developer": frozenset(
                {
                    "agent:read",
                    "agent:create",
                    "agent:update",
                    "agent:deploy",
                    "run:read",
                    "run:read_input",
                    "run:read_output",
                    "task:read",
                    "trace:read",
                    "catalog:read",
                    "prompt:read",
                    "prompt:create",
                    "prompt:update",
                }
            ),
            "operator": frozenset(
                {
                    "agent:read",
                    "run:read",
                    "run:cancel",
                    "run:retry",
                    "task:read",
                    "trace:read",
                    "published_surface:read",
                }
            ),
            "auditor": frozenset({"audit:read", "run:read", "trace:read", "task:read"}),
            "viewer": READ_ONLY_PERMISSIONS,
            "enduser": frozenset({"agent:invoke", "run:read"}),
        }

    def permissions_for(self, role: str) -> frozenset[str]:
        return self.role_permissions.get(role.lower(), frozenset())

    def has_permission(self, *, role: str, permission: str) -> bool:
        return permission in self.permissions_for(role)
