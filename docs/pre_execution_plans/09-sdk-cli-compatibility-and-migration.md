# 09 SDK、CLI、Compatibility 与迁移执行计划

> **给执行 Agent 的要求：** Compatibility API 是迁移入口，不是 DimooRun 主语义。所有兼容调用仍必须落到 Run / Task / Event / AuditLog。

**目标：** 实现 `dimoorun` CLI、Python SDK、TypeScript SDK 生成、LangGraph Compatibility API、Agent Protocol 兼容边界、`manifest.yaml` / `dimoorun.yaml` 配置模型和迁移工具。

**架构说明：** Native API 是平台真实语义。Compatibility API 只负责把 LangGraph assistants / threads / runs / stream 映射到 DimooRun 的 Deployment / Session / Run / Task / Streaming / CheckpointIndex。

**设计覆盖：** `DESIGN_SPEC.md` 第 13、15、16、25、38.7、38.9、39 章。

---

## 实施结果

- [x] 已实现 `dimoo_run.config.project`，覆盖 `dimoorun.yaml` 的 project、agents、adapters、deployments、execution_profiles、model_gateways、policies、observability、storage。
- [x] 已实现 `dimoorun` CLI entrypoint，并支持 `init`、`validate`、`doctor`、`migrate langgraph`、`migrate aegra`、`migrate langgraph-platform`。
- [x] `doctor` 输出固定 LangChain 生态版本矩阵和当前安装版本。
- [x] `validate` 会加载 `dimoorun.yaml` 和 Agent `manifest.yaml`，并验证 agent path、entrypoint module file、entrypoint function 与 manifest 错误。
- [x] `manifest.yaml` 明确拒绝在 `required_secrets` 中写入明文 secret。
- [x] 已实现 `/compat/langgraph` 核心 assistants / threads / runs / cancel / join / stream 路由。
- [x] Compatibility API 使用真实 API Key 校验、Tenant / Project scope header 和 `agent:invoke` scope，不允许无认证或伪 Bearer 访问。
- [x] Compatibility runs 通过 `RunManager` / `TaskBackend` 创建 DimooRun Run / Task；cancel / join / stream 会同步 DimooRun Run / Task 状态，追加 ReplayBuffer runtime events，并写入 AuditLog。
- [x] Compatibility stream 返回 SSE `text/event-stream`，包含稳定 `id` / `event` / `data` 结构；当前可输出 `run.created` / `task.queued` / `run.started` 等 runtime 事件，重连 replay 留给后续生产化。
- [x] 已实现 `/compat/agent-protocol/capabilities` skeleton，并声明 `compatibility_not_supported`。
- [x] 已实现 LangGraph best-effort migration，优先读取 `langgraph.json`，检测多 graph、依赖、env file、checkpoint / store backend，生成 `manifest.yaml`、`dimoorun.yaml`、`migration_report.md` 和 checkpoint / multi-graph compatibility warning。
- [x] Aegra / LangGraph Platform 迁移入口会生成来源专属报告和人工复核 warning，避免把深度迁移伪装成普通 LangGraph 迁移。
- [x] 已新增最小 Native API 闭环：进程内 Agents / AgentVersions / Runs / Tasks runtime store，支持创建 Agent、创建 AgentVersion、创建 Run/Task、读取 Run/Task/Event、cancel Run/Task、`Idempotency-Key` 复用与冲突检测。
- [x] 已新增 Python SDK 基础客户端，错误类型保留 `error_code`、`request_id`、`details`，支持 caller-supplied / per-request idempotency key，并通过 FastAPI Native API 集成测试验证可创建 Run。
- [x] 已创建 TypeScript SDK 目录和生成 SDK 边界说明。
- [x] Console 新增 `nativeConsoleClient` 和 `VITE_DIMOORUN_API_BASE_URL` / tenant / project 环境变量边界；页面默认 mock 主路径和 generated SDK 主路径仍留给 10 阶段收敛。
- [x] 已新增 `tests/cli`、`tests/compat`、`tests/migration`、`tests/sdk` 覆盖 09 MVP。

暂缓到后续阶段：

- [ ] `dev` / `worker` / `up` / `down` 的真实进程编排。
- [ ] `package` / `deploy` / `logs` / `console` 的完整命令实现。
- [ ] TypeScript SDK 从 OpenAPI 自动生成。
- [ ] OpenAPI diff CI 和 backward compatibility gate。
- [ ] Native API / Compatibility API 与持久化 Repository / EventLog / PolicyEngine 的生产级接线。
- [ ] Console 真实后端 API 作为主路径，替代 mock-first 页面数据。
- [ ] Agent Protocol 更完整协议细节。
- [ ] Aegra / LangGraph Platform 的深度配置迁移、custom routes / hosted deployment 细节迁移和 checkpoint 数据迁移。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 9.4 章：LangChain Ecosystem Version Policy。
- [x] 第 13 章：LangGraph Compatibility Mode。
- [x] 第 15 章：Project Configuration。
- [x] 第 16 章：CLI / Developer Experience。
- [x] 第 25 章：Migration Story。
- [x] 第 38.7 章：LangGraph Compatibility API。
- [x] 第 38.9 章：API Contract Governance。
- [x] 第 39 章：SDK Design。

## 1. 文件规划

```text
apps/server/dimoo_run/cli/main.py
apps/server/dimoo_run/config/project.py
apps/server/dimoo_run/api/compat/langgraph.py
apps/server/dimoo_run/api/compat/agent_protocol.py
apps/server/dimoo_run/migration/langgraph.py
apps/server/dimoo_run/migration/aegra.py
apps/server/dimoo_run/migration/langgraph_platform.py
packages/sdk-python/dimoorun/__init__.py
packages/sdk-python/dimoorun/client.py
packages/sdk-js/
tests/cli/
tests/compat/
tests/migration/
```

## 2. manifest.yaml

字段：

```text
name
version
schema_version
runtime.framework
runtime.adapter
runtime.entrypoint
runtime.python
capabilities
dependencies
required_secrets
security
metadata
```

校验：

- [x] schema_version 必填或可推断。
- [x] runtime.framework 只能是早期支持范围：langgraph、langchain-agent、deepagents。
- [x] adapter 与 framework 匹配。
- [x] entrypoint 格式为 `module:function`。
- [x] capabilities 与 Adapter 支持范围匹配。
- [x] required_secrets 不包含明文。

## 3. dimoorun.yaml

字段：

```text
project
agents
adapters
deployments
execution_profiles
model_gateways
policies
observability
storage
```

示例能力：

- [x] project.name。
- [x] project.tenant。
- [x] agents 列表。
- [x] adapters.langgraph.enabled。
- [x] deployments.dev / prod。
- [x] execution_profiles.local-dev / prod-worker。
- [x] model_gateways.default。
- [x] policies.tool_approval。
- [x] observability.langfuse。
- [x] storage.metadata / queue / object_store。

## 4. CLI 命令

MVP 命令：

```text
dimoorun init
dimoorun dev
dimoorun validate
dimoorun worker
dimoorun up
dimoorun down
dimoorun doctor
```

Phase 2 命令：

```text
dimoorun package
dimoorun deploy
dimoorun migrate
dimoorun logs
dimoorun console
```

命令语义：

- [x] `init` 生成最小目录、manifest、dimoorun.yaml。
- [ ] `dev` 启动 server、worker、基础 Console。
- [x] `validate` 校验 manifest、配置、entrypoint、capability、secret 引用。
- [ ] `worker` 启动 Worker。
- [ ] `up` 启动 Docker Compose。
- [ ] `down` 停止 Docker Compose。
- [ ] `doctor` 检查 Python、uv、依赖、配置、端口、数据库、Redis。
- [x] `doctor` 检查 LangChain 生态包版本是否符合固定测试矩阵。
- [x] `doctor` 输出 langchain、langchain-core、langgraph、deepagents、langsmith 的实际安装版本。
- [ ] `package` 生成 Agent Package 和 hash。
- [ ] `deploy` 创建 AgentVersion / Deployment。
- [ ] `logs` 查看 server / worker 日志。
- [ ] `console` 打开 Console URL。

## 5. Python SDK

职责：

```text
注册 Agent Package
创建 Run / Task
读取 Run / Event / Artifact
stream SSE events
resume / cancel / retry
调用 Compatibility API
```

SDK 规则：

- [ ] 不隐藏平台状态机。
- [ ] 暴露 request_id、run_id、task_id、event_id。
- [x] 错误类型保留平台 error code。
- [x] `create_run` 可调用 Native `/v1/agents/{agent_id}/tasks`，并通过 FastAPI 集成测试验证。
- [ ] stream client 支持 Last-Event-ID。

## 6. TypeScript SDK

来源：

```text
openapi/dimoorun.openapi.json
```

手写层只封装：

- [ ] auth header 注入。
- [ ] SSE reconnect。
- [ ] Last-Event-ID。
- [ ] cursor pagination。
- [ ] typed error handling。

当前状态：

- [x] 已保留 `packages/sdk-js/README.md` 作为生成式 TypeScript SDK 边界说明。
- [x] Console 侧已有手写 `nativeConsoleClient`，可按环境变量调用 Native API。
- [ ] 仍未从 OpenAPI 生成正式 TypeScript SDK，也未将 Console 默认主路径切到 generated SDK。

## 7. LangGraph Compatibility API

路由：

```http
POST /compat/langgraph/assistants
GET  /compat/langgraph/assistants
GET  /compat/langgraph/assistants/{assistant_id}
POST /compat/langgraph/threads
GET  /compat/langgraph/threads/{thread_id}
POST /compat/langgraph/threads/{thread_id}/runs
GET  /compat/langgraph/threads/{thread_id}/runs/{run_id}
POST /compat/langgraph/threads/{thread_id}/runs/{run_id}/cancel
POST /compat/langgraph/threads/{thread_id}/runs/{run_id}/join
POST /compat/langgraph/threads/{thread_id}/runs/stream
```

映射：

```text
assistant_id -> Deployment / AgentVersion
thread_id -> Session.thread_id / CheckpointIndex.thread_id
run_id -> Run.id (internal numeric ID, serialized as a path segment for LangGraph-compatible routes)
stream -> Streaming Runtime
checkpoint -> Framework Runtime Store + CheckpointIndex
```

约束：

- [x] Compatibility API 不绕过 API Key。
- [x] 不绕过 Tenant / Project scope。
- [x] 对已存在 Deployment 不绕过 Deployment Gate / Policy 边界；完整 PolicyEngine 持久化接线留给生产化阶段。
- [x] 不绕过 AuditLog。
- [x] 不支持的 LangGraph Platform 特性返回 `compatibility_not_supported`。
- [x] 返回结构尽量保持 LangGraph SDK 兼容。
- [x] 内部状态以 DimooRun 状态机为准。

Golden tests：

- [x] assistants create/list/get。
- [x] threads create/get。
- [x] runs create/get/join/cancel。
- [x] runs stream。
- [x] unsupported feature error。

## 8. Agent Protocol 兼容边界

- [x] 路由挂 `/compat/agent-protocol`。
- [x] 第一版只实现 skeleton 和能力声明。
- [x] 不支持能力返回稳定 error code。
- [ ] 仍然经过 auth、Policy、AuditLog。

## 9. Migration Story

命令：

```text
dimoorun migrate langgraph ./my-agent
dimoorun migrate aegra ./aegra-project
dimoorun migrate langgraph-platform ./langgraph.json
dimoorun migrate langchain-agent ./my-agent
```

迁移能力：

```text
自动识别 graph entrypoint
生成 manifest.yaml
生成 dimoorun.yaml
检测 capabilities
检测 checkpoint backend
检测 store backend
检测 Python 依赖
检测环境变量和 Secret 引用
提示不可自动迁移项
生成 compatibility_warnings
生成 migration_report.md
```

Checkpoint 迁移原则：

- [x] best-effort。
- [x] 不保证历史 checkpoint 无损迁移。
- [x] 不可迁移时仍允许迁移 Agent Package 和新 Run。
- [x] `checkpoint_incompatible` 必须说明原因。

## 10. API Contract Governance

必须实现：

- [x] OpenAPI schema 可由 `scripts/export_openapi.py` 导出，并已同步 `openapi/dimoorun.openapi.json`。
- [ ] OpenAPI diff check。
- [ ] backward compatibility tests。
- [x] Compatibility API golden tests。
- [ ] SDK version matrix。
- [ ] deprecated endpoint policy。
- [x] error code registry。

规则：

- [ ] API breaking change 提升 `api_schema_version`。
- [ ] Compatibility breaking change 提升 `compat_api_version`。
- [ ] CI 阻止未声明 breaking change。

错误码契约：

- [x] SDK 必须保留 `error_code`。
- [x] SDK 不把所有错误折叠成普通异常文本。
- [x] Compatibility API 错误码必须稳定，尤其是 `compatibility_not_supported`。
- [ ] OpenAPI 中必须完整描述所有错误响应。

## 11. 验收清单

- [x] `dimoorun doctor` 能输出 LangChain 生态版本。
- [x] `dimoorun init` 生成配置。
- [x] `dimoorun validate` 能发现 entrypoint 错误。
- [x] Python SDK 可创建 Run。
- [x] Native API 可创建 Agent / AgentVersion / Run / Task，并支持幂等复用和冲突检测。
- [ ] TS SDK 可由 OpenAPI 生成。
- [x] Compatibility API 能完成 assistants / threads / runs。
- [x] Compatibility stream 使用 ReplayBuffer + SSE，并支持 event_id / sequence。
- [x] migration 可生成 manifest / dimoorun.yaml / report。

命令：

```bash
uv run pytest tests/cli tests/compat tests/migration tests/sdk tests/api/test_native_api.py -q
```

## 12. 提交建议

```text
feat: add cli sdk compatibility and migration
```

## 13. 设计回查清单

- [x] Compatibility API 目标和约束符合第 13 章。
- [x] `dimoorun.yaml` 字段覆盖第 15 章。
- [x] CLI 命令覆盖第 16 章。
- [x] Migration 来源、能力、输出、checkpoint 原则覆盖第 25 章。
- [x] Compatibility API 路由和映射覆盖第 38.7 章。
- [ ] OpenAPI diff、SDK version matrix、error code registry 覆盖第 38.9 章。
- [x] Python SDK / TypeScript SDK 原则覆盖第 39 章。
