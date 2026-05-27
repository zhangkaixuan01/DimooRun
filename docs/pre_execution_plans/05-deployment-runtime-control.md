# 05 Deployment Runtime Control 执行计划

> **给执行 Agent 的要求：** 前端和 API 不能直接“启动 Agent”。必须通过 Deployment desired_status 控制运行目标，由 Worker 管理 AgentInstance。

**目标：** 实现 Deployment 启停控制、AgentInstance 生命周期、状态聚合、实例缓存、PublishedSurface、IngressRoute 和相关 API。

**架构说明：** Agent 是逻辑对象，AgentVersion 是不可变包，Deployment 是运行目标，AgentInstance 是 Worker 上实际加载的实例。Console 控制 Deployment，Worker 响应 desired_status。

**设计覆盖：** `DESIGN_SPEC.md` 第 22.9、22.10、24.1、26、38.5、41、48 章。

**当前状态：** 已完成 Dev/MVP contract-level 基础实现。当前实现提供内存版 DeploymentRuntimeControlService、Policy Engine / Audit Sink 边界、AgentInstanceRegistry、runtime_status 聚合、RunManager deployment gate、PublishedSurface / IngressRoute 策略校验、Deployment API 基础接线，以及 PublishedSurface / IngressRoute 持久化字段硬化。Deployment API 与 service 层均要求 tenant/project request scope，RunManager 会校验 Deployment 与 Run 的 tenant/project/agent/version 绑定关系，PublishedSurface 已限制合法类型。完整持久化 repository、真实 Policy Engine、Console 完整页面、生产级 Worker instance heartbeat / lost detection 进入后续阶段。

**本阶段完成内容：**

- Deployment control actions：activate、pause、resume、drain、stop、restart。
- 所有 control action 经过 Policy Engine 边界，并写 Audit Sink。
- paused / draining / stopped / archived 语义通过 RunManager deployment gate 拒绝新 Run；已有 Run / Task 仍由 04 lease / checkpoint 机制完成。
- RunManager deployment gate 校验 tenant/project/agent/version，防止跨租户、跨项目或跨版本绑定 Run。
- restart / stop 驱逐 AgentInstance cache，不修改 AgentVersion。
- AgentInstance cache key：`deployment_id + agent_version_id + execution_profile_id`。
- runtime_status 聚合：not_loaded、warming_up、ready、degraded、failed、draining、stopped。
- Runtime summary 计算 running_runs、queue_backlog、worker_distribution、last_runtime_error、last heartbeat、loaded_at。
- AgentInstance ready / failed 状态流转统一通过 AgentInstanceRegistry 注入时钟。
- control action 的 AuditEntry 记录 tenant_id、project_id、request_id，为 06 Policy Engine / AuditLog 接线保留上下文。
- PublishedSurface 只允许绑定 active Deployment，且类型必须属于 `api/chat/task/stream/mcp_server/webhook`。
- public IngressRoute 必须绑定 rate limit 并开启 access log。
- PublishedSurface / IngressRoute 持久化表已加入 active 唯一索引，避免重复发布 surface/type 与重复 surface/path。
- Deployment API 已从纯 501 stub 接到内存控制服务；已实现的 Deployment API 不再声明 501 response，并要求请求携带 tenant/project scope。
- `published_surfaces` / `ingress_routes` 从 placeholder 表升级为明确字段表。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 22.9 章：Deployment。
- [x] 第 22.10 章：AgentInstance。
- [x] 第 24.1 章：Deployment Runtime Control。
- [x] 第 26 章：Published Runtime Surfaces。
- [x] 第 38.5 章：Deployment Runtime Control API。
- [x] 第 41 章：Worker Pool。
- [x] 第 48 章：前端 Console 设计。

## 1. 核心语义

对象关系：

```text
Agent
  逻辑智能体，不启动。

AgentVersion
  不可变版本，不启动。

Deployment
  某个 AgentVersion 在某个环境中的运行目标。

AgentInstance
  Worker 上通过 Adapter.load() 加载出的实际运行实例。
```

Deployment desired_status：

```text
draft
active
paused
draining
stopped
archived
```

Deployment runtime_status：

```text
not_loaded
warming_up
ready
degraded
failed
draining
stopped
```

AgentInstance status：

```text
loading
ready
busy
idle
draining
evicted
failed
```

## 2. 文件规划

```text
apps/server/dimoo_run/deployments/service.py
apps/server/dimoo_run/deployments/status.py
apps/server/dimoo_run/deployments/instances.py
apps/server/dimoo_run/gateway/published_surfaces.py
apps/server/dimoo_run/gateway/ingress_routes.py
apps/server/dimoo_run/api/native/deployments.py
tests/deployments/test_runtime_control.py
tests/deployments/test_agent_instances.py
tests/deployments/test_published_surfaces.py
```

## 3. 控制动作

必须实现：

```http
POST /v1/deployments/{deployment_id}/activate
POST /v1/deployments/{deployment_id}/pause
POST /v1/deployments/{deployment_id}/resume
POST /v1/deployments/{deployment_id}/drain
POST /v1/deployments/{deployment_id}/stop
POST /v1/deployments/{deployment_id}/restart
GET  /v1/deployments/{deployment_id}/instances
```

动作语义：

```text
activate：允许新 Run，Worker 可按需加载实例。
pause：不接收新 Run，已有 Run 继续。
resume：从 paused 恢复 active。
drain：不接收新 Run，等待已有 Run 完成后卸载实例。
stop：不接收新 Run，并要求 Worker 卸载实例。
restart：驱逐当前实例，下次 Run 重新 load，不修改 AgentVersion。
```

规则：

- [x] 所有动作经过 Policy Engine 边界；当前为 AllowAll / StaticPolicyEngine Dev 实现。
- [x] 所有动作写 Audit Sink；数据库 AuditLog repository 接线进入持久化阶段。
- [x] `restart` 不是发布，不创建 AgentVersion。
- [x] paused / draining / stopped / archived 拒绝新 Run。
- [x] draining 不取消已有 Run。
- [x] stop 是否取消已有 Run 由策略控制，当前默认不强杀，只驱逐实例缓存。

## 4. Runtime Status 聚合

聚合规则：

```text
not_loaded：没有活动实例。
warming_up：至少一个 loading，且没有 ready。
ready：至少一个 ready/idle/busy，且没有关键失败。
degraded：至少一个可用实例，同时存在 failed 实例或最近错误。
failed：所有实例 failed，或最近加载失败且无可用实例。
draining：desired_status=draining 或实例都在 draining。
stopped：desired_status=stopped 且无活动实例。
```

需要计算：

- [x] running_runs。
- [x] queue backlog。
- [x] worker distribution。
- [x] last_runtime_error。
- [x] last heartbeat。
- [x] loaded_at。

## 5. AgentInstance 缓存

cache key：

```text
deployment_id + agent_version_id + execution_profile_id
```

字段：

```text
id
tenant_id
project_id
deployment_id
agent_id
agent_version_id
worker_id
execution_profile_id
cache_key
status
loaded_at
last_used_at
heartbeat_at
running_runs
error
metadata
```

规则：

- [x] Worker 可以缓存 ready 实例。
- [x] 缓存不改变 AgentVersion 不可变语义。
- [x] restart / stop 可驱逐缓存；drain 将实例标记为 draining。
- [x] 长时间 idle 可按策略 evict。
- [x] Worker 崩溃后 AgentInstance 视为 lost 的生产 heartbeat/reaper 接线保留到 Worker 生产化阶段。
- [x] Run / Task 恢复仍由 lease 和 checkpoint 负责。

## 6. PublishedSurface 与 IngressRoute

PublishedSurface 类型：

```text
api
chat
task
stream
mcp_server
webhook
```

IngressRoute 字段：

```text
path
custom_domain
auth_mode: api_key | jwt | public | internal
cors_policy_id
rate_limit_policy_id
request_transform_ref
response_transform_ref
access_log_enabled
```

规则：

- [x] PublishedSurface 只暴露 active Deployment。
- [x] IngressRoute 不绕过 Runtime API 的规则已写入 gateway 边界；真实请求转发进入 Agent Gateway 阶段。
- [x] public auth_mode 必须显式开启。
- [x] public auth_mode 必须绑定限流和审计。
- [x] 每次调用都落到 Run / Task / Event / AuditLog 的完整链路进入 Agent Gateway 阶段。
- [x] MCP server endpoint 必须经过 Tool Gateway 和 Policy Engine 的完整链路进入 Agent Gateway 阶段。

## 7. 测试计划

- [x] active Deployment 可以创建 Run。
- [x] paused Deployment 拒绝新 Run。
- [x] draining Deployment 拒绝新 Run，但已有 Run 可完成。
- [x] stop 驱逐 AgentInstance。
- [x] restart 驱逐实例，下次 Run 重新 load。
- [x] runtime_status 能正确聚合多 Worker 状态。
- [x] PublishedSurface 不允许绑定非 active Deployment。
- [x] public IngressRoute 没有限流策略时创建失败。

验收命令：

```bash
uv run pytest tests/deployments -q
```

## 8. 提交建议

```text
feat: add deployment runtime control
```

## 9. 设计回查清单

- [x] Deployment desired_status / runtime_status 与第 22.9 章一致。
- [x] AgentInstance 字段和状态与第 22.10 章一致。
- [x] Console 只控制 Deployment，不直接启动 Agent，符合第 24.1 章。
- [x] activate / pause / resume / drain / stop / restart 语义与第 24.1 章一致。
- [x] PublishedSurface / IngressRoute 规则符合第 26 章。
- [x] API 路由完整覆盖第 38.5 章。
