import pytest
from dimoo_run.deployments.service import DeploymentRecord, InMemoryDeploymentStore
from dimoo_run.domain.enums import DeploymentDesiredStatus
from dimoo_run.gateway.ingress_routes import IngressRouteConfig, IngressRoutePolicyError
from dimoo_run.gateway.published_surfaces import (
    PublishedSurfaceConfig,
    PublishedSurfacePolicyError,
    PublishedSurfaceRegistry,
)


def test_published_surface_requires_active_deployment() -> None:
    deployments = InMemoryDeploymentStore()
    deployments.add(
        DeploymentRecord(
            id="deployment_1",
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="version_1",
            environment="prod",
            desired_status=DeploymentDesiredStatus.paused,
        )
    )
    registry = PublishedSurfaceRegistry(deployments=deployments)

    with pytest.raises(PublishedSurfacePolicyError):
        registry.publish(
            PublishedSurfaceConfig(
                id="surface_1",
                tenant_id="tenant_1",
                project_id="project_1",
                deployment_id="deployment_1",
                type="api",
            )
        )


def test_published_surface_requires_same_tenant_and_project_as_deployment() -> None:
    deployments = InMemoryDeploymentStore()
    deployments.add(
        DeploymentRecord(
            id="deployment_1",
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="version_1",
            environment="prod",
            desired_status=DeploymentDesiredStatus.active,
        )
    )
    registry = PublishedSurfaceRegistry(deployments=deployments)

    with pytest.raises(PublishedSurfacePolicyError):
        registry.publish(
            PublishedSurfaceConfig(
                id="surface_1",
                tenant_id="tenant_2",
                project_id="project_1",
                deployment_id="deployment_1",
                type="api",
            )
        )


def test_published_surface_rejects_unknown_type() -> None:
    deployments = InMemoryDeploymentStore()
    deployments.add(
        DeploymentRecord(
            id="deployment_1",
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="agent_1",
            agent_version_id="version_1",
            environment="prod",
            desired_status=DeploymentDesiredStatus.active,
        )
    )
    registry = PublishedSurfaceRegistry(deployments=deployments)

    with pytest.raises(PublishedSurfacePolicyError):
        registry.publish(
            PublishedSurfaceConfig(
                id="surface_1",
                tenant_id="tenant_1",
                project_id="project_1",
                deployment_id="deployment_1",
                type="unknown",
            )
        )


def test_public_ingress_route_requires_rate_limit_and_audit() -> None:
    with pytest.raises(IngressRoutePolicyError):
        IngressRouteConfig(
            id="route_1",
            surface_id="surface_1",
            path="/agents/support",
            auth_mode="public",
            rate_limit_policy_id=None,
            access_log_enabled=True,
        ).validate()

    route = IngressRouteConfig(
        id="route_1",
        surface_id="surface_1",
        path="/agents/support",
        auth_mode="public",
        rate_limit_policy_id="rate_limit_1",
        access_log_enabled=True,
    ).validate()

    assert route.path == "/agents/support"


def test_ingress_route_rejects_unknown_auth_mode_and_invalid_path() -> None:
    with pytest.raises(IngressRoutePolicyError):
        IngressRouteConfig(
            id="route_1",
            surface_id="surface_1",
            path="/agents/support",
            auth_mode="none",
        ).validate()

    with pytest.raises(IngressRoutePolicyError):
        IngressRouteConfig(
            id="route_1",
            surface_id="surface_1",
            path="agents/support",
            auth_mode="api_key",
        ).validate()
