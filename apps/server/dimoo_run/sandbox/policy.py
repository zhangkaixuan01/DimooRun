from dataclasses import dataclass, field


class SandboxPolicyViolation(PermissionError):
    error_code = "security_policy_violation"


@dataclass(frozen=True)
class SandboxPolicy:
    isolation_level: str
    network_policy: str
    filesystem_policy: str
    allowed_env: set[str] = field(default_factory=set)
    allowed_secret_refs: set[str] = field(default_factory=set)
    allowed_gateway_refs: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.isolation_level not in {"L0", "L1", "L2", "L3", "L4"}:
            raise SandboxPolicyViolation("unsupported isolation level")

    def validate_env(self, env: dict[str, str]) -> None:
        blocked = set(env) - self.allowed_env
        if blocked:
            raise SandboxPolicyViolation(f"env keys are not allowed: {sorted(blocked)}")

    def validate_secret_ref(self, secret_ref: str) -> None:
        if secret_ref not in self.allowed_secret_refs:
            raise SandboxPolicyViolation(f"secret ref is not allowed: {secret_ref}")

    def validate_gateway_ref(self, gateway_ref: str) -> None:
        if gateway_ref not in self.allowed_gateway_refs:
            raise SandboxPolicyViolation(f"gateway ref is not allowed: {gateway_ref}")
