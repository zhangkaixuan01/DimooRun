# DimooRun 总执行计划

> **给执行 Agent 的要求：** 实施本计划时必须使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`。每个任务用 checkbox 跟踪，不允许跳过测试、验收和提交边界。

**目标：** 将当前设计阶段的 DimooRun 仓库，按 `DESIGN_SPEC.md` 落地为 LangChain 生态优先的企业级 Agent Runtime / Ops / Control Plane。

**总体架构：** DimooRun 分为 Control Plane、Runtime Plane、Agent Plane、Frontend Console。系统坚持“业务黑盒，运行白盒”：不接管用户 Agent 的业务智能逻辑，但完整管理 Agent 的注册、版本、部署、运行、事件、任务、权限、审计、观测、回放、评估、成本和运维。

**技术栈：** Python 3.11、FastAPI、Pydantic、SQLAlchemy、Alembic、Postgres、Redis、SSE、OpenTelemetry、Vue 3、TypeScript、Vite、Naive UI、ECharts、OpenAPI SDK、LangGraph、LangChain Agent、DeepAgents。

---

## 1. 执行计划目录

所有执行计划统一放在：

```text
execution_plans/
```

执行顺序：

```text
00-master-execution-plan.md
01-project-foundation.md
02-domain-persistence-and-api.md
03-agent-package-and-adapters.md
04-runtime-task-worker-streaming.md
05-deployment-runtime-control.md
06-governance-security-and-model-gateway.md
07-observability-replay-and-quality.md
08-console-product-plan.md
09-sdk-cli-compatibility-and-migration.md
10-enterprise-ops-and-cloud-native.md
```

执行原则：

```text
先做项目骨架，再做领域模型，再做 Adapter，再做 Runtime，再做治理和 Console。
不要先写复杂前端或企业能力，除非后端 API、OpenAPI 和运行时状态已经有稳定边界。
每个计划完成后都要能独立验收，不能只提交半成品代码。
```

当前执行状态：

| 计划 | 状态 | 说明 |
| --- | --- | --- |
| `01-project-foundation.md` | 已完成 | 项目骨架、Server、Worker、Console scaffold、基础测试已落地。 |
| `02-domain-persistence-and-api.md` | 已完成 | 领域模型、迁移、Repository、API skeleton、OpenAPI、审计/软删除契约已落地并通过验证。 |
| `03-agent-package-and-adapters.md` | 已完成 | Agent Package manifest、entrypoint loader、Adapter contract、RuntimeContext、版本治理、Conformance Kit 和三类早期 Adapter 已落地。 |
| `04-runtime-task-worker-streaming.md` | 已完成 | 状态机、幂等、InMemory TaskBackend、lease / heartbeat / retry / dead letter、fencing token、ReplayBuffer、SSE 编码、CheckpointIndex、ReplayScheduler 和 Worker fake-adapter 执行闭环已落地；Redis 命令映射保留为生产阶段边界。 |

最近完成提交：

```text
843ec0b feat: add domain persistence and api contracts
5167bb4 fix: add audit fields and soft delete semantics
d4d35f8 fix: harden domain persistence contracts
a368499 fix(persistence): harden metadata contracts
33b29a4 docs(plans): sync foundation and persistence progress
f712f67 feat(adapters): add agent package contracts
```

## 1.1 设计文档真相源规则

`execution_plans/` 不是 `DESIGN_SPEC.md` 的替代品。实现时必须同时阅读设计文档和对应执行计划。

关系定义：

```text
DESIGN_SPEC.md：
  产品和架构真相源，定义“要做成什么、边界是什么、为什么这么做”。

execution_plans/：
  施工组织设计，定义“先做什么、后做什么、每块怎么验收”。

代码实现：
  必须同时满足 DESIGN_SPEC.md 和 execution_plans/。
```

硬性规则：

- [ ] 每个执行计划开工前，必须阅读该计划列出的 `实施前必读 DESIGN_SPEC 章节`。
- [ ] 每个 Task 开始前，必须回看 Task 标注的设计章节。
- [ ] 每个计划完成前，必须执行该计划的 `设计回查清单`。
- [ ] 如果执行计划和 `DESIGN_SPEC.md` 冲突，以 `DESIGN_SPEC.md` 为准，并先更新执行计划再写代码。
- [ ] 如果实现时发现设计缺口，先补设计文档或记录明确设计决策，再继续实现。
- [ ] 不允许仅凭执行计划实现复杂模块。

## 1.2 LangChain 生态版本规则

实施 LangGraph / LangChain Agent / DeepAgents 相关任务时，必须先回看 `DESIGN_SPEC.md` 第 9.4 章。

固定测试基线：

```text
langchain      1.3.1
langchain-core 1.4.0
langgraph      1.2.1
deepagents     0.6.3
langsmith      0.8.5
```

执行规则：

- [ ] 不要求每次实施都查询最新版本。
- [ ] 默认使用本计划固定测试基线。
- [ ] 写入 lockfile，生产不使用裸 latest。
- [ ] `langchain-core` 必须显式依赖。
- [ ] `deepagents` 未到 1.0，必须锁定到测试版本。
- [ ] Adapter conformance tests 必须记录 framework version。
- [ ] 版本升级是显式维护动作，必须先更新版本矩阵并跑 conformance tests。

## 2. 设计文档覆盖矩阵

| DESIGN_SPEC 章节 | 对应执行计划 |
| --- | --- |
| 1 项目概述 | `01-project-foundation.md` |
| 2 项目定位 | `01-project-foundation.md` |
| 3 设计目标 | 全部计划，主入口 `00-master-execution-plan.md` |
| 4 非目标 | 全部计划共同遵守 |
| 5 核心边界 | 全部计划共同遵守 |
| 6 Design Guardrails | 全部计划共同遵守 |
| 7 三层架构 | `01-project-foundation.md` |
| 8 总体架构 | `01-project-foundation.md`、`02-domain-persistence-and-api.md` |
| 9 技术选型 | `01-project-foundation.md`、`08-console-product-plan.md` |
| 10 Adapter-first Agent Contract | `03-agent-package-and-adapters.md` |
| 11 Adapter Contract Versioning | `03-agent-package-and-adapters.md` |
| 11.1 Adapter Conformance Test Kit | `03-agent-package-and-adapters.md` |
| 12 Schema Migration & Data Compatibility | `02-domain-persistence-and-api.md` |
| 13 LangGraph Compatibility Mode | `09-sdk-cli-compatibility-and-migration.md` |
| 14 Agent Package 规范 | `03-agent-package-and-adapters.md` |
| 15 Project Configuration | `01-project-foundation.md`、`09-sdk-cli-compatibility-and-migration.md` |
| 16 CLI / DX | `09-sdk-cli-compatibility-and-migration.md` |
| 17 Deployment Modes | `01-project-foundation.md`、`10-enterprise-ops-and-cloud-native.md` |
| 18 Execution Isolation & Sandbox | `06-governance-security-and-model-gateway.md`、`10-enterprise-ops-and-cloud-native.md` |
| 19 RuntimeContext | `03-agent-package-and-adapters.md`、`04-runtime-task-worker-streaming.md` |
| 20 Event Model | `04-runtime-task-worker-streaming.md`、`07-observability-replay-and-quality.md` |
| 21 Streaming Runtime | `04-runtime-task-worker-streaming.md` |
| 22 核心领域模型 | `02-domain-persistence-and-api.md` |
| 23 Extended Domain Models | `02-domain-persistence-and-api.md` 和各专项计划 |
| 24 Agent Lifecycle | `03-agent-package-and-adapters.md`、`05-deployment-runtime-control.md` |
| 24.1 Deployment Runtime Control | `05-deployment-runtime-control.md` |
| 25 Migration Story | `09-sdk-cli-compatibility-and-migration.md` |
| 26 Published Runtime Surfaces | `05-deployment-runtime-control.md`、`08-console-product-plan.md` |
| 27 Component, Tool, and MCP Catalog | `06-governance-security-and-model-gateway.md` |
| 28 Prompt, Config, and Template Assets | `06-governance-security-and-model-gateway.md`、`07-observability-replay-and-quality.md` |
| 29 Runtime State Machines | `04-runtime-task-worker-streaming.md` |
| 30 Checkpoint Boundary | `03-agent-package-and-adapters.md`、`04-runtime-task-worker-streaming.md` |
| 31 Human-in-the-loop Governance | `06-governance-security-and-model-gateway.md`、`08-console-product-plan.md` |
| 32 Policy Engine | `06-governance-security-and-model-gateway.md` |
| 33 Artifact Store | `07-observability-replay-and-quality.md` |
| 33.1 Backup / Restore / DR | `10-enterprise-ops-and-cloud-native.md` |
| 34 Event / Trace / Audit 三账本 | `07-observability-replay-and-quality.md` |
| 35 Run Graph and Execution Provenance | `07-observability-replay-and-quality.md` |
| 36 Dataset, Experiment, and Quality Loop | `07-observability-replay-and-quality.md` |
| 37 存储边界 | `02-domain-persistence-and-api.md` |
| 38 API 设计 | `02-domain-persistence-and-api.md`、`09-sdk-cli-compatibility-and-migration.md` |
| 39 SDK Design | `09-sdk-cli-compatibility-and-migration.md` |
| 40 Task Scheduler | `04-runtime-task-worker-streaming.md` |
| 41 Worker Pool | `04-runtime-task-worker-streaming.md`、`05-deployment-runtime-control.md` |
| 42 HA / Scaling Design | `04-runtime-task-worker-streaming.md`、`10-enterprise-ops-and-cloud-native.md` |
| 43 权限系统 | `06-governance-security-and-model-gateway.md` |
| 44 Tool Gateway | `06-governance-security-and-model-gateway.md` |
| 45 Model Gateway / Provider Governance | `06-governance-security-and-model-gateway.md` |
| 46 Secret 管理 | `06-governance-security-and-model-gateway.md` |
| 47 可观测性 | `07-observability-replay-and-quality.md` |
| 48 前端 Console 设计 | `08-console-product-plan.md` |
| 49 评估设计 | `07-observability-replay-and-quality.md` |
| 50 插件化设计 | 全部计划按 Provider 边界实现 |
| 51 Extension API | `10-enterprise-ops-and-cloud-native.md` |
| 52 代码结构建议 | `01-project-foundation.md` |
| 53 MVP 范围 | `01`、`02`、`03`、`04`、`05`、`08`、`09` |
| 54 Roadmap | 全部计划 |
| 55 可参考开源项目 | 各计划吸收相关设计，不改变项目精髓 |
| 56 架构学习目标 | 全部计划 |
| 57 总结 | 全部计划共同遵守 |

## 3. 全局不可变原则

- [ ] 不做低代码 Agent Builder。
- [ ] 不做拖拽编排画布。
- [ ] 不设计新的 Agent DSL。
- [ ] 不接管用户 Agent 的业务 State Schema。
- [ ] 不把 Run Graph 变成编排源。
- [ ] 不把 Prompt / Config / Template 做成 Prompt 设计平台。
- [ ] 不把 Catalog 做成节点编排系统。
- [ ] 不把 New API 变成 DimooRun 的账务核心。
- [ ] 不让 Extension / Tool / Model / Secret / Compatibility API 绕过 Policy Engine。
- [ ] Adapter 早期只做 LangGraph、LangChain Agent、DeepAgents。
- [ ] Console 是 Runtime Control Plane，不是 Builder。

## 4. 全局实现质量要求

- [ ] 所有写 API 支持 `X-Request-Id`。
- [ ] 所有需要幂等的写 API 支持 `Idempotency-Key`。
- [ ] 所有写操作、拒绝操作、高风险操作写 `AuditLog`。
- [ ] 所有 API 都经过 auth、tenant/project scope、Policy Engine。
- [ ] 所有 Runtime 执行都能追溯到 `Run`、`Task`、`RunAttempt`、`Event`。
- [ ] 所有大 payload 通过 `Artifact Store` 存储引用。
- [ ] 所有流式事件有 `sequence` 和 `event_id`。
- [ ] 所有 Adapter capability 都通过 conformance tests 证明。
- [ ] 所有前端 API 类型来自 OpenAPI，不手写散落请求类型。
- [ ] 所有 Secret 不在前端、日志、Trace 明文展示。

## 4.1 全局测试分层

后续实现不能只写 API happy path。每个阶段按风险选择对应测试层级。

```text
unit tests：
  纯函数、状态机、schema、版本策略、错误码。

repository tests：
  SQLAlchemy model、migration、Repository、tenant/project scope 查询。

API contract tests：
  FastAPI route、OpenAPI schema、错误响应、Idempotency-Key、X-Request-Id。

adapter conformance tests：
  LangGraph / LangChain Agent / DeepAgents 的 invoke、stream、capability negative tests、event mapping。

worker integration tests：
  Task lease、heartbeat、retry、dead letter、fencing token、cancel、timeout。

streaming tests：
  SSE sequence、event_id、Last-Event-ID reconnect、Replay Buffer、Backpressure。

governance tests：
  Policy deny、approval required、Secret access、Tool risk、Model budget、AuditLog。

console tests：
  TypeScript typecheck、build、generated SDK type usage、关键页面状态渲染。

docker compose smoke tests：
  server、worker、console、postgres、redis、minio 健康检查。

migration tests：
  empty database upgrade、downgrade、schema compatibility、OpenAPI diff。
```

最低验收：

- [ ] 每个后端计划至少包含 unit/API/repository 中的一类测试。
- [ ] Adapter 计划必须包含 conformance tests。
- [ ] Runtime 计划必须包含 worker integration tests。
- [ ] Console 计划必须包含 typecheck 和 build。
- [ ] Enterprise 计划必须包含 compose 或 helm smoke。

## 4.2 全局错误码注册表

错误码必须稳定，前端和 SDK 不依赖错误文本判断行为。

第一批错误码：

```text
capability_not_supported
adapter_contract_incompatible
adapter_conformance_failed
manifest_invalid
package_entrypoint_not_found
deployment_not_accepting_runs
deployment_control_conflict
agent_instance_not_ready
stale_fencing_token
task_lease_expired
idempotency_conflict
stream_replay_unavailable
compatibility_not_supported
policy_denied
approval_required
secret_access_denied
model_budget_exceeded
unsupported_usage_accounting
checkpoint_incompatible
artifact_access_denied
backup_restore_validation_failed
```

实现要求：

- [ ] 错误码集中定义在后端。
- [ ] OpenAPI 暴露统一错误响应 schema。
- [ ] Python SDK / TypeScript SDK 保留 error code。
- [ ] Console 基于 error code 展示状态和动作。
- [ ] 新增错误码必须更新本注册表或后续专门错误码文档。

## 5. 目标仓库结构

```text
apps/
  server/
    dimoo_run/
      api/
      adapters/
      artifacts/
      backup/
      catalog/
      checkpoints/
      cli/
      config/
      core/
      datasets/
      deployments/
      evals/
      extensions/
      gateway/
      governance/
      hitl/
      identity/
      memory/
      migration/
      model_gateway/
      notifications/
      observability/
      packages/
      persistence/
      policy/
      prompts/
      replay/
      run_graph/
      runtime/
      sandbox/
      scheduler/
      secrets/
      streaming/
      tools/
      worker/
  worker/
  console/
packages/
  sdk-python/
  sdk-js/
examples/
  langgraph/
  compatibility/
execution_plans/
openapi/
deploy/
tests/
```

## 6. 阶段验收主线

### 6.1 Dev MVP 验收

- [ ] `dimoorun dev` 能启动 server、worker、基础 Console。
- [ ] 可以注册 LangGraph Agent Package。
- [ ] 可以创建 AgentVersion。
- [ ] 可以创建 Deployment 并 activate。
- [ ] 可以通过 Native API 创建 Run/Task。
- [ ] Worker 可以执行 LangGraphAdapter。
- [ ] Console 能查看 Agents、Deployments、Runs、Tasks、Events、API Keys。
- [ ] SSE event 包含 `sequence` 和 `event_id`。
- [ ] 重复 `Idempotency-Key` 不产生多个业务结果。

### 6.2 Runtime MVP 验收

- [ ] Docker Compose 启动 server、worker、console、postgres、redis。
- [ ] Redis Queue 支持 lease、heartbeat、retry、dead letter。
- [ ] Postgres 存储 Run、Task、Event、AuditLog。
- [ ] Compatibility API 支持 assistants / threads / runs 核心调用。
- [ ] Worker 崩溃后任务可恢复或进入可见失败状态。
- [ ] Deployment pause/resume/restart/drain/stop 语义可验证。

### 6.3 Phase 2 验收

- [ ] LangChain Agent 和 DeepAgents Adapter 可执行。
- [ ] Adapter Conformance Test Kit 覆盖 invoke、stream、capability negative tests。
- [ ] Debug / Replay 可从失败 Run 创建新 Run。
- [ ] OpenTelemetry、Langfuse / Phoenix 接口边界可用。
- [ ] ServiceAccount 可调用 Runtime API。
- [ ] OpenAPI diff check 可阻止未声明 breaking change。

### 6.4 Enterprise Ops 验收

- [ ] Tool Gateway 支持高风险审批。
- [ ] Model Gateway 接入 New API / OpenAI-compatible endpoint。
- [ ] Notification / Alerting 可触发 incident。
- [ ] Backup dry-run restore 可验证。
- [ ] Helm chart 可 render。
- [ ] Worker 可水平扩容并消化队列积压。

## 7. 执行方式

推荐：

```text
Subagent-Driven：
每个执行计划拆成多个独立任务，由子 Agent 实施；
主 Agent 在每个任务后 review diff、运行测试、确认边界。
```

备选：

```text
Inline Execution：
当前会话按计划逐步实现；
每完成一个 Task 做 checkpoint、测试和提交。
```

## 8. 当前不进入实现范围

- [ ] CrewAIAdapter。
- [ ] LlamaIndexAdapter。
- [ ] SemanticKernelAdapter。
- [ ] 低代码画布。
- [ ] Prompt 设计器。
- [ ] 完整计费充值系统。
- [ ] 完整组织架构和复杂 ABAC。
- [ ] 多区域生产部署。
- [ ] Custom Routes 的开放式后端扩展。

这些能力如果以后要做，必须重新评审是否仍符合 DimooRun 的项目精髓。
