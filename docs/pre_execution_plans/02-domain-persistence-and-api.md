# 02 领域模型、持久化与 API 执行计划

> **给执行 Agent 的要求：** 逐任务实现并运行测试。领域模型是后续 Runtime、治理、Console 的基础，不允许随意省略设计文档中的对象。

**目标：** 实现 DimooRun 的核心领域模型、扩展领域模型、数据库迁移、Repository 边界、Native API、Admin API 和 OpenAPI 契约治理。

**架构说明：** 领域层描述平台事实，持久化层负责存取，API 层只做请求/响应和调用服务。所有写 API 都要预留 auth、tenant/project scope、Policy Engine、AuditLog、Idempotency-Key、X-Request-Id。

**设计覆盖：** `DESIGN_SPEC.md` 第 12、22、23、37、38 章。

**当前状态：** 已完成并推送到 `main`。实现提交包括：

```text
843ec0b feat: add domain persistence and api contracts
5167bb4 fix: add audit fields and soft delete semantics
d4d35f8 fix: harden domain persistence contracts
a368499 fix(persistence): harden metadata contracts
```

**最终验证：**

```bash
uv run pytest -q                         # 38 passed
uv run ruff check .                      # passed
uv run mypy apps/server tests scripts    # passed
uv run python scripts/export_openapi.py  # passed
npm run build                            # passed
```

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 12 章：Schema Migration & Data Compatibility。
- [x] 第 22 章：核心领域模型。
- [x] 第 23 章：Extended Domain Models。
- [x] 第 37 章：存储边界。
- [x] 第 38 章：API 设计。
- [x] 第 53 章：MVP 范围。

## 1. 实现边界

本计划负责：

- [x] SQLAlchemy Base。
- [x] Alembic migration。
- [x] Core Domain Models。
- [x] Extended Domain Models 的最小 metadata 表。
- [x] Native API 路由骨架。
- [x] Admin / Governance API 路由骨架。
- [x] OpenAPI 导出。
- [x] API schema 版本治理起点。

本计划不负责：

- [x] 真实 Worker 执行：不在本阶段。
- [x] 真实 Policy 判定逻辑：不在本阶段。
- [x] 真实 Adapter 加载：不在本阶段，进入 `03-agent-package-and-adapters.md`。
- [x] Console 页面：不在本阶段。

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
idempotency_records
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
  idempotency_records

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

- [x] 每个 migration 文件只做一个分组。
- [x] 每个 migration 都有 downgrade。
- [x] 每个 migration 都有 metadata table existence 测试。
- [x] 如果 MVP 暂不实现某类业务逻辑，也可以先建最小 metadata 表，但必须在注释和计划中说明用途。

实现补充：

- Alembic migration 已从 `Base.metadata.create_all(...)` 改为冻结的显式迁移脚本，历史 migration 不再依赖最新 ORM metadata。
- `migrations/table_helpers.py` 只复用稳定列定义 helper，不读取 ORM model。
- `migrations/env.py` 同时加入项目根目录和 `apps/server` 到 `sys.path`，保证 migration helper 和 server 包都可导入。
- 核心查询索引已在 migration 中显式创建，并用测试校验 migration 后的数据库索引覆盖 ORM metadata 中的核心索引。

字段策略：

- [x] 核心对象字段按 `DESIGN_SPEC.md` 完整建。
- [x] 扩展对象第一版至少包含 `id`、`tenant_id`、`project_id nullable`、`status`、`metadata_json`、`created_at`、`updated_at`。
- [x] 所有 Platform Metadata Store 表必须包含通用审计与软删除字段：`created_at`、`created_by`、`updated_at`、`updated_by`、`is_deleted`、`deleted_at`、`deleted_by`。
- [x] 默认业务删除必须是 soft delete，不允许 API / Repository 默认 hard delete。
- [x] `status=archived` 是生命周期归档，不等同于 `is_deleted=true`。
- [x] 默认 Repository 查询过滤 `is_deleted=true`，只有显式 `include_deleted` 才返回软删除记录。
- [x] AuditLog 保留通用字段但必须不可变，不允许业务软删除。
- [x] 扩展 metadata 表的 `tenant_id` / `project_id` 必须是外键，不允许只存裸字符串。
- [x] 关键唯一性必须由数据库约束保护：Project slug、Agent name、AgentVersion version、Deployment scope、API key hash、Idempotency key。
- [x] 幂等写 API 必须落到 `idempotency_records`，不能只把幂等键散落在 Run / Task 表。
- [x] 大 JSON 使用 `*_json` 命名，例如 `manifest_json`、`payload_json`、`config_json`。
- [x] 不使用含糊的 `data` 字段。
- [x] 所有多租户对象必须有 `tenant_id`。
- [x] Project 级对象必须有 `project_id` 或明确 nullable。

实现补充：

- 所有 `DateTime` 字段已统一为 timezone-aware `DateTime(timezone=True)`。
- `Agent` 与 `Deployment` 的唯一性使用 active-only partial unique index，软删除后允许重建同名资源。
- 扩展 metadata 表通过 `Table.info["placeholder"] = True` 标记为第一阶段占位表，避免误认为领域字段已经完整实体化。
- `AuditLog` 保留审计/软删除列用于统一 schema，但 repository 层禁止业务软删除。

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
migrations/__init__.py
migrations/table_helpers.py
migrations/versions/0001_core_identity_and_agents.py
migrations/versions/0002_runtime_execution.py
migrations/versions/0003_governance.py
migrations/versions/0004_observability_quality.py
migrations/versions/0005_platform_extensions.py
scripts/export_openapi.py
openapi/dimoorun.openapi.json
tests/domain/test_domain_models.py
tests/domain/test_migrations.py
tests/domain/test_repositories.py
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
GET    /v1/tasks/{task_id}
POST   /v1/tasks/{task_id}/cancel
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

- [x] 创建 `domain/enums.py`。
- [x] 创建 `domain/schemas.py`。
- [x] Schema 使用明确字段，不返回裸 dict。
- [x] 错误响应包含稳定 `error_code`。

测试：

- [x] 枚举值与设计文档一致。
- [x] Deployment schema 能区分 `desired_status` 和 `runtime_status`。
- [x] Run schema 包含 `service_account_id nullable`。

### Task 2：实现 SQLAlchemy 模型

- [x] 创建 `persistence/database.py`。
- [x] 创建 `domain/models.py`。
- [x] 所有表进入 `Base.metadata.tables`。
- [x] 字段命名与设计文档一致。
- [x] JSON 字段使用 `JSON` 类型或兼容 SQLite 的 JSON 存储。

测试：

- [x] 检查全部必需表存在。
- [x] 检查核心外键存在。
- [x] 检查状态字段默认值正确。
- [x] 检查所有 DateTime 字段为 timezone-aware。
- [x] 检查扩展 metadata placeholder 标记存在。
- [x] 检查 soft-delete-aware unique index 存在。

### Task 3：实现 Alembic 迁移

- [x] 创建 Alembic 配置。
- [x] 创建分组 migration：`0001_core_identity_and_agents.py` 到 `0005_platform_extensions.py`。
- [x] 空库执行 upgrade 成功。
- [x] downgrade 能删除表。
- [x] migration 脚本不依赖 live ORM metadata。
- [x] migration 后核心索引覆盖 ORM metadata 中声明的索引。

验收命令：

```bash
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
  默认查询不返回该记录，除非 include_deleted=true。

AuditLog:
  AuditLog 是不可变事实，Repository 不允许 update / archive / soft delete。

hard delete:
  仅允许 migration rollback、测试清理、retention purge job 或显式管理员物理清理任务使用。
```

必须覆盖：

- [x] AgentRepository。
- [x] AgentVersionRepository。
- [x] DeploymentRepository。
- [x] RunRepository。
- [x] TaskRepository。
- [x] EventRepository。
- [x] AuditLogRepository。

实现补充：

- Repository 能力按模型形状拆分为基础查询、project scoped 查询、status 更新、soft delete、archive 等 mixin。
- 没有 `project_id` 的模型不会暴露 `list_by_project`。
- 没有 status 语义的模型不会暴露 `update_status`。

### Task 5：实现 Native API 骨架

- [x] 路由挂到 `/v1`。
- [x] 每个写 API 接收 `X-Request-Id`。
- [x] 幂等写 API 接收 `Idempotency-Key`。
- [x] 暂未实现真实业务时返回明确 `501 not_implemented`，不能静默成功或返回假数据。
- [x] OpenAPI 中必须出现全部路径。

### Task 6：实现 Admin API 骨架

- [x] 路由命名和设计文档一致。
- [x] 高风险 API 在响应 schema 中包含 `audit_required: true`。
- [x] HumanTask approve/reject 路由预留 `decision_payload`。

### Task 7：实现 OpenAPI 导出和契约检查

创建：

```text
scripts/export_openapi.py
openapi/dimoorun.openapi.json
```

检查：

- [x] OpenAPI 包含 Native API。
- [x] OpenAPI 包含 Admin API。
- [x] 错误响应 schema 统一。
- [x] SDK 后续可以从该文件生成。
- [x] `scripts/export_openapi.py` 支持 `--output`，测试可写入临时文件。
- [x] 未实现 GET / POST / PATCH / DELETE API 的 OpenAPI 均声明 `501 ErrorResponse`。

## 8. 验收清单

- [x] `uv run pytest tests/domain -q` 通过。
- [x] `uv run pytest tests/api -q` 通过。
- [x] `uv run alembic upgrade head` 通过。
- [x] `uv run python scripts/export_openapi.py` 生成 OpenAPI。
- [x] OpenAPI 包含 Deployment Runtime Control API。
- [x] 表清单没有遗漏 `DESIGN_SPEC.md` 中的核心对象。
- [x] `uv run pytest -q` 通过，最终结果 `38 passed`。
- [x] `uv run ruff check .` 通过。
- [x] `uv run mypy apps/server tests scripts` 通过。
- [x] `npm run build` 通过。

## 9. 提交建议

已落地提交：

```text
843ec0b feat: add domain persistence and api contracts
5167bb4 fix: add audit fields and soft delete semantics
d4d35f8 fix: harden domain persistence contracts
a368499 fix(persistence): harden metadata contracts
```

## 10. 设计回查清单

- [x] 第 22 章所有核心对象都有模型或明确 metadata 表。
- [x] 第 23 章所有扩展对象都有落点或明确延后实现说明。
- [x] 第 37.1 章 Platform Metadata Store 表清单没有遗漏。
- [x] 第 38 章所有 API surface 都有路由边界。
- [x] API 通用规则包含 auth、tenant/project scope、Policy Engine、AuditLog、request_id、idempotency。
- [x] Schema version 字段预留覆盖第 12 章列出的版本维度。
- [x] 所有表都有统一审计与软删除字段，删除语义没有退化为 hard delete。
- [x] Repository 默认过滤软删除记录。
- [x] DELETE API 不返回静默 204，必须表达 soft delete / AuditLog / Policy 边界。
- [x] AuditLog 不可变约束有测试覆盖。
- [x] 扩展 metadata 表有 tenant/project 外键。
- [x] 关键唯一性约束有测试覆盖。
- [x] `idempotency_records` 表和唯一约束有测试覆盖。

## 11. 后续进入 03 前的注意事项

- `03-agent-package-and-adapters.md` 可以基于当前 `Agent` / `AgentVersion` / `Deployment` / `Run` / `Task` 表继续开发。
- Adapter 相关真实加载、manifest 校验、package registry、LangGraph conformance test 不属于本阶段，进入 03 实现。
- 当前 API 路由是 contract skeleton，未实现业务的接口必须继续保持 `501 not_implemented`，直到对应服务层真实接入。
- 扩展 metadata placeholder 表只保证治理落点，不代表对应领域字段已经最终定型；后续计划实体化时必须新增 migration。
