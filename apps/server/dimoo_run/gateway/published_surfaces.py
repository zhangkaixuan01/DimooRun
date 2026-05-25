from dataclasses import dataclass

from dimoo_run.deployments.service import InMemoryDeploymentStore
from dimoo_run.domain.enums import DeploymentDesiredStatus


class PublishedSurfacePolicyError(ValueError):
    pass


ALLOWED_SURFACE_TYPES = {"api", "chat", "task", "stream", "mcp_server", "webhook"}


@dataclass(frozen=True)
class PublishedSurfaceConfig:
    id: str
    tenant_id: str
    project_id: str
    deployment_id: str
    type: str
    status: str = "active"


class PublishedSurfaceRegistry:
    def __init__(self, *, deployments: InMemoryDeploymentStore) -> None:
        self.deployments = deployments
        self.surfaces: dict[str, PublishedSurfaceConfig] = {}

    def publish(self, surface: PublishedSurfaceConfig) -> PublishedSurfaceConfig:
        deployment = self.deployments.get(surface.deployment_id)
        if surface.type not in ALLOWED_SURFACE_TYPES:
            raise PublishedSurfacePolicyError("unsupported PublishedSurface type")
        if deployment.desired_status != DeploymentDesiredStatus.active:
            raise PublishedSurfacePolicyError("PublishedSurface requires an active Deployment")
        if deployment.tenant_id != surface.tenant_id or deployment.project_id != surface.project_id:
            raise PublishedSurfacePolicyError(
                "PublishedSurface tenant_id and project_id must match Deployment"
            )
        self.surfaces[surface.id] = surface
        return surface
