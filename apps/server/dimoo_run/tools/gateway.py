from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dimoo_run.core.context import RuntimeContext
from dimoo_run.hitl.service import HumanTaskService
from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import PolicyEngine, PolicyRequest


class ToolScopeMismatchError(PermissionError):
    error_code = "tool_scope_mismatch"


@dataclass(frozen=True)
class ToolDefinition:
    id: int
    tenant_id: int
    project_id: int | None
    name: str
    risk_level: str
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolCallResult:
    status: str
    output: dict[str, Any] | None = None
    human_task_id: int | None = None


class ToolGateway:
    def __init__(self, *, policy_engine: PolicyEngine, human_tasks: HumanTaskService) -> None:
        self.policy_engine = policy_engine
        self.human_tasks = human_tasks
        self.tools: dict[int, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> ToolDefinition:
        self.tools[definition.id] = definition
        return definition

    def call(
        self,
        *,
        tool_id: int,
        arguments: dict[str, Any],
        context: RuntimeContext,
        actor_id: str | None,
    ) -> ToolCallResult:
        tool = self.tools[tool_id]
        if tool.tenant_id != context.tenant_id or tool.project_id != context.project_id:
            self.policy_engine.record_violation(
                PolicyRequest(
                    tenant_id=context.tenant_id,
                    project_id=context.project_id,
                    actor_id=actor_id,
                    actor_type="user" if actor_id else "agent",
                    resource_type="tool",
                    resource_id=tool.id,
                    action="call",
                    risk_level=tool.risk_level,
                    runtime_context=context.to_metadata(),
                ),
                reason="tool_scope_mismatch",
                metadata={"tool_tenant_id": tool.tenant_id, "tool_project_id": tool.project_id},
            )
            raise ToolScopeMismatchError(tool.id)
        decision = self.policy_engine.evaluate(
            PolicyRequest(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                actor_id=actor_id,
                actor_type="user" if actor_id else "agent",
                resource_type="tool",
                resource_id=tool.id,
                action="call",
                risk_level=tool.risk_level,
                agent_id=context.agent_id,
                agent_version_id=context.agent_version_id,
                deployment_id=context.deployment_id,
                runtime_context=context.to_metadata(),
            )
        )
        if decision.decision == Decision.deny:
            raise PermissionError(decision.reason or "tool_call_denied")
        if decision.decision == Decision.require_approval:
            human_task = self.human_tasks.create_approval(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                run_id=context.run_id,
                attempt_id=None,
                task_id=context.task_id,
                payload={"tool_id": tool.id, "arguments": arguments, "risk_level": tool.risk_level},
                requested_by=actor_id,
            )
            return ToolCallResult(status="approval_required", human_task_id=human_task.id)
        return ToolCallResult(status="succeeded", output=tool.handler(arguments))
