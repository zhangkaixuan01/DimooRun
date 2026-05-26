# 10 生产化基础闭环与 Console 接线执行计划

> **给执行 Agent 的要求：** 本阶段只补齐“可以用生产形态本地跑通”的基础闭环，不提前实现复杂 HA、Helm、多区域、Kafka、Temporal 或开放式 Extension API。

**目标：** 将 00-09 阶段的内存实现、占位边界、Console mock 和 CLI skeleton 接成可运行的 Production Foundation：server、worker、console、Postgres、Redis、MinIO、OpenAPI SDK、durable Native 写 API 和 durable repository。

**架构说明：** 10 阶段是 DimooRun 从“功能骨架”进入“本地生产形态闭环”的阶段。重点不是企业云原生，而是让开发者能通过 `dimoorun dev/up/down/worker/logs` 或 Docker Compose 启动完整 Runtime Control Plane，并能注册 Agent、创建 Deployment、发起 Run、查看事件、使用 Console 操作真实后端。

**设计覆盖：** `DESIGN_SPEC.md` 第 15、16、17、20、21、22、24、26、34、38、39、40、41、48、53、54 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [ ] 第 15 章：Project Configuration。
- [ ] 第 16 章：CLI / DX。
- [ ] 第 17 章：Deployment Modes。
- [ ] 第 20 章：Event Model。
- [ ] 第 21 章：Streaming Runtime。
- [ ] 第 22 章：核心领域模型。
- [ ] 第 24 章：Agent Lifecycle。
- [ ] 第 26 章：Published Runtime Surfaces。
- [ ] 第 34 章：Event / Trace / Audit 三账本。
- [ ] 第 38 章：API 设计。
- [ ] 第 39 章：SDK Design。
- [ ] 第 40 章：Task Scheduler。
- [ ] 第 41 章：Worker Pool。
- [ ] 第 48 章：前端 Console 设计。

## 1. 本阶段边界

当前 00-09 基线说明：

- 已有最小进程内 Native Agents / AgentVersions / Runs / Tasks API，可用于 SDK 与 API 契约测试。
- 已有 Console `nativeConsoleClient` 环境变量边界，但页面默认仍以 mock 数据为主。
- 已有 Compatibility API 的 in-memory assistants / threads / runs 与 ReplayBuffer SSE。
- 10 阶段的任务不是重新证明这些接口存在，而是把它们迁移到 durable repository、真实 worker loop、generated SDK 和本地生产形态启动链路。

必须完成：

- [ ] Docker Compose 启动 `server`、`worker`、`console`、`postgres`、`redis`、`minio`。
- [ ] `.env.example` 覆盖 server、worker、console、database、redis、object store、auth、CORS 的最小变量。
- [ ] server 使用 Postgres 作为 Platform Metadata Store。
- [ ] worker 使用同一 Postgres 和 Redis。
- [ ] Console 指向真实 server API。
- [ ] durable Run / Task / RunAttempt / Event / AuditLog repository。
- [ ] durable Deployment / AgentVersion / PublishedSurface 查询和写入路径。
- [ ] durable Compatibility Assistant / Thread / Run repository。
- [ ] Native Agents / AgentVersions / Deployments / Runs / Tasks 写 API durable 化。
- [ ] 真实 OpenAPI 导出进入 `openapi/`。
- [ ] Console API client 改为 generated TypeScript SDK 或 OpenAPI generated typed client。
- [ ] OpenAPI diff CI / 本地检查脚本能阻止未声明 breaking change。
- [ ] `dimoorun dev` 能启动 server、worker、基础 Console。
- [ ] `dimoorun up` / `dimoorun down` 包装 compose。
- [ ] `dimoorun worker` 启动 worker loop。
- [ ] `dimoorun logs` 查看本地服务日志。

不在本阶段：

- [ ] Redis Queue 完整生产 HA 语义。
- [ ] lease reaper 多实例一致性。
- [ ] Redis pub/sub cancel。
- [ ] tenant / project concurrency quota。
- [ ] Helm / K8s。
- [ ] Backup / Restore / DR。
- [ ] Extension Webhook Subscription。
- [ ] Kafka / Temporal / 多区域。

## 2. 文件规划

```text
docker-compose.yml
.env.example
deploy/docker/server.Dockerfile
deploy/docker/worker.Dockerfile
deploy/docker/console.Dockerfile
apps/server/dimoo_run/persistence/repositories/
apps/server/dimoo_run/api/native/
apps/server/dimoo_run/api/admin/
apps/server/dimoo_run/api/compat/repository.py
apps/server/dimoo_run/cli/dev.py
apps/server/dimoo_run/cli/compose.py
apps/server/dimoo_run/worker/loop.py
apps/console/src/api/generated/
openapi/dimoorun.openapi.json
scripts/check_openapi_diff.py
tests/production_foundation/
tests/console_contract/
```

## 3. Docker Compose

服务：

```text
server
worker
console
postgres
redis
minio
```

健康检查：

```text
server /healthz
worker heartbeat endpoint 或 heartbeat record
postgres readiness
redis ping
console static readiness
minio readiness
```

配置要求：

- [ ] server 读取 `DATABASE_URL`、`REDIS_URL`、`OBJECT_STORE_*`。
- [ ] worker 与 server 共用 tenant/project aware repository。
- [ ] console 读取 `VITE_DIMOORUN_API_BASE_URL`。
- [ ] minio bucket 初始化有脚本或启动说明。
- [ ] compose volume 不提交真实数据。

验收命令：

```powershell
docker compose up
```

## 4. Durable Repository

必须从 00-09 的 in-memory / skeleton 迁移到 durable boundary：

- [ ] RunRepository：create、get、list、transition、soft delete。
- [ ] TaskRepository：enqueue、lease snapshot、get、list、transition。
- [ ] RunAttemptRepository：start、heartbeat、complete、fail。
- [ ] EventRepository：append、list by run、sequence uniqueness。
- [ ] AuditLogRepository：append、query by tenant/project/resource。
- [ ] CompatibilityRepository：assistant、thread、run 映射。
- [ ] DeploymentRepository：desired status、runtime status、version binding。
- [ ] AgentRepository：package、version、deployment 读取和写入。

硬性规则：

- [ ] 所有查询必须 tenant/project scoped。
- [ ] 所有表继续保留 created_at / created_by / updated_at / updated_by / is_deleted。
- [ ] 删除默认软删除。
- [ ] 写 API 支持 `X-Request-Id`。
- [ ] 需要幂等的写 API 支持 `Idempotency-Key`。
- [ ] 写操作、拒绝操作、高风险操作写 AuditLog。

## 5. Native 写 API

最小 API 闭环：

```text
POST /v1/agents
POST /v1/agents/{agent_id}/versions
POST /v1/deployments
POST /v1/deployments/{deployment_id}:activate
POST /v1/runs
POST /v1/runs/{run_id}:cancel
POST /v1/tasks
GET  /v1/runs/{run_id}/events
GET  /v1/runs/{run_id}/stream
```

要求：

- [ ] API 使用统一错误响应 schema。
- [ ] API Key / ServiceAccount auth 接入。
- [ ] tenant/project scope 校验接入。
- [ ] Policy Engine 进入 enforcement 路径，即使本阶段只实现基础规则。
- [ ] Deployment gate 生效。
- [ ] Run 创建后能进入 Task queue。
- [ ] Event `sequence` 和 `event_id` 可被 Console 和 SDK 读取。

## 6. Worker Loop

本阶段实现单节点可用的 long-running worker loop：

- [ ] 持续 lease task。
- [ ] 加载 Deployment 绑定的 AgentVersion。
- [ ] 调用 Adapter。
- [ ] 写 RunAttempt、Event、Task terminal state。
- [ ] 处理 cancel 标记。
- [ ] 处理 retryable failure。
- [ ] worker 启动时记录 heartbeat。
- [ ] worker 退出时不破坏 durable state。

注意：

- [ ] 生产级 lease reaper、fencing 跨实例、quota 和 queue partition 放到 11。
- [ ] 本阶段 worker crash 后至少能让 Task 进入可见 pending / leased / failed 状态，不追求完整自愈。

## 7. Console 真实后端接线

必须把 08 的 Runtime Control Plane Console 从 mock 数据切到真实 API：

- [ ] Dashboard 使用真实 runtime summary。
- [ ] Agents 使用真实 Agent / AgentVersion API。
- [ ] Deployments 使用真实 Deployment API。
- [ ] Compatibility 使用真实 Assistant / Thread / Run API。
- [ ] Runs / Run Detail 使用真实 Run / Event API。
- [ ] Tasks 使用真实 Task API。
- [ ] Events 使用真实 Event API。
- [ ] Human Tasks / Policies / API Keys 能读取当前后端已有 API。
- [ ] Settings 展示真实环境和 provider 配置摘要。

交互要求：

- [ ] 所有 mutation 显示 loading / success / error。
- [ ] 错误展示基于 error code，不依赖错误文本。
- [ ] 中英文文案继续覆盖新增页面和状态。
- [ ] 明暗主题不被 generated SDK 接线破坏。
- [ ] 高风险操作仍需确认。

## 8. OpenAPI / SDK

要求：

- [ ] OpenAPI 导出稳定。
- [ ] OpenAPI diff 本地脚本能比较当前文件和基线。
- [ ] breaking change 必须显式更新说明。
- [ ] Python SDK 保留 error code 和 idempotency key 支持。
- [ ] TypeScript SDK 由 OpenAPI 生成或使用 generated typed client，不手写散落类型。
- [ ] Console 只能通过统一 API client 调用后端。

## 9. CLI / DX

命令：

```text
dimoorun dev
dimoorun up
dimoorun down
dimoorun worker
dimoorun logs
dimoorun validate
dimoorun doctor
```

规则：

- [ ] `dev` 面向本地开发，优先使用 SQLite / in-process 或自动提示 compose 依赖。
- [ ] `up/down/logs` 面向 compose。
- [ ] `worker` 直接启动 worker loop。
- [ ] `doctor` 检查 Python、Node、Docker、Postgres、Redis、OpenAPI 文件。
- [ ] 命令失败时给出明确下一步，不吞异常。

## 10. 验收流程

```text
dimoorun up
  ↓
server /healthz healthy
  ↓
worker heartbeat visible
  ↓
console opens and calls server API
  ↓
create Agent
  ↓
create AgentVersion
  ↓
create Deployment and activate
  ↓
create Run
  ↓
worker executes Task
  ↓
events stream to Console
  ↓
OpenAPI export and diff pass
```

## 11. 验收清单

- [ ] Docker Compose 服务全部 healthy。
- [ ] `dimoorun dev/up/down/worker/logs` 可用。
- [ ] Postgres 存储 Run、Task、Event、AuditLog。
- [ ] Redis 用于基础队列或队列边界。
- [ ] Native Agents / Runs / Tasks 写 API 可用。
- [ ] Compatibility API 使用 durable repository。
- [ ] Console 不再依赖 mock 数据作为主路径。
- [ ] generated TypeScript SDK 或 typed client 被 Console 使用。
- [ ] OpenAPI diff check 可运行。
- [ ] 关键路径有 API / repository / console contract 测试。

命令：

```powershell
uv run pytest tests/production_foundation -q
uv run pytest tests/compat tests/cli tests/sdk -q
uv run ruff check .
uv run mypy apps/server tests scripts
npm run build
docker compose up
```

## 12. 提交建议

```text
feat: add production foundation runtime wiring
```

## 13. 设计回查清单

- [ ] 没有把 DimooRun 做成低代码 Builder。
- [ ] Console 仍是 Runtime Control Plane。
- [ ] Native API 与 Compatibility API 共存。
- [ ] Event / Trace / Audit 三账本边界没有混淆。
- [ ] 所有真实写 API 都经过 auth、tenant/project scope、Policy Engine 和 AuditLog。
- [ ] 本阶段没有提前实现 11/12 的 HA、DR、Helm、Extension 复杂能力。
