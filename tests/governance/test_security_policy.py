from datetime import UTC, datetime, timedelta

import pytest
from dimoo_run.identity.service_accounts import ServiceAccountRegistry
from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import (
    AuditRecord,
    InMemoryAuditSink,
    PolicyEngine,
    PolicyRequest,
    StaticPolicyRule,
)
from dimoo_run.security.api_keys import (
    APIKeyAuthenticator,
    APIKeyDisabledError,
    APIKeyScopeError,
)
from dimoo_run.security.auth import RESOURCE_ACTIONS, RBACPolicy


def test_rbac_roles_are_resource_action_based() -> None:
    rbac = RBACPolicy()

    assert "agent:deploy" in RESOURCE_ACTIONS
    assert "model_gateway:create" in RESOURCE_ACTIONS
    assert rbac.has_permission(role="owner", permission="secret:delete")
    assert rbac.has_permission(role="viewer", permission="agent:read")
    assert not rbac.has_permission(role="viewer", permission="agent:create")
    assert not rbac.has_permission(role="enduser", permission="audit:read")


def test_api_key_authentication_enforces_scope_project_status_and_last_used() -> None:
    now = datetime(2026, 5, 26, tzinfo=UTC)
    audit_sink = InMemoryAuditSink()
    registry = ServiceAccountRegistry(now=lambda: now)
    service_account = registry.create(
        tenant_id="tenant_1",
        project_id="project_1",
        name="runtime",
        permissions={"agent:invoke", "run:read"},
        created_by="admin_1",
    )
    authenticator = APIKeyAuthenticator(
        service_accounts=registry,
        audit_sink=audit_sink,
        now=lambda: now,
    )

    plain_key, api_key = authenticator.create_key(
        tenant_id="tenant_1",
        project_id="project_1",
        name="runtime-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes={"agent:invoke"},
        created_by="admin_1",
        expires_at=now + timedelta(days=1),
    )
    actor = authenticator.authenticate(
        plain_key,
        tenant_id="tenant_1",
        project_id="project_1",
        required_scope="agent:invoke",
    )

    assert actor.actor_type == "service_account"
    assert actor.actor_id == service_account.id
    assert authenticator.keys[api_key.id].last_used_at == now
    assert audit_sink.records[0].actor_type == "service_account"
    assert audit_sink.records[0].result == "allow"
    assert audit_sink.records[0].action == "authenticate"

    with pytest.raises(APIKeyScopeError):
        authenticator.create_key(
            tenant_id="tenant_1",
            project_id="project_1",
            name="too-wide",
            owner_type="service_account",
            owner_id=service_account.id,
            scopes={"secret:read"},
            created_by="admin_1",
        )
    with pytest.raises(APIKeyScopeError):
        authenticator.authenticate(
            plain_key,
            tenant_id="tenant_1",
            project_id="project_2",
            required_scope="agent:invoke",
        )

    authenticator.disable_key(api_key.id, actor_id="admin_1")
    with pytest.raises(APIKeyDisabledError):
        authenticator.authenticate(
            plain_key,
            tenant_id="tenant_1",
            project_id="project_1",
            required_scope="agent:invoke",
        )


def test_api_key_creation_requires_owner_scope_status_and_same_tenant_project() -> None:
    registry = ServiceAccountRegistry()
    service_account = registry.create(
        tenant_id="tenant_1",
        project_id="project_1",
        name="runtime",
        permissions={"agent:invoke"},
        created_by="admin_1",
    )
    disabled = registry.create(
        tenant_id="tenant_1",
        project_id="project_1",
        name="disabled",
        permissions={"agent:invoke"},
        created_by="admin_1",
    )
    disabled.status = "disabled"
    authenticator = APIKeyAuthenticator(service_accounts=registry)

    with pytest.raises(APIKeyScopeError, match="owner_scope_mismatch"):
        authenticator.create_key(
            tenant_id="tenant_2",
            project_id="project_1",
            name="cross-tenant",
            owner_type="service_account",
            owner_id=service_account.id,
            scopes={"agent:invoke"},
            created_by="admin_1",
        )
    with pytest.raises(APIKeyScopeError, match="owner_scope_mismatch"):
        authenticator.create_key(
            tenant_id="tenant_1",
            project_id="project_2",
            name="cross-project",
            owner_type="service_account",
            owner_id=service_account.id,
            scopes={"agent:invoke"},
            created_by="admin_1",
        )
    with pytest.raises(APIKeyDisabledError, match="owner_disabled"):
        authenticator.create_key(
            tenant_id="tenant_1",
            project_id="project_1",
            name="disabled-owner",
            owner_type="service_account",
            owner_id=disabled.id,
            scopes={"agent:invoke"},
            created_by="admin_1",
        )


def test_policy_engine_records_deny_and_approval_audit() -> None:
    audit_sink = InMemoryAuditSink()
    engine = PolicyEngine(
        rules=[
            StaticPolicyRule(
                policy_id="deny-prod-secret",
                tenant_id="tenant_1",
                project_id="project_1",
                resource_type="secret",
                action="read",
                decision=Decision.deny,
                reason="secret_access_denied",
            ),
            StaticPolicyRule(
                policy_id="approve-tool",
                resource_type="tool",
                action="call",
                risk_level="destructive",
                decision=Decision.require_approval,
                reason="approval_required",
            ),
        ],
        audit_sink=audit_sink,
    )

    denied = engine.evaluate(
        PolicyRequest(
            tenant_id="tenant_1",
            project_id="project_1",
            actor_id="user_1",
            actor_type="user",
            resource_type="secret",
            resource_id="secret_1",
            action="read",
        )
    )
    approval = engine.evaluate(
        PolicyRequest(
            tenant_id="tenant_1",
            project_id="project_1",
            actor_id="user_1",
            actor_type="user",
            resource_type="tool",
            resource_id="tool_1",
            action="call",
            risk_level="destructive",
        )
    )

    assert denied.decision == Decision.deny
    assert denied.reason == "secret_access_denied"
    assert approval.decision == Decision.require_approval
    assert approval.approval_required is True
    assert [
        (record.action, record.result, record.reason)
        for record in audit_sink.records
    ] == [
        ("read", "deny", "secret_access_denied"),
        ("call", "require_approval", "approval_required"),
    ]
    assert all(isinstance(record, AuditRecord) for record in audit_sink.records)


def test_policy_rules_are_scoped_by_tenant_and_project() -> None:
    engine = PolicyEngine(
        rules=[
            StaticPolicyRule(
                policy_id="deny-tenant-1-secret",
                tenant_id="tenant_1",
                project_id="project_1",
                resource_type="secret",
                action="read",
                decision=Decision.deny,
                reason="secret_access_denied",
            )
        ]
    )

    same_scope = engine.evaluate(
        PolicyRequest(
            tenant_id="tenant_1",
            project_id="project_1",
            actor_id="user_1",
            actor_type="user",
            resource_type="secret",
            resource_id="secret_1",
            action="read",
        )
    )
    other_scope = engine.evaluate(
        PolicyRequest(
            tenant_id="tenant_2",
            project_id="project_2",
            actor_id="user_2",
            actor_type="user",
            resource_type="secret",
            resource_id="secret_1",
            action="read",
        )
    )

    assert same_scope.decision == Decision.deny
    assert other_scope.decision == Decision.allow
