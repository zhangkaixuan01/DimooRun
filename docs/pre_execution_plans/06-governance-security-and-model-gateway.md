# 06 治理、安全与 Model Gateway 执行计划

> **给执行 Agent 的要求：** 治理能力必须集中到 Policy Engine，不能让 API、Tool、Secret、Model、Extension、Compatibility 路径各自决定权限。

**目标：** 实现 RBAC、API Key、ServiceAccount、Policy Engine、Tool Gateway、SecretProvider、Model Gateway / New API 集成、Human-in-the-loop、Catalog、Prompt/Config/Template 资产、Sandbox Policy。

**架构说明：** 所有治理入口都调用 Policy Engine。Policy Engine 只返回决策，不执行业务动作。所有 deny、require_approval、policy_violation 都写 AuditLog。

**设计覆盖：** `DESIGN_SPEC.md` 第 18、27、28、31、32、43、44、45、46、50 章。

**当前状态：** 已完成 Dev/MVP contract-level 基础实现。当前实现提供 RBAC resource:action 权限表、ServiceAccountRegistry、APIKeyAuthenticator、Deployment API Bearer API Key 接入、PolicyEngine / PolicyDecision / AuditSink 边界、ToolGateway 高风险审批、SecretProvider 策略校验、ModelGatewayProvider / ModelPolicy / usage snapshot、HumanTaskService、CatalogService、PromptAssetStore、SandboxPolicy，以及治理相关领域表实体化。真实数据库 repository、生产鉴权 middleware、外部 New API HTTP 调用、真实 Secret 后端、限流、dry-run、回滚和完整 Console 页面进入后续阶段。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 18 章：Execution Isolation & Sandbox。
- [x] 第 27 章：Component, Tool, and MCP Catalog。
- [x] 第 28 章：Prompt, Config, and Template Assets。
- [x] 第 31 章：Human-in-the-loop Governance。
- [x] 第 32 章：Policy Engine。
- [x] 第 43 章：权限系统。
- [x] 第 44 章：Tool Gateway。
- [x] 第 45 章：Model Gateway / Provider Governance。
- [x] 第 46 章：Secret 管理。
- [x] 第 50 章：插件化设计。

## 1. 文件规划

```text
apps/server/dimoo_run/security/auth.py
apps/server/dimoo_run/security/api_keys.py
apps/server/dimoo_run/identity/service_accounts.py
apps/server/dimoo_run/policy/engine.py
apps/server/dimoo_run/policy/decisions.py
apps/server/dimoo_run/tools/gateway.py
apps/server/dimoo_run/secrets/provider.py
apps/server/dimoo_run/model_gateway/provider.py
apps/server/dimoo_run/hitl/service.py
apps/server/dimoo_run/catalog/service.py
apps/server/dimoo_run/prompts/assets.py
apps/server/dimoo_run/sandbox/policy.py
tests/governance/
```

## 2. 权限模型

资源动作必须包含：

```text
agent:read/create/update/delete/deploy/invoke
run:read/cancel/retry/read_input/read_output
trace:read/read_prompt/read_tool_args/export
task:read
tool:read/call/approve
secret:read/create/update/delete
policy:read/create/update/delete
artifact:read/create/delete
dataset:read/create/update/delete
experiment:read/create/run
schedule:read/create/update/delete
batch:read/create
replay:create
memory:read/create/update/delete
catalog:read/create/update/delete
prompt:read/create/update/delete
model_gateway:read/create/update/delete/use
published_surface:read/create/update/delete
extension:read/create/update/delete
alert:read/create/update/delete
backup:read/create/restore
audit:read
user:manage
service_account:manage
role:manage
```

RBAC MVP：

```text
Owner：租户内所有资源。
Admin：用户、权限、Agent、Deployment。
Developer：注册 Agent、发布版本、查看运行结果。
Operator：查看运行状态、取消、重试、回滚。
Auditor：查看审计日志和运行记录。
Viewer：只读查看。
EndUser：调用授权 Agent。
```

规则：

- [x] 权限基于 `resource:action`，不基于菜单。
- [x] 菜单只是前端展示结果。
- [x] 后端接口必须强制鉴权。

## 3. API Key 与 ServiceAccount

APIKey 字段：

```text
tenant_id
project_id nullable
name
owner_type: user | service_account
owner_id
key_hash
scopes
status
last_used_at
rotation_policy nullable
expires_at
created_by
created_at
```

ServiceAccount 规则：

- [x] 权限必须显式授予。
- [x] 不继承创建者全部权限。
- [x] API Key scopes 是 ServiceAccount 权限子集。
- [x] API Key owner 必须与 key 的 tenant/project scope 一致，且 owner 必须 active。
- [x] 高风险 ServiceAccount 支持过期、轮换、审批。
- [x] 调用写 AuditLog，`actor_type=service_account`。

测试：

- [x] 禁用 API Key 后拒绝所有调用。
- [x] project-scoped API Key 不能访问其他 project。
- [x] API Key scope 不能超过 owner 权限。
- [x] Deployment API 控制类操作必须使用 Bearer API Key，并要求 `agent:deploy` scope。
- [x] Deployment API 只读类操作必须使用 Bearer API Key，并要求 `agent:read` scope。
- [x] `last_used_at` 更新。

## 4. Policy Engine

Policy 输入：

```text
tenant_id
project_id
user_id
service_account_id
agent_id
agent_version_id
deployment_id
environment
resource_type
resource_id
action
risk_level
runtime_context
request_metadata
```

决策：

```text
allow
deny
allow_with_redaction
allow_with_limit
require_approval
require_dry_run
fallback
```

PolicyDecision 字段：

```text
decision
reason
matched_policy_ids
limits
redactions
approval_required
expires_at
metadata
```

实现要求：

- [x] 第一版用数据库规则实现。
- [x] 后续可替换 OPA / Cedar / Casbin。
- [x] API、Worker、ToolGateway、SecretProvider、ModelGatewayProvider 必须调用。
- [x] deny / approval / violation 必须写 AuditLog。

## 5. Tool Gateway

调用链：

```text
Agent
  ↓
Tool Gateway
  ↓
Policy Engine
  ↓
参数校验
  ↓
审计
  ↓
限流
  ↓
实际企业系统
```

风险等级：

```text
read
write
external_side_effect
destructive
financial
privileged
```

高风险 Tool：

- [x] human approval。
- [ ] dry-run。
- [ ] 二次确认。
- [ ] 调用前后快照。
- [ ] 回滚策略 metadata。
- [x] 调用审计。

## 6. Model Gateway / New API

边界：

```text
DimooRun 不重做模型供应商聚合、渠道管理、倍率计费、充值、余额。
DimooRun 通过 ModelGatewayProvider 集成 New API / LiteLLM / OpenAI-compatible Gateway。
DimooRun 负责运行归因、预算策略、熔断、审批、审计、usage/cost snapshot。
```

ModelGateway：

```text
provider_type: newapi | litellm | openai_compatible | custom
base_url
credential_ref
default_model_group
status
metadata
```

ModelPolicy：

```text
allowed_models
denied_models
default_model
gateway_id
max_tokens_per_run
max_cost_per_run
max_cost_per_day
fallback_policy
on_budget_exceeded: reject | warn | require_approval | fallback
```

ModelUsageSnapshot：

```text
run_id
attempt_id
gateway_id
gateway_request_id
model
provider
prompt_tokens
completion_tokens
total_tokens
cost
currency
raw_usage
created_at
```

规则：

- [x] Agent Package 不暴露底层模型供应商 Key。
- [x] Worker 注入 Model Gateway endpoint 和受控 credential 引用。
- [x] ModelGateway / ModelPolicy 与 RuntimeContext tenant/project scope 必须一致。
- [x] Runtime 模型调用使用 `model_gateway:use` / Policy Engine action，不与 `model_gateway:create` 管理动作混用。
- [x] usage / cost 从 callback、网关响应或观测事件提取。
- [ ] Agent 绕过 Model Gateway 直连供应商时标记 `policy_violation` 或 `unsupported_usage_accounting`。

## 7. Secret 管理

SecretProvider：

```python
class SecretProvider(Protocol):
    async def get_secret(
        self,
        tenant_id: int,
        project_id: int | None,
        secret_name: str,
        context: RuntimeContext,
    ) -> str: ...
```

规则：

- [x] 前端不展示 Secret 明文。
- [x] 日志和 Trace 不记录 Secret 明文。
- [x] Agent 只能获得授权 Secret。
- [x] Secret 使用记录 `last_used_at`。
- [x] Secret 使用写 AuditLog。

## 8. Human-in-the-loop

HumanTask 类型：

```text
approval
input_required
review
escalation
```

来源：

- [ ] Adapter 产生 `human_interrupt.required`。
- [x] 高风险 Tool。
- [ ] 高风险 Model。
- [ ] Secret read。
- [ ] Deployment 控制。
- [x] Policy Engine 判定 `require_approval`。

规则：

- [ ] 审批结果通过 resume payload 回到 Run。
- [x] 审批人不能审批自己触发的高风险操作，除非策略允许。
- [ ] 审批超时必须有明确结果。
- [x] HumanTask 必须写审计。

## 9. Catalog 与资产治理

Catalog 类型：

```text
AdapterCatalogItem
ToolCatalogItem
MCPServerCatalogItem
ModelGatewayCatalogItem
StoreProviderCatalogItem
EvaluatorCatalogItem
ExtensionCatalogItem
```

Prompt / Config / Template：

- [x] PromptAsset。
- [x] ConfigAsset。
- [x] AgentTemplate。
- [x] DeploymentTemplate。
- [x] PolicyTemplate。

规则：

- [x] 生产环境禁止隐式 latest。
- [ ] AgentVersion 记录引用的资产版本。
- [x] 大内容进入 Artifact Store。
- [x] visibility policy 控制展示和脱敏。
- [x] 变更写 AuditLog。

## 10. Sandbox Policy

隔离等级：

```text
L0 in_process
L1 dedicated venv
L2 subprocess
L3 container sandbox
L4 remote isolated pool
```

策略：

- [x] network egress policy。
- [x] filesystem policy。
- [x] env whitelist。
- [x] Secret runtime injection。
- [ ] 临时文件按 retention 清理或转 Artifact。
- [x] 越权访问产生 `security.policy_violation`。

## 11. 验收清单

- [x] API Key 鉴权测试通过。
- [x] ServiceAccount 调用写 AuditLog。
- [x] Policy deny 写 AuditLog。
- [x] Tool high-risk 创建 HumanTask。
- [x] ModelGateway 可调用 OpenAI-compatible endpoint。
- [x] ModelGateway 跨 tenant/project 绑定会被拒绝并记录 policy violation。
- [x] Budget exceeded 行为符合策略。
- [x] Secret 不在日志和 Trace 明文出现。
- [x] PromptAsset / ConfigAsset 版本化可查询。

命令：

```bash
uv run pytest tests/governance -q
```

## 12. 提交建议

```text
feat: add governance security and model gateway
```

## 13. 设计回查清单

- [x] Sandbox 隔离等级覆盖第 18 章。
- [x] Catalog 类型覆盖第 27 章。
- [x] Prompt / Config / Template 资产规则覆盖第 28 章。
- [x] HumanTask / ApprovalPolicy 覆盖第 31 章。
- [x] Policy 输入、决策、原则覆盖第 32 章。
- [x] RBAC MVP 覆盖第 43 章。
- [x] Tool Gateway 风险等级和高风险策略覆盖第 44 章。
- [x] Model Gateway 边界不重复 New API，符合第 45 章。
- [x] SecretProvider 规则覆盖第 46 章。
