# 05 Deployment Runtime Control 执行计划

> **给执行 Agent 的要求：** 前端和 API 不能直接“启动 Agent”。必须通过 Deployment desired_status 控制运行目标，由 Worker 管理 AgentInstance。

**目标：** 实现 Deployment 启停控制、AgentInstance 生命周期、状态聚合、实例缓存、PublishedSurface、IngressRoute 和相关 API。

**架构说明：** Agent 是逻辑对象，AgentVersion 是不可变包，Deployment 是运行目标，AgentInstance 是 Worker 上实际加载的实例。Console 控制 Deployment，Worker 响应 desired_status。

**设计覆盖：** `DESIGN_SPEC.md` 第 22.9、22.10、24.1、26、38.5、41、48 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [ ] 第 22.9 章：Deployment。
- [ ] 第 22.10 章：AgentInstance。
- [ ] 第 24.1 章：Deployment Runtime Control。
- [ ] 第 26 章：Published Runtime Surfaces。
- [ ] 第 38.5 章：Deployment Runtime Control API。
- [ ] 第 41 章：Worker Pool。
- [ ] 第 48 章：前端 Console 设计。

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

- [ ] 所有动作经过 Policy Engine。
- [ ] 所有动作写 AuditLog。
- [ ] `restart` 不是发布，不创建 AgentVersion。
- [ ] paused / draining / stopped / archived 拒绝新 Run。
- [ ] draining 不取消已有 Run。
- [ ] stop 是否取消已有 Run 由策略控制，默认不强杀。

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

- [ ] running_runs。
- [ ] queue backlog。
- [ ] worker distribution。
- [ ] last_runtime_error。
- [ ] last heartbeat。
- [ ] loaded_at。

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

- [ ] Worker 可以缓存 ready 实例。
- [ ] 缓存不改变 AgentVersion 不可变语义。
- [ ] restart / stop / drain 可驱逐缓存。
- [ ] 长时间 idle 可按策略 evict。
- [ ] Worker 崩溃后 AgentInstance 视为 lost。
- [ ] Run / Task 恢复仍由 lease 和 checkpoint 负责。

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

- [ ] PublishedSurface 只暴露已部署 Agent。
- [ ] IngressRoute 不绕过 Runtime API。
- [ ] public auth_mode 必须显式开启。
- [ ] public auth_mode 必须绑定限流和审计。
- [ ] 每次调用都落到 Run / Task / Event / AuditLog。
- [ ] MCP server endpoint 必须经过 Tool Gateway 和 Policy Engine。

## 7. 测试计划

- [ ] active Deployment 可以创建 Run。
- [ ] paused Deployment 拒绝新 Run。
- [ ] draining Deployment 拒绝新 Run，但已有 Run 可完成。
- [ ] stop 驱逐 AgentInstance。
- [ ] restart 驱逐实例，下次 Run 重新 load。
- [ ] runtime_status 能正确聚合多 Worker 状态。
- [ ] PublishedSurface 不允许绑定非 active Deployment。
- [ ] public IngressRoute 没有限流策略时创建失败。

验收命令：

```powershell
uv run pytest tests/deployments -q
```

## 8. 提交建议

```text
feat: add deployment runtime control
```

## 9. 设计回查清单

- [ ] Deployment desired_status / runtime_status 与第 22.9 章一致。
- [ ] AgentInstance 字段和状态与第 22.10 章一致。
- [ ] Console 只控制 Deployment，不直接启动 Agent，符合第 24.1 章。
- [ ] activate / pause / resume / drain / stop / restart 语义与第 24.1 章一致。
- [ ] PublishedSurface / IngressRoute 规则符合第 26 章。
- [ ] API 路由完整覆盖第 38.5 章。
