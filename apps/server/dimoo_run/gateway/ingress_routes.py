from dataclasses import dataclass


class IngressRoutePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class IngressRouteConfig:
    id: int
    surface_id: int
    path: str
    auth_mode: str
    custom_domain: str | None = None
    cors_policy_id: str | None = None
    rate_limit_policy_id: str | None = None
    request_transform_ref: str | None = None
    response_transform_ref: str | None = None
    access_log_enabled: bool = True

    def validate(self) -> "IngressRouteConfig":
        if self.auth_mode not in {"api_key", "jwt", "public", "internal"}:
            raise IngressRoutePolicyError("unsupported auth_mode")
        if not self.path.startswith("/"):
            raise IngressRoutePolicyError("path must start with /")
        if self.auth_mode == "public" and not self.rate_limit_policy_id:
            raise IngressRoutePolicyError("public auth_mode requires a rate_limit_policy_id")
        if self.auth_mode == "public" and not self.access_log_enabled:
            raise IngressRoutePolicyError("public auth_mode requires access logs")
        return self
