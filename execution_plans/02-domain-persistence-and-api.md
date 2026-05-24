# 02 领域模型、持久化与 API 执行计划

> **给执行 Agent 的要求：** 逐任务实现并运行测试。领域模型是后续 Runtime、治理、Console 的基础，不允许随意省略设计文档中的对象。

**目标：** 实现 DimooRun 的核心领域模型、扩展领域模型、数据库迁移、Repository 边界、Native API、Admin API 和 OpenAPI 契约治理。

**架构说明：** 领域层描述平台事实，持久化层负责存取，API 层只做请求/响应和调用服务。所有写 API 都要预留 auth、tenant/project scope、Policy Engine、AuditLog、Idempotency-Key、X-Request-Id。

**设计覆盖：** `DESIGN_SPEC.md` 第 12、22、23、37、38 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [ ] 第 12 章：Schema Migration & Data Compatibility。
- [ ] 第 22 章：核心领域模型。
- [ ] 第 23 章：Extended Domain Models。
- [ ] 第 37 章：存储边界。
- [ ] 第 38 章：API 设计。
- [ ] 第 53 章：MVP 范围。

## 1. 实现边界

本计划负责：

- [ ] SQLAlchemy Base。
- [ ] Alembic migration。
- [ ] Core Domain Models。
- [ ] Extended Domain Models 的最小 metadata 表。
- [ ] Native API 路由骨架。
- [ ] Admin / Governance API 路由骨架。
- [ ] OpenAPI 导出。
- [ ] API schema 版本治理起点。

本计划不负责：

- [ ] 真实 Worker 执行。
- [ ] 真实 Policy 判定逻辑。
- [ ] 真实 Adapter 加载。
- [ ] Console 页面。

## 2. 必须实现的核心对象

核心领域模型：

```text
Tenant
Project / Workspace
User
ServiceAccount
Role
Permission
APIKey
Agent
AgentVersion
Deployment
AgentInstance
Session
Run
RunAttempt
Task
Event
CheckpointIndex
Tool
Secret
AuditLog
```

扩展领域模型：

```text
PublishedSurface
IngressRoute
CatalogItem
PromptAsset
ConfigAsset
TemplateAsset
RunGraphNode
RunGraphEdge
Dataset
DatasetItem
Experiment
ExperimentRun
EvaluationResult
Feedback
ScheduledRun
BatchRun
ReplayJob
MemoryBlock
SemanticStoreProvider
ModelGateway
ModelPolicy
ModelUsageSnapshot
Policy
PolicyDecision
HumanTask
ApprovalRequest
ApprovalPolicy
Artifact
NotificationChannel
AlertRule
IncidentEvent
WebhookSubscription
Extension
BackupPlan
RestoreJob
```

## 3. 数据库表清单

必须创建：

```text
tenants
projects
users
service_accounts
roles
permissions
api_keys
agents
agent_versions
deployments
agent_instances
sessions
runs
run_attempts
tasks
events
checkpoint_indexes
tools
secrets
audit_logs
published_surfaces
ingress_routes
catalog_items
prompt_assets
config_assets
templates
run_graph_nodes
run_graph_edges
datasets
dataset_items
experiments
experiment_runs
evaluation_results
feedback
scheduled_runs
batch_runs
replay_jobs
memory_blocks
semantic_store_providers
model_gateways
model_policies
model_usage_snapshots
policies
policy_decisions
human_tasks
approval_requests
approval_policies
artifacts
notification_channels
alert_rules
incident_events
webhook_subscriptions
extensions
backup_plans
restore_jobs
```

## 3.1 Migration 分组策略

设计文档定义了完整领域对象，但实现时 migration 需要分组，避免第一版 migration 过大、不可 review。

推荐分组：

```text
0001_core_identity_and_agents:
  tenants
  projects
  users
  service_accounts
  roles
  permissions
  api_keys
  agents
  agent_versions
  deployments
  agent_instances

0002_runtime_execution:
  sessions
  runs
  run_attempts
  tasks
  events
  checkpoint_indexes
  artifacts
  audit_logs

0003_governance:
  policies
  policy_decisions
  tools
  secrets
  model_gateways
  model_policies
  model_usage_snapshots
  human_tasks
  approval_requests
  approval_policies

0004_observability_quality:
  run_graph_nodes
  run_graph_edges
  datasets
  dataset_items
  experiments
  experiment_runs
  evaluation_results
  feedback
  memory_blocks
  semantic_store_providers

0005_platform_extensions:
  published_surfaces
  ingress_routes
  catalog_items
  prompt_assets
  config_assets
  templates
  scheduled_runs
  batch_runs
  replay_jobs
  notification_channels
  alert_rules
  incident_events
  webhook_subscriptions
  extensions
  backup_plans
  restore_jobs
```

执行规则：

- [ ] 每个 migration 文件只做一个分组。
- [ ] 每个 migration 都有 downgrade。
- [ ] 每个 migration 都有 metadata table existence 测试。
- [ ] 如果 MVP 暂不实现某类业务逻辑，也可以先建最小 metadata 表，但必须在注释和计划中说明用途。

字段策略：

- [ ] 核心对象字段按 `DESIGN_SPEC.md` 完整建。
- [ ] 扩展对象第一版至少包含 `id`、`tenant_id`、`project_id nullable`、`status`、`metadata_json`、`created_at`、`updated_at`。
- [ ] 所有 Platform Metadata Store 表必须包含通用审计与软删除字段：`created_at`、`created_by`、`updated_at`、`updated_by`、`is_deleted`、`deleted_at`、`deleted_by`。
- [ ] 默认业务删除必须是 soft delete，不允许 API / Repository 默认 hard delete。
- [ ] `status=archived` 是生命周期归档，不等同于 `is_deleted=true`。
- [ ] 大 JSON 使用 `*_json` 命名，例如 `manifest_json`、`payload_json`、`config_json`。
- [ ] 不使用含糊的 `data` 字段。
- [ ] 所有多租户对象必须有 `tenant_id`。
- [ ] Project 级对象必须有 `project_id` 或明确 nullable。

## 4. 状态枚举

必须实现：

```text
DeploymentDesiredStatus:
draft, active, paused, draining, stopped, archived

DeploymentRuntimeStatus:
not_loaded, warming_up, ready, degraded, failed, draining, stopped

AgentInstanceStatus:
loading, ready, busy, idle, draining, evicted, failed

RunStatus:
pending, running, interrupted, succeeded, failed, cancelled, timeout

RunAttemptStatus:
running, succeeded, failed, timeout, cancelled, worker_lost

TaskStatus:
queued, leased, running, retrying, succeeded, failed, dead_letter, cancelled

AuditActorType:
user, service_account, system, agent
```

## 5. 文件规划

```text
apps/server/dimoo_run/domain/enums.py
apps/server/dimoo_run/domain/models.py
apps/server/dimoo_run/domain/schemas.py
apps/server/dimoo_run/persistence/database.py
apps/server/dimoo_run/persistence/repositories.py
apps/server/dimoo_run/api/dependencies.py
apps/server/dimoo_run/api/native/agents.py
apps/server/dimoo_run/api/native/deployments.py
apps/server/dimoo_run/api/native/runs.py
apps/server/dimoo_run/api/native/tasks.py
apps/server/dimoo_run/api/admin/*.py
migrations/env.py
migrations/versions/0001_initial_domain.py
scripts/export_openapi.py
openapi/dimoorun.openapi.json
tests/domain/test_domain_models.py
tests/api/test_native_api.py
tests/api/test_admin_api.py
tests/api/test_openapi_contract.py
```

## 6. API 路由范围

Native API：

```http
POST   /v1/agents
GET    /v1/agents
GET    /v1/agents/{agent_id}
PATCH  /v1/agents/{agent_id}
DELETE /v1/agents/{agent_id}
POST   /v1/agents/{agent_id}/versions
GET    /v1/agents/{agent_id}/versions
GET    /v1/agents/{agent_id}/versions/{version}
POST   /v1/agents/{agent_id}/invoke
POST   /v1/agents/{agent_id}/tasks
POST   /v1/agents/{agent_id}/stream
GET    /v1/runs/{run_id}
GET    /v1/runs/{run_id}/events
GET    /v1/runs/{run_id}/attempts
POST   /v1/runs/{run_id}/cancel
POST   /v1/runs/{run_id}/resume
POST   /v1/runs/{run_id}/retry
POST   /v1/runs/{run_id}/replay
GET    /v1/deployments
GET    /v1/deployments/{deployment_id}
POST   /v1/deployments/{deployment_id}/activate
POST   /v1/deployments/{deployment_id}/pause
POST   /v1/deployments/{deployment_id}/resume
POST   /v1/deployments/{deployment_id}/drain
POST   /v1/deployments/{deployment_id}/stop
POST   /v1/deployments/{deployment_id}/restart
GET    /v1/deployments/{deployment_id}/instances
```

Admin / Governance API：

```http
GET/POST /v1/policies
GET      /v1/artifacts/{artifact_id}
GET      /v1/human-tasks
POST     /v1/human-tasks/{task_id}/approve
POST     /v1/human-tasks/{task_id}/reject
GET/POST /v1/model-gateways
GET/POST /v1/published-surfaces
GET/POST /v1/ingress-routes
GET      /v1/catalog/items
GET/POST /v1/datasets
GET/POST /v1/experiments
GET/POST /v1/service-accounts
GET/POST /v1/schedules
GET/POST /v1/batch-runs
GET/POST /v1/notifications/channels
GET/POST /v1/alerts/rules
GET/POST /v1/backups/plans
```

## 6.1 第一批错误响应 Schema

统一错误响应：

```json
{
  "error_code": "deployment_not_accepting_runs",
  "message": "Deployment is not accepting new runs.",
  "request_id": "req_123",
  "details": {
    "deployment_id": "dep_123",
    "desired_status": "paused"
  }
}
```

本计划必须至少注册这些错误码：

```text
manifest_invalid
deployment_not_accepting_runs
idempotency_conflict
compatibility_not_supported
policy_denied
approval_required
artifact_access_denied
```

后续计划补充 Adapter、Worker、Streaming、Backup 相关错误码。

## 7. 任务拆分

### Task 1：实现枚举和 Pydantic Schema

- [ ] 创建 `domain/enums.py`。
- [ ] 创建 `domain/schemas.py`。
- [ ] Schema 使用明确字段，不返回裸 dict。
- [ ] 错误响应包含稳定 `error_code`。

测试：

- [ ] 枚举值与设计文档一致。
- [ ] Deployment schema 能区分 `desired_status` 和 `runtime_status`。
- [ ] Run schema 包含 `service_account_id nullable`。

### Task 2：实现 SQLAlchemy 模型

- [ ] 创建 `persistence/database.py`。
- [ ] 创建 `domain/models.py`。
- [ ] 所有表进入 `Base.metadata.tables`。
- [ ] 字段命名与设计文档一致。
- [ ] JSON 字段使用 `JSON` 类型或兼容 SQLite 的 JSON 存储。

测试：

- [ ] 检查全部必需表存在。
- [ ] 检查核心外键存在。
- [ ] 检查状态字段默认值正确。

### Task 3：实现 Alembic 迁移

- [ ] 创建 Alembic 配置。
- [ ] 创建 `0001_initial_domain.py`。
- [ ] 空库执行 upgrade 成功。
- [ ] downgrade 能删除表。

验收命令：

```powershell
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

### Task 4：实现 Repository 边界

Repository 第一版提供：

```text
create
get_by_id
list_by_project
update_status
soft_delete_or_archive
```

删除语义：

```text
soft_delete_or_archive:
  设置 is_deleted=true。
  设置 deleted_at。
  设置 deleted_by。
  如果模型有 status 字段，同时设置 status=archived。

hard delete:
  仅允许 migration rollback、测试清理、retention purge job 或显式管理员物理清理任务使用。
```

必须覆盖：

- [ ] AgentRepository。
- [ ] AgentVersionRepository。
- [ ] DeploymentRepository。
- [ ] RunRepository。
- [ ] TaskRepository。
- [ ] EventRepository。
- [ ] AuditLogRepository。

### Task 5：实现 Native API 骨架

- [ ] 路由挂到 `/v1`。
- [ ] 每个写 API 接收 `X-Request-Id`。
- [ ] 幂等写 API 接收 `Idempotency-Key`。
- [ ] 暂未实现真实业务时返回明确 `501 not_implemented` 或最小可用响应，不能静默成功。
- [ ] OpenAPI 中必须出现全部路径。

### Task 6：实现 Admin API 骨架

- [ ] 路由命名和设计文档一致。
- [ ] 高风险 API 在响应 schema 中包含 `audit_required: true`。
- [ ] HumanTask approve/reject 路由预留 `decision_payload`。

### Task 7：实现 OpenAPI 导出和契约检查

创建：

```text
scripts/export_openapi.py
openapi/dimoorun.openapi.json
```

检查：

- [ ] OpenAPI 包含 Native API。
- [ ] OpenAPI 包含 Admin API。
- [ ] 错误响应 schema 统一。
- [ ] SDK 后续可以从该文件生成。

## 8. 验收清单

- [ ] `uv run pytest tests/domain -q` 通过。
- [ ] `uv run pytest tests/api -q` 通过。
- [ ] `uv run alembic upgrade head` 通过。
- [ ] `uv run python scripts/export_openapi.py` 生成 OpenAPI。
- [ ] OpenAPI 包含 Deployment Runtime Control API。
- [ ] 表清单没有遗漏 `DESIGN_SPEC.md` 中的核心对象。

## 9. 提交建议

提交信息：

```text
feat: add domain persistence and api contracts
```

## 10. 设计回查清单

- [ ] 第 22 章所有核心对象都有模型或明确 metadata 表。
- [ ] 第 23 章所有扩展对象都有落点或明确延后实现说明。
- [ ] 第 37.1 章 Platform Metadata Store 表清单没有遗漏。
- [ ] 第 38 章所有 API surface 都有路由边界。
- [ ] API 通用规则包含 auth、tenant/project scope、Policy Engine、AuditLog、request_id、idempotency。
- [ ] Schema version 字段预留覆盖第 12 章列出的版本维度。
- [ ] 所有表都有统一审计与软删除字段，删除语义没有退化为 hard delete。
