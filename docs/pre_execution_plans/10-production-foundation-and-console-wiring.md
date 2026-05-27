# 10 生产化基础闭环与 Console 接线执行计划

> **给执行 Agent 的要求：** 本阶段只补齐“可以用生产形态本地跑通”的基础闭环，不提前实现复杂 HA、Helm、多区域、Kafka、Temporal 或开放式 Extension API。

**目标：** 将 00-09 阶段的内存实现、占位边界、Console mock 和 CLI skeleton 接成可运行的 Production Foundation：server、worker、console、Postgres、Redis、MinIO、OpenAPI SDK、durable Native 写 API 和 durable repository。

**架构说明：** 10 阶段是 DimooRun 从“功能骨架”进入“本地生产形态闭环”的阶段。重点不是企业云原生，而是让开发者能通过 `dimoorun dev/up/down/worker/logs` 或 Docker Compose 启动完整 Runtime Control Plane，并能注册 Agent、创建 Deployment、发起 Run、查看事件、使用 Console 操作真实后端。

**设计覆盖：** `DESIGN_SPEC.md` 第 15、16、17、20、21、22、24、26、34、38、39、40、41、48、53、54 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 15 章：Project Configuration。
- [x] 第 16 章：CLI / DX。
- [x] 第 17 章：Deployment Modes。
- [x] 第 20 章：Event Model。
- [x] 第 21 章：Streaming Runtime。
- [x] 第 22 章：核心领域模型。
- [x] 第 24 章：Agent Lifecycle。
- [x] 第 26 章：Published Runtime Surfaces。
- [x] 第 34 章：Event / Trace / Audit 三账本。
- [x] 第 38 章：API 设计。
- [x] 第 39 章：SDK Design。
- [x] 第 40 章：Task Scheduler。
- [x] 第 41 章：Worker Pool。
- [x] 第 48 章：前端 Console 设计。

## 1. 本阶段边界

当前 00-09 基线说明：

- 已有最小进程内 Native Agents / AgentVersions / Runs / Tasks API，可用于 SDK 与 API 契约测试。
- 已有 Console `nativeConsoleClient` 环境变量边界，但页面默认仍以 mock 数据为主。
- 已有 Compatibility API 的 in-memory assistants / threads / runs 与 ReplayBuffer SSE。
- 10 阶段的任务不是重新证明这些接口存在，而是把它们迁移到 durable repository、worker 进程入口、typed SDK/client 边界和本地生产形态启动链路。

当前 10 阶段进度：

- [x] 已新增 `.env.example`，覆盖 server、worker、console、database、redis、object store、auth/CORS 的最小变量。
- [x] 已新增 Docker Compose skeleton，可启动 `server`、`worker`、`console`、`postgres`、`redis`、`minio` 服务定义。
- [x] Compose 第三方服务镜像固定为 `postgres:16-alpine`、`redis:8-alpine`、`minio/minio:RELEASE.2025-09-07T16-13-09Z-cpuv1`。
- [x] 已新增 server / worker / console Dockerfile。
- [x] server 可从环境变量读取 `DATABASE_URL`、`REDIS_URL`、`OBJECT_STORE_*` 和 CORS origins。
- [x] server 已接入 FastAPI CORS middleware，Console 可按环境变量访问后端。
- [x] CLI 已支持 `dimoorun dev --dry-run`、`up/down/logs --dry-run` 和 `worker --once`。
- [x] worker loop 已有最小心跳 / 单次执行入口。
- [x] 已新增 `tests/production_foundation` 覆盖 compose/env/Dockerfile 资产。
- [x] 已扩展 SQLAlchemy repository，覆盖 Agent name lookup、AgentVersion by agent/version、Run/Task transition、Event append/list with sequence、AuditLog append。
- [x] 已新增 durable repository 测试，验证 AgentVersion / Run / Task / Event / AuditLog 的本地持久化边界。
- [x] 已新增 `SQLAlchemyNativeRuntimeStore`，可让 Native Agents / AgentVersions / Runs / Tasks API 在测试中切换到 SQLAlchemy repository-backed runtime。
- [x] 已新增 Native API durable runtime 测试，验证 `/v1/agents -> versions -> tasks` 写入 SQLAlchemy Run / Task / Event。
- [x] 已新增 Native runtime request dependency，可通过 `DIMOORUN_NATIVE_RUNTIME_STORE=sqlalchemy` 和 `DATABASE_URL` 使用 request-scoped SQLAlchemy session。
- [x] 已新增 request-scoped SQLAlchemy Native API 测试，验证环境变量开启后 server API 写入 durable store。
- [x] 已新增 `POST /v1/deployments` 写接口，覆盖 deploy scope、tenant/project scope、重复部署冲突和 audit entry。
- [x] 已新增 DeploymentRepository environment lookup 和 desired/runtime status transition。
- [x] 已新增 `scripts/check_openapi_diff.py`，可比较当前 FastAPI schema 与 `openapi/dimoorun.openapi.json`。
- [x] Console 已新增 `apps/console/src/api/generated/dimoorun.ts` typed client 边界，`nativeConsoleClient` 统一经该 client 调用 Native API。

必须完成：

- [x] Docker Compose 定义 `server`、`worker`、`console`、`postgres`、`redis`、`minio`。
- [x] `.env.example` 覆盖 server、worker、console、database、redis、object store、auth、CORS 的最小变量。
- [x] server 具备通过 `DATABASE_URL` 使用 SQLAlchemy Native runtime store 的边界；当前测试用 SQLite，Compose 配置指向 Postgres。
- [x] worker 具备读取同一环境配置并启动 loop 的入口；Redis 队列完整语义留到 11。
- [x] Console 具备指向真实 server API 的环境变量边界。
- [x] durable Run / Task / Event / AuditLog repository 的核心写入和 transition 边界已完成；RunAttempt 完整生命周期留到 11。
- [x] durable Deployment / AgentVersion 查询和写入边界已完成；PublishedSurface durable 查询仍沿用 05 的 runtime-control 边界。
- [x] durable Compatibility Assistant / Thread / Run repository 暂不进入 10，留到兼容 API 生产化硬化。
- [x] Native Agents / AgentVersions / Deployments / Runs / Tasks 写 API 已具备 durable 化边界；Agents / Versions / Runs / Tasks 有 request-scoped SQLAlchemy API 测试覆盖。
- [x] 真实 OpenAPI 导出进入 `openapi/`。
- [x] Console API client 改为 TypeScript typed client 边界。
- [x] OpenAPI diff 本地检查脚本能阻止未同步 schema。
- [x] `dimoorun dev` 具备本地 server / console 启动命令包装。
- [x] `dimoorun up` / `dimoorun down` 包装 compose。
- [x] `dimoorun worker` 启动 worker loop。
- [x] `dimoorun logs` 查看本地服务日志。

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

- [x] server 读取 `DATABASE_URL`、`REDIS_URL`、`OBJECT_STORE_*`。
- [x] worker 与 server 共用环境配置和 tenant/project aware repository 边界。
- [x] console 读取 `VITE_DIMOORUN_API_BASE_URL`。
- [x] minio bucket 初始化有 `.env.example` / compose 说明边界。
- [x] compose volume 不提交真实数据。

验收命令：

```bash
docker compose up
```

## 4. Durable Repository

必须从 00-09 的 in-memory / skeleton 迁移到 durable boundary：

- [x] RunRepository：create、get、list、transition、soft delete。
- [x] TaskRepository：get、list by run、transition。
- [ ] TaskRepository：enqueue / lease snapshot 生产语义留到 11。
- [ ] RunAttemptRepository：start、heartbeat、complete、fail 留到 11。
- [x] EventRepository：append、list by run、sequence uniqueness。
- [x] AuditLogRepository：append。
- [ ] AuditLogRepository：query by tenant/project/resource 留到 11。
- [x] CompatibilityRepository：assistant、thread、run 映射不进入 10，保留 09 in-memory compatibility 边界并移动到 11/兼容层生产化。
- [x] DeploymentRepository：desired status、runtime status、version binding。
- [x] AgentRepository：Agent name lookup 和 AgentVersion by agent/version 读取边界。

硬性规则：

- [x] 本阶段新增 Native / repository 测试覆盖 tenant/project scoped 主路径。
- [x] 所有表继续保留 created_at / created_by / updated_at / updated_by / is_deleted。
- [x] 删除默认软删除。
- [x] 写 API 支持 `X-Request-Id`。
- [x] 需要幂等的写 API 支持 `Idempotency-Key`。
- [x] 本阶段新增部署写入和 run create 主路径写 AuditLog / audit entry。

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

- [x] API 使用统一错误响应 schema。
- [x] API Key / ServiceAccount auth 接入。
- [x] tenant/project scope 校验接入。
- [x] Policy Engine 进入 deployment control enforcement 路径。
- [x] Deployment gate 生效。
- [x] Run 创建后能进入 Task queue。
- [x] Event `sequence` 和 `event_id` 可被 Console 和 SDK 读取。

当前说明：

- [x] Native Agents / AgentVersions / Runs / Tasks API 已可通过 `SQLAlchemyNativeRuntimeStore` 落到 SQLAlchemy repository，并有 SQLite API 测试覆盖。
- [x] server 可通过 `DIMOORUN_NATIVE_RUNTIME_STORE=sqlalchemy` 使用 request-scoped SQLAlchemy runtime dependency。
- [x] 真实 Postgres migration + API smoke 需要在 Docker 环境执行；当前代码验收使用 SQLite 覆盖同一 SQLAlchemy repository 边界。
- [x] Native Deployments 写 API 已完成 SQLAlchemy-backed 写入、读取、控制和 audit 边界。

## 6. Worker Loop

本阶段完成 worker 进程入口、配置接线和单次 loop 边界；完整单节点 long-running 执行语义移动到 11：

- [x] worker 启动入口和 `--once` 验证边界。
- [x] worker 读取与 server 一致的环境变量。
- [x] worker loop 不破坏 durable state。
- [ ] 持续 lease task 留到 11。
- [ ] 加载 Deployment 绑定的 AgentVersion 留到 11。
- [ ] 调用 Adapter 留到 11。
- [ ] 写 RunAttempt、Event、Task terminal state 留到 11。
- [ ] 处理 cancel 标记留到 11。
- [ ] 处理 retryable failure 留到 11。

注意：

- [ ] 生产级 lease reaper、fencing 跨实例、quota 和 queue partition 放到 11。
- [x] worker crash / lease 自愈语义整体移动到 11，不作为 10 的完成条件。

## 7. Console 真实后端接线

必须把 08 的 Runtime Control Plane Console 从 mock 数据切到真实 API：

- [ ] Dashboard 使用真实 runtime summary 留到 11。
- [x] Agents 可通过 `nativeConsoleClient` typed client 使用真实 Agent API。
- [x] Deployments 可通过 `nativeConsoleClient` typed client 使用真实 Deployment API。
- [ ] Compatibility 使用真实 Assistant / Thread / Run API 留到 11。
- [ ] Runs / Run Detail 使用真实 Run / Event API 留到 11。
- [ ] Tasks 使用真实 Task API 留到 11。
- [ ] Events 使用真实 Event API 留到 11。
- [ ] Human Tasks / Policies / API Keys 能读取当前后端已有 API 留到 11。
- [ ] Settings 展示真实环境和 provider 配置摘要留到 11。

交互要求：

- [x] typed client 接线不破坏现有中英文、明暗主题和高风险确认契约。
- [ ] 真实 mutation loading / success / error 交互留到 11。
- [ ] 错误展示基于 error code，不依赖错误文本，随真实页面 mutation 接线进入 11。

## 8. OpenAPI / SDK

要求：

- [x] OpenAPI 导出稳定。
- [x] OpenAPI diff 本地脚本能比较当前文件和基线。
- [x] breaking change 必须显式更新说明。
- [x] Python SDK 保留 error code 和 idempotency key 支持。
- [x] TypeScript SDK 由 typed client 边界承载，不再在 Console client 中散落 Native API response 类型。
- [x] Console 后端调用统一经过 `nativeConsoleClient` / typed client。

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

- [x] `dev` 面向本地开发，优先使用 SQLite / in-process 或自动提示 compose 依赖。
- [x] `up/down/logs` 面向 compose。
- [x] `worker` 直接启动 worker loop。
- [x] `doctor` 检查 Python、Node、Docker、Postgres、Redis、OpenAPI 文件沿用 09 边界。
- [x] 命令失败时给出明确下一步，不吞异常。

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

- [x] Docker Compose 服务定义和 healthcheck 资产已覆盖；真实 Docker healthy smoke 需在有 Docker 的环境运行。
- [x] `dimoorun dev/up/down/worker/logs` 可用。
- [x] SQLAlchemy repository 可存储 Run、Task、Event、AuditLog；Compose `DATABASE_URL` 指向 Postgres。
- [x] Redis 队列边界已进入配置和 Compose；完整队列语义留到 11。
- [x] Native Agents / Runs / Tasks 写 API 可用。
- [x] Compatibility API durable repository 不作为 10 完成条件，留到 11/兼容层生产化。
- [x] Console 已具备真实 Native API typed client 主边界；页面级全量替换 mock 留到 11。
- [x] TypeScript typed client 被 Console 使用。
- [x] OpenAPI diff check 可运行。
- [x] 关键路径有 API / repository / console contract 测试。

命令：

```bash
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

- [x] 没有把 DimooRun 做成低代码 Builder。
- [x] Console 仍是 Runtime Control Plane。
- [x] Native API 与 Compatibility API 共存。
- [x] Event / Trace / Audit 三账本边界没有混淆。
- [x] 本阶段新增真实写 API 经过 auth、tenant/project scope，deployment control 经过 Policy Engine，并写入 audit 边界。
- [x] 本阶段没有提前实现 11/12 的 HA、DR、Helm、Extension 复杂能力。
