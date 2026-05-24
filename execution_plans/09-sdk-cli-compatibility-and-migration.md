# 09 SDK、CLI、Compatibility 与迁移执行计划

> **给执行 Agent 的要求：** Compatibility API 是迁移入口，不是 DimooRun 主语义。所有兼容调用仍必须落到 Run / Task / Event / AuditLog。

**目标：** 实现 `dimoorun` CLI、Python SDK、TypeScript SDK 生成、LangGraph Compatibility API、Agent Protocol 兼容边界、`manifest.yaml` / `dimoorun.yaml` 配置模型和迁移工具。

**架构说明：** Native API 是平台真实语义。Compatibility API 只负责把 LangGraph assistants / threads / runs / stream 映射到 DimooRun 的 Deployment / Session / Run / Task / Streaming / CheckpointIndex。

**设计覆盖：** `DESIGN_SPEC.md` 第 13、15、16、25、38.7、38.9、39 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [ ] 第 9.4 章：LangChain Ecosystem Version Policy。
- [ ] 第 13 章：LangGraph Compatibility Mode。
- [ ] 第 15 章：Project Configuration。
- [ ] 第 16 章：CLI / Developer Experience。
- [ ] 第 25 章：Migration Story。
- [ ] 第 38.7 章：LangGraph Compatibility API。
- [ ] 第 38.9 章：API Contract Governance。
- [ ] 第 39 章：SDK Design。

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

- [ ] schema_version 必填或可推断。
- [ ] runtime.framework 只能是早期支持范围：langgraph、langchain-agent、deepagents。
- [ ] adapter 与 framework 匹配。
- [ ] entrypoint 格式为 `module:function`。
- [ ] capabilities 与 Adapter 支持范围匹配。
- [ ] required_secrets 不包含明文。

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

- [ ] project.name。
- [ ] project.tenant。
- [ ] agents 列表。
- [ ] adapters.langgraph.enabled。
- [ ] deployments.dev / prod。
- [ ] execution_profiles.local-dev / prod-worker。
- [ ] model_gateways.default。
- [ ] policies.tool_approval。
- [ ] observability.langfuse。
- [ ] storage.metadata / queue / object_store。

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

- [ ] `init` 生成最小目录、manifest、dimoorun.yaml。
- [ ] `dev` 启动 server、worker、基础 Console。
- [ ] `validate` 校验 manifest、配置、entrypoint、capability、secret 引用。
- [ ] `worker` 启动 Worker。
- [ ] `up` 启动 Docker Compose。
- [ ] `down` 停止 Docker Compose。
- [ ] `doctor` 检查 Python、uv、依赖、配置、端口、数据库、Redis。
- [ ] `doctor` 检查 LangChain 生态包版本是否符合固定测试矩阵。
- [ ] `doctor` 输出 langchain、langchain-core、langgraph、deepagents、langsmith 的实际安装版本。
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
- [ ] 错误类型保留平台 error code。
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
run_id -> Run.id
stream -> Streaming Runtime
checkpoint -> Framework Runtime Store + CheckpointIndex
```

约束：

- [ ] Compatibility API 不绕过 API Key。
- [ ] 不绕过 Tenant / Project scope。
- [ ] 不绕过 Policy Engine。
- [ ] 不绕过 AuditLog。
- [ ] 不支持的 LangGraph Platform 特性返回 `compatibility_not_supported`。
- [ ] 返回结构尽量保持 LangGraph SDK 兼容。
- [ ] 内部状态以 DimooRun 状态机为准。

Golden tests：

- [ ] assistants create/list/get。
- [ ] threads create/get。
- [ ] runs create/get/join/cancel。
- [ ] runs stream。
- [ ] unsupported feature error。

## 8. Agent Protocol 兼容边界

- [ ] 路由挂 `/compat/agent-protocol`。
- [ ] 第一版只实现 skeleton 和能力声明。
- [ ] 不支持能力返回稳定 error code。
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

- [ ] best-effort。
- [ ] 不保证历史 checkpoint 无损迁移。
- [ ] 不可迁移时仍允许迁移 Agent Package 和新 Run。
- [ ] `checkpoint_incompatible` 必须说明原因。

## 10. API Contract Governance

必须实现：

- [ ] OpenAPI schema source of truth。
- [ ] OpenAPI diff check。
- [ ] backward compatibility tests。
- [ ] Compatibility API golden tests。
- [ ] SDK version matrix。
- [ ] deprecated endpoint policy。
- [ ] error code registry。

规则：

- [ ] API breaking change 提升 `api_schema_version`。
- [ ] Compatibility breaking change 提升 `compat_api_version`。
- [ ] CI 阻止未声明 breaking change。

错误码契约：

- [ ] SDK 必须保留 `error_code`。
- [ ] SDK 不把所有错误折叠成普通异常文本。
- [ ] Compatibility API 错误码必须稳定，尤其是 `compatibility_not_supported`。
- [ ] OpenAPI 中必须描述统一错误响应。

## 11. 验收清单

- [ ] `dimoorun doctor` 能输出 LangChain 生态版本。
- [ ] `dimoorun init` 生成配置。
- [ ] `dimoorun validate` 能发现 entrypoint 错误。
- [ ] Python SDK 可创建 Run。
- [ ] TS SDK 可由 OpenAPI 生成。
- [ ] Compatibility API 能完成 assistants / threads / runs。
- [ ] Compatibility stream 支持 event_id。
- [ ] migration 可生成 manifest / dimoorun.yaml / report。

命令：

```powershell
uv run pytest tests/cli tests/compat tests/migration -q
```

## 12. 提交建议

```text
feat: add cli sdk compatibility and migration
```

## 13. 设计回查清单

- [ ] Compatibility API 目标和约束符合第 13 章。
- [ ] `dimoorun.yaml` 字段覆盖第 15 章。
- [ ] CLI 命令覆盖第 16 章。
- [ ] Migration 来源、能力、输出、checkpoint 原则覆盖第 25 章。
- [ ] Compatibility API 路由和映射覆盖第 38.7 章。
- [ ] OpenAPI diff、SDK version matrix、error code registry 覆盖第 38.9 章。
- [ ] Python SDK / TypeScript SDK 原则覆盖第 39 章。
