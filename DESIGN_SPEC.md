# DimooRun DESIGN_SPEC

> **DimooRun** 是一个 Adapter-first 的企业级 Agent 运行时平台。
>
> Slogan：**Bring your agent, DimooRun handles production runtime, governance, and observability.**

---

## 1. 项目概述

DimooRun 是一个面向 AI Agent 的企业级运行时平台，用于接入、调度、治理和观测不同 Agent 框架生成的智能体。

DimooRun 的第一优先级适配对象是 **LangGraph**，因为 LangGraph 在 durable execution、checkpoint、streaming、interrupt、resume、human-in-the-loop 等生产级 Agent 能力上最完整。但 DimooRun 的核心架构不应绑定 LangGraph，而应该采用 Adapter-first 设计。早期 Adapter 路线先收敛在 LangChain 生态：LangGraph、LangChain Agent、DeepAgents。其他框架 Adapter 暂不进入早期设计和实现范围。

核心目标：

```text
用户继续使用自己熟悉的 Agent 框架编写智能体；
DimooRun 提供统一的企业级运行时、任务调度、状态管理、权限治理、观测审计、前端控制台和部署能力。
```

---

## 2. 项目定位

DimooRun 不是新的 Agent 编排框架，也不是低代码 Agent Builder，而是 Agent 的企业级 Runtime / Ops / Control Plane。

可以类比为：

```text
Spring Boot + Spring Cloud + AgentOps for AI Agents
```

| Spring 生态                | DimooRun                           |
| ------------------------ | ---------------------------------- |
| Spring Boot              | Agent Runtime 快速启动和标准工程结构          |
| Spring MVC               | Runtime API：invoke / stream / task |
| Spring Security          | 用户、角色、权限、API Key、Tool 权限           |
| Spring Cloud Gateway     | Agent Gateway / API Gateway        |
| Spring Cloud Config      | Agent 配置中心、模型配置、环境配置               |
| Spring Actuator          | 健康检查、metrics、runtime 状态            |
| Spring Batch / Scheduler | 异步任务、定时任务、重试                       |
| Spring State Machine     | LangGraph 等 Agent 编排框架             |
| Spring Admin             | DimooRun Console                   |
| Micrometer / Sleuth      | Trace、日志、指标、成本统计                   |
| JPA / Transaction        | Run Store、Checkpoint Store、元数据管理   |

与传统后端不同，Agent Runtime 额外关注：

* LLM 调用成本
* Prompt、输入输出和 Trace 审计
* Tool 调用权限
* Agent 中断与恢复
* 长任务状态
* 流式事件
* 人工介入
* 模型供应商限流
* RAG 证据追踪
* 评估回放

---

## 3. 设计目标

### 3.1 核心目标

1. **Adapter-first Agent Runtime**

   * 核心层面向通用 Agent Contract，而不是直接绑定 LangGraph。
   * LangGraph 是第一优先级 Adapter。

2. **企业级执行模型**

   * 支持同步调用、异步任务、流式调用、任务取消、失败重试、超时控制、并发限制、任务租约、Worker heartbeat、死信队列。

3. **标准化 Agent Package**

   * 用户按照统一 manifest 协议提交 Agent，平台负责加载、部署、配置注入和执行。

4. **能力声明 Capability Model**

   * 不同 Agent 框架能力不同，DimooRun 需要根据能力声明决定是否支持 stream、checkpoint、resume、interrupt、tool_events 等。

5. **状态持久化与恢复**

   * 记录 Run、RunAttempt、Task、Event、Trace、CheckpointIndex 和审计信息。

6. **控制平面能力**

   * 支持 Tenant、Project / Workspace、User、Role、Permission、API Key、Agent、AgentVersion、Deployment、Tool、Secret 等管理。

7. **运行时治理**

   * 支持 Tool Gateway、Secret 注入、权限校验、风险等级、人工审批、限流、审计和安全策略。

8. **模型资源治理集成**

   * DimooRun 不重复实现专业模型资源管理系统，而是通过 Model Gateway 集成 New API 等平台，复用其模型供应商接入、渠道路由、额度、倍率、计费、限流和成本统计能力。

9. **可观测性**

   * 支持结构化日志、事件流、OpenTelemetry、指标、成本统计、Trace、脱敏、采样、保留策略和外部观测平台集成。

10. **可评估性**

   * 从第一天记录可评估数据，后续支持自动评估、回归测试、上线门禁、线上抽样和人工反馈闭环。

11. **前端控制台**

    * 提供 DimooRun Console，用于 Agent 管理、Run 查看、Task 查看、Event Timeline、Trace 调试、API Key、Tool、Secret、用户权限和审计。

---

## 4. 非目标

1. DimooRun 不重新实现 LangGraph、LangChain、DeepAgents 或其他 Agent 框架。
2. DimooRun 不提供新的 Agent DSL。
3. DimooRun 不提供低代码 Agent 画布。
4. DimooRun 不替代 Dify、Flowise、Langflow 等 Agent Builder。
5. DimooRun 不定义用户 Agent 的 State Schema。
6. DimooRun 不限制用户 Agent 内部的节点、边、工具、Prompt、RAG、Memory 实现。
7. DimooRun 不内置业务 Tool。
8. DimooRun 不绑定某个模型供应商。
9. DimooRun 不内置完整模型供应商网关、余额系统、充值系统和计费系统；这类能力应优先接入 New API 等专业 Model Gateway。
10. DimooRun 不在 MVP 阶段实现多个 Agent Adapter；MVP 只实现 LangGraph Adapter。
11. DimooRun 不在 MVP 阶段实现复杂动态菜单、组织架构、审批流、计费系统、K8s Operator、完整评估平台。

一句话：

```text
DimooRun 关注 Agent 的企业级运行时，不关注 Agent 的业务智能逻辑。
```

---

## 5. 核心边界

DimooRun 不能完全脱离具体 Agent 框架，因为运行时必须理解不同框架的调用协议、事件协议和能力边界。

但 DimooRun 不应该理解用户 Agent 的业务语义。

例如对于 LangGraph，DimooRun 需要理解：

* thread_id
* checkpoint
* configurable
* stream event
* interrupt
* resume
* state lifecycle

但不理解：

* State 里有哪些业务字段
* 节点如何推理
* Prompt 如何设计
* Tool 具体做什么
* RAG 如何检索
* Memory 里存了什么业务内容

因此项目边界是：

```text
业务黑盒，运行白盒。
```

也就是：

```text
用户 Agent 的业务逻辑是黑盒；
Agent 的运行过程、状态生命周期、事件、权限和恢复机制是白盒。
```

---

## 6. Design Guardrails

随着 DimooRun 吸收 LangGraph Platform、Aegra、Dify、Langflow、Flowise、Letta、Langfuse、Phoenix、Haystack 等项目的优秀设计，必须明确哪些边界不能被稀释。

不可变原则：

```text
1. Adapter-first 是核心架构，不因为 LangGraph Compatibility Mode 变成 LangGraph-only 平台。
2. Compatibility API 是迁移和生态入口，不是 DimooRun 的主语义。
3. DimooRun 不提供低代码 Agent Builder，不提供拖拽编排画布。
4. Catalog 是组件治理目录，不是节点编排系统。
5. PublishedSurface 是运行时发布入口，不是应用构建器。
6. Run Graph 是观测投影，不是编排 DSL。
7. Memory / Semantic Store 是可治理资源，不是业务 Memory 语义接管。
8. Prompt / Config / Template 是版本化资产，不是 Prompt 设计平台。
9. Langfuse / Phoenix / OpenLLMetry 是观测或评估后端，不是 DimooRun 的核心账本。
10. New API 是 Model Gateway 实现，不是 DimooRun 的账务核心。
11. Policy Engine 是统一治理入口，不能被 API、Extension、Tool、Model、Secret 路径绕过。
12. 业务黑盒，运行白盒。
13. Scheduled / Batch / Replay 是运行时任务形态，不是业务编排 DSL。
14. Agent Gateway / PublishedSurface 是受治理的发布入口，不是应用构建器。
15. Debug / Replay Console 是运行时排障工具，不是 Agent 设计器。
```

判断标准：

```text
如果一个能力增强的是运行、治理、观测、审计、部署、恢复和兼容，它属于 DimooRun。
如果一个能力要求 DimooRun 理解和编排用户业务智能逻辑，它不属于核心范围。
```

---

## 7. 三层架构

### 7.1 Control Plane

控制平面负责管理和治理，不直接执行 Agent。

职责：

* Tenant 管理
* Project / Workspace 管理
* User / Role / Permission 管理
* API Key 管理
* Agent 注册
* AgentVersion 管理
* Deployment 管理
* 配置管理
* Secret 管理
* Tool Registry
* 审计日志
* Web Console

### 7.2 Runtime Plane

运行时平面负责 Agent 执行协议。

职责：

* invoke
* stream
* async task
* run lifecycle
* run attempt lifecycle
* task lifecycle
* worker dispatch
* capability 判断
* adapter dispatch
* checkpoint 管理
* interrupt / resume
* event mapping
* timeout / retry / cancel
* runtime context 注入
* 幂等控制

### 7.3 Agent Plane

Agent 平面是用户自己编写的 Agent。

职责：

* State Schema
* Node / Chain / Agent Loop
* Tool
* Memory
* RAG
* Prompt
* LLM 调用
* 业务逻辑

### 7.4 Frontend Console

DimooRun Console 是控制平面的可视化入口。

职责：

* 查看 Dashboard
* 管理 Agents / Versions / Deployments
* 查看 Runs / Tasks / Events / Trace
* 管理 API Keys
* 管理 Tools / Secrets
* 管理 Users / Roles / Permissions
* 查看 Audit Logs
* 辅助排障和回放

Console 不是低代码 Agent Builder，MVP 不提供拖拽画布。

---

## 8. 总体架构

### 8.1 逻辑架构

```text
Client / SDK / Console
        ↓
API Gateway / Runtime API
        ↓
Auth / Tenant / Project / Rate Limit / Permission
        ↓
Run Manager
        ↓
Task Scheduler / Queue
        ↓
Worker Pool
        ↓
Agent Runtime Contract
        ↓
Agent Adapter
   ├── LangGraphAdapter
   ├── LangChainAgentAdapter
   └── DeepAgentsAdapter
        ↓
User Agent
        ↓
Run Store / Event Store / Checkpoint Store / Trace Sink
```

### 8.2 模块架构

```text
┌──────────────────────────────────────┐
│             Console Frontend          │
│ Vue / Dashboard / Timeline / Trace    │
└──────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────┐
│              API Gateway              │
│ Auth / Rate Limit / Tenant / Routing  │
└──────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────┐
│           Agent Runtime API           │
│ invoke / stream / task / session      │
└──────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────┐
│             Scheduler Layer           │
│ queue / lease / retry / heartbeat     │
└──────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────┐
│              Worker Layer             │
│ Agent Contract + Adapter Executor     │
└──────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────┐
│           Persistence Layer           │
│ Postgres / Redis / Object Storage     │
└──────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────┐
│          Observability Layer          │
│ Trace / Metrics / Logs / Eval / Cost  │
└──────────────────────────────────────┘
```

### 8.3 MVP 架构形态

MVP 使用：

```text
模块化单体 + 独立 Worker
```

MVP 进程：

```text
server 进程：FastAPI API Server
worker 进程：Agent Worker，第一版只实现 LangGraphAdapter
console 进程：前端静态应用 / Vite dev server / Nginx
postgres：元数据和运行记录
redis：队列、事件流、缓存、锁
```

---

## 9. 技术选型

### 9.1 Backend / Runtime

MVP 推荐：

```text
Language: Python
Web Framework: FastAPI
Runtime Adapter: LangGraph Python first
ORM: SQLAlchemy / SQLModel
Migration: Alembic
Database: Postgres
Queue: Redis + Dramatiq / Celery / Arq
Cache / Stream / Lock: Redis
Observability: OpenTelemetry + Langfuse / Phoenix 可选
Deployment: Docker Compose
```

选择 Python 的原因：

* LangGraph / LangChain / DeepAgents 的 Python 生态更自然。
* 用户的 Agent、RAG、LLM SDK、embedding、eval 工具大概率使用 Python。
* Worker 层需要直接执行用户 Agent。
* MVP 避免跨语言复杂度。

### 9.2 Frontend Console

推荐：

```text
Vue 3
TypeScript
Vite
Vue Router
Pinia
Naive UI
ECharts
Monaco Editor
Axios / TanStack Query
openapi-typescript / orval
```

偏传统后台可以选择 Element Plus。

### 9.3 Java / Go 后续定位

Java / Go 不建议用于 MVP 核心 Runtime。

后续可选：

* Java：企业控制平面、IAM、后台管理、企业集成。
* Go：高性能 Gateway、CLI、K8s Operator、Worker Supervisor。

### 9.4 LangChain Ecosystem Version Policy

DimooRun 早期 Adapter 路线收敛在 LangChain 生态，因此版本策略需要稳定、可复现，而不是每次实施都追最新。

根据 LangChain 生态依赖策略，本项目采用以下首个固定测试基线：

```text
langchain      1.3.1
langchain-core 1.4.0
langgraph      1.2.1
deepagents     0.6.3
langsmith      0.8.5
```

起步原则：

```text
1. 新实现从 LangChain 1.0+ / LangGraph 1.0+ 生态起步，不支持 LangChain 0.x / LangGraph 0.x 兼容包袱。
2. 不要求每次实施都查询最新版本；以本节固定测试基线为准。
3. Runtime 自身依赖和示例 Agent 依赖分开管理。
4. AgentVersion 必须记录实际运行时的 framework_version。
5. Adapter conformance tests 必须绑定具体 framework version 运行。
6. 生产环境不使用裸 latest，必须使用 lockfile 和明确版本矩阵。
7. LangChain / LangGraph 可在 1.x LTS 范围内升级，但升级是显式维护动作，不是默认行为。
8. DeepAgents 当前未到 1.0，生产必须锁定到已测试版本。
9. langchain-core 必须显式依赖，不能只依赖 langchain 间接带入。
10. langchain-community 不作为默认依赖；如必须使用，需要 pin 到明确 minor series。
```

推荐版本约束策略：

```text
DimooRun Runtime：
  langchain>=1.0,<2.0
  langchain-core>=1.0,<2.0
  langgraph>=1.0,<2.0
  langsmith>=0.3.0
  deepagents==<tested-version>

生产 Agent Package：
  必须生成 lockfile。
  必须记录 package hash。
  必须记录 framework_version。
  必须通过 Adapter Conformance Test Kit。
```

首个固定测试版本矩阵：

```text
langchain==1.3.1
langchain-core==1.4.0
langgraph==1.2.1
deepagents==0.6.3
langsmith==0.8.5
```

版本升级规则：

```text
1. 默认不自动升级 LangChain 生态依赖。
2. 需要升级时，先更新版本矩阵。
3. 更新 lockfile。
4. 运行 Adapter Conformance Test Kit。
5. 通过后再更新 AgentVersion compatibility policy。
```

---

## 10. Adapter-first Agent Contract

DimooRun 核心层不直接依赖 LangGraph，而是依赖通用 AgentAdapter 协议。

### 10.1 AgentAdapter 接口

```python
from typing import Any, AsyncIterator, Protocol


class AgentAdapter(Protocol):
    framework: str

    async def load(
        self,
        package_uri: str,
        manifest: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> Any:
        ...

    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: "RuntimeContext",
    ) -> "AgentResult":
        ...

    async def stream(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: "RuntimeContext",
    ) -> AsyncIterator["AgentEvent"]:
        ...

    async def resume(
        self,
        agent: Any,
        run_id: str,
        payload: dict[str, Any],
        context: "RuntimeContext",
    ) -> "AgentResult":
        ...

    async def cancel(
        self,
        run_id: str,
        context: "RuntimeContext",
    ) -> None:
        ...
```

### 10.2 Capability Model

不是所有 Agent 框架都支持所有能力，因此必须声明 capability。

核心能力：

```text
invoke
stream
checkpoint
resume
interrupt
human_in_loop
tool_events
model_events
token_usage
filesystem
subagents
```

如果 API 调用了不支持的能力，应返回：

```json
{
  "error": "capability_not_supported",
  "capability": "resume",
  "framework": "langchain-agent-python"
}
```

### 10.3 Adapter 优先级

MVP：

```text
LangGraphAdapter
```

Phase 2：

```text
LangChainAgentAdapter
DeepAgentsAdapter
```

后续：

```text
暂不规划更多 Agent Adapter。
先把 LangGraph / LangChain Agent / DeepAgents 的加载、执行、事件映射、stream、checkpoint、interrupt、resume、tool/model usage、conformance tests 做完整。
```

---

## 11. Adapter Contract Versioning

Adapter-first 的长期风险不在于能不能写出第一个 Adapter，而在于框架升级、协议演进和 AgentVersion 的可重复运行。

因此 DimooRun 需要把 Adapter Contract 本身版本化。

版本维度：

```text
adapter_api_version
framework_name
framework_version_range
manifest_schema_version
capability_schema_version
event_schema_version
runtime_context_version
```

兼容性规则：

```text
1. AgentVersion 创建时记录当时使用的 adapter_api_version 和 manifest_schema_version。
2. Worker 执行前必须检查 AgentVersion 与当前 Adapter 的兼容性。
3. breaking change 必须提升 adapter_api_version。
4. capability 的含义发生变化时必须提升 capability_schema_version。
5. event payload 结构发生 breaking change 时必须提升 event_schema_version。
6. 新 Adapter 可以兼容旧 AgentVersion，但不能静默改变旧版本运行语义。
7. 不兼容时返回 adapter_contract_incompatible，而不是运行到一半失败。
```

AgentVersion 应补充字段：

```text
adapter_api_version
framework_version
manifest_schema_version
capability_schema_version
event_schema_version
compatibility_status
compatibility_checked_at
```

AdapterManifest 示例：

```yaml
adapter:
  name: langgraph
  adapter_api_version: "1.0"
  framework: langgraph-python
  framework_version_range: ">=1.0,<2.0"
  manifest_schema_version: "1.0"
  capability_schema_version: "1.0"
  event_schema_version: "1.0"
```

升级策略：

```text
compatible:
  允许直接运行。

compatible_with_warning:
  允许运行，但记录 warning event。

migration_required:
  禁止直接运行，需要先执行 manifest / package 迁移。

unsupported:
  Adapter 不再支持该 AgentVersion。
```

### 11.1 Adapter Conformance Test Kit

Adapter-first 的生态扩展不能只依赖接口定义，还需要可执行的兼容性测试。DimooRun 应提供 Adapter Conformance Test Kit，用于验证官方和第三方 Adapter 是否满足平台运行语义。

测试范围：

```text
invoke conformance
stream conformance
event mapping conformance
checkpoint conformance
resume conformance
interrupt conformance
cancel conformance
capability positive tests
capability negative tests
error mapping tests
idempotency behavior tests
```

认证结果：

```text
certified
certified_with_limitations
experimental
failed
```

规则：

```text
1. 官方 Adapter 发布前必须通过 conformance test。
2. 第三方 Adapter 可以声明 experimental，但不能默认进入 production profile。
3. Adapter 的 capability 声明必须由测试证明，不能只由 manifest 声明。
4. Compatibility API 的 Adapter 需要额外通过 golden tests。
5. conformance report 应记录 framework version、adapter_api_version、测试时间和失败项。
```

---

## 12. Schema Migration & Data Compatibility

除了 Adapter Contract，DimooRun 自身的数据结构也必须可演进。

需要版本化的 schema：

```text
database_schema_version
manifest_schema_version
dimoorun_yaml_schema_version
event_schema_version
artifact_schema_version
policy_schema_version
capability_schema_version
runtime_context_version
api_schema_version
compat_api_version
```

迁移原则：

```text
1. 数据库 schema 变更必须通过 migration 管理。
2. manifest.yaml 和 dimoorun.yaml 必须带 schema version 或可推断版本。
3. Event schema breaking change 必须保留旧事件读取能力。
4. Artifact schema breaking change 不应破坏历史 Artifact 读取。
5. Policy schema breaking change 必须提供 dry-run migration 和影响报告。
6. Compatibility API 版本变更不能静默改变 LangGraph 用户调用语义。
7. API schema 变更必须同步 OpenAPI 和 SDK 生成。
```

迁移类型：

```text
online migration
offline migration
backfill
schema validation
compatibility check
rollback plan
```

CLI：

```text
dimoorun migrate schema
dimoorun migrate manifest
dimoorun migrate config
dimoorun migrate events
dimoorun migrate policies
```

---

## 13. LangGraph Compatibility Mode

DimooRun 的长期定位是 Adapter-first，但第一优先级用户仍然是 LangGraph 用户。

如果用户已有 LangGraph / LangGraph Platform 项目，迁移到 DimooRun 不应要求重写 Agent。

因此 DimooRun 同时提供两套 API：

```text
Native DimooRun API
Compatibility API
```

目标：

```text
1. 让已有 LangGraph 项目尽量低成本迁移到 DimooRun。
2. 保留 DimooRun Native API 的完整企业治理能力。
3. 提供 LangGraph-compatible API，兼容核心 assistants / threads / runs 交互。
4. 尽量兼容 LangGraph Studio 的调试入口。
5. 逐步兼容 Agent Protocol 相关交互。
```

概念映射：

| LangGraph / Platform 概念 | DimooRun 概念 |
| ------------------------- | ------------- |
| assistant                 | Agent / AgentVersion / Deployment |
| thread                    | Session / thread_id / CheckpointIndex |
| run                       | Run / Task / RunAttempt |
| stream event              | AgentEvent / Event / Streaming Runtime |
| checkpoint                | Framework Runtime Store / CheckpointIndex |
| store                     | Runtime Store / Agent Memory Store / Semantic Store |

API 分层：

```text
/v1/...                        Native DimooRun API
/compat/langgraph/...           LangGraph-compatible API
/compat/agent-protocol/...      Agent Protocol compatibility API
```

兼容原则：

```text
1. Native API 是平台主语义，Compatibility API 是入口适配层。
2. Compatibility API 创建的对象也必须落到 DimooRun 的 Agent / Run / Task / Event / AuditLog。
3. Compatibility API 不能绕过 Tenant、Project、Policy、Secret、Model Gateway、Tool Gateway。
4. 对无法兼容的能力返回明确 capability_not_supported 或 compatibility_not_supported。
5. 兼容层应尽量保持 SDK 调用方式不变，但不承诺完整复制第三方平台所有内部行为。
```

Phase 1 优先兼容：

```text
assistants.create / get / list
threads.create / get
runs.create / get / stream
核心 SSE stream
LangGraph thread_id / checkpoint 基础映射
```

Phase 2 扩展：

```text
LangGraph Studio 调试入口
Agent Protocol 更多细节
store / semantic store 兼容
更完整的 stream modes
迁移工具自动生成 compatibility config
```

---

## 14. Agent Package 规范

### 14.1 推荐目录结构

```text
agent_project/
├── agent.py
├── manifest.yaml
├── requirements.txt
├── config.schema.json
├── schemas/
│   ├── input.json
│   └── output.json
├── tools/
├── prompts/
└── tests/
```

### 14.2 manifest.yaml 通用结构

```yaml
name: customer-support-agent
version: 1.0.3
schema_version: "1.0"

runtime:
  framework: langgraph-python
  adapter: langgraph
  entrypoint: agent:build_graph

capabilities:
  invoke: true
  stream: true
  checkpoint: true
  resume: true
  interrupt: true
  human_in_loop: true
  tool_events: true
  model_events: true
  token_usage: true

input_schema: schemas/input.json
output_schema: schemas/output.json

resources:
  cpu: "1"
  memory: "2Gi"
  timeout_seconds: 300

execution:
  mode: async
  max_concurrency: 20
  retry:
    max_attempts: 3
    backoff: exponential

checkpoint:
  enabled: true
  backend: platform-postgres

streaming:
  enabled: true

permissions:
  tools:
    - crm.read
    - ticket.write
  secrets:
    - OPENAI_API_KEY
    - CRM_TOKEN

security:
  network_policy: restricted
  allow_file_system_write: false
```

### 14.3 LangGraph Agent 入口

```python
from typing import Any


def build_graph(config: dict[str, Any]):
    """Return a compiled LangGraph graph."""
    ...
```

### 14.4 LangChain Agent 入口

```python
from typing import Any


def create_agent(config: dict[str, Any]):
    """Return a LangChain runnable / agent executor."""
    ...
```

### 14.5 DeepAgents 入口

```python
from typing import Any


def create_deep_agent(config: dict[str, Any]):
    """Return a DeepAgents agent."""
    ...
```

### 14.6 Agent Package 安全边界

Agent Package 是高风险入口。

风险包括：

* 任意代码执行
* 恶意依赖
* pip 供应链风险
* 读取宿主环境变量
* 访问宿主文件
* 访问内网
* 无限循环
* 资源耗尽

后续安全策略：

```text
容器隔离
依赖锁定
requirements hash 校验
依赖漏洞扫描
Agent 镜像构建
资源限制 CPU / Memory / Timeout
网络访问策略
Secret 最小暴露
文件系统只读
工具调用必须经过 Tool Gateway
```

MVP 可先在可信环境运行，但生产环境不应无隔离执行任意 Agent Package。

---

## 15. Project Configuration

DimooRun 使用两个层级的配置文件：

```text
manifest.yaml       # 单个 Agent Package 的元信息
dimoorun.yaml       # 项目级 / workspace 级配置
```

`manifest.yaml` 描述 Agent Package 本身，随 Agent 一起发布。

`dimoorun.yaml` 描述项目级开发、部署、Adapter、执行环境、策略、观测和存储配置。

示例：

```yaml
schema_version: "1.0"

project:
  name: customer-support
  tenant: default

agents:
  - name: support-agent
    path: ./agents/support
    manifest: ./agents/support/manifest.yaml

adapters:
  langgraph:
    enabled: true
  langchain-agent:
    enabled: false
  deepagents:
    enabled: false

deployments:
  dev:
    agent: support-agent
    version: 0.1.0
    execution_profile: local-dev
  prod:
    agent: support-agent
    version: 0.1.0
    execution_profile: prod-worker

execution_profiles:
  local-dev:
    mode: in_process
    storage: sqlite
  prod-worker:
    mode: worker
    queue: redis
    max_concurrency: 20

model_gateways:
  default:
    provider: newapi
    base_url: ${NEWAPI_BASE_URL}
    secret: NEWAPI_API_KEY

policies:
  tool_approval:
    destructive: required
    financial: required
  trace_visibility:
    default: redacted

observability:
  tracing: opentelemetry
  langfuse:
    enabled: false

storage:
  metadata: postgres
  queue: redis
  object_store: local
```

配置原则：

```text
1. manifest.yaml 面向 Agent Package，可被 Registry 持久化。
2. dimoorun.yaml 面向项目和环境，可被 CLI、server、worker、console 共同读取。
3. Secret 值不直接写入 dimoorun.yaml，只写 secret name 或 env var 引用。
4. dimoorun.yaml 可以被环境变量覆盖。
5. 生产部署时，dimoorun.yaml 应被解析成数据库中的 Deployment / ExecutionProfile / Policy 等对象。
```

---

## 16. CLI / Developer Experience

CLI 是 DimooRun 的开发者入口。

命令：

```text
dimoorun init
dimoorun dev
dimoorun validate
dimoorun package
dimoorun deploy
dimoorun worker
dimoorun console
dimoorun doctor
dimoorun migrate
dimoorun logs
dimoorun up
dimoorun down
```

MVP 命令：

```text
dimoorun init       # 创建 dimoorun.yaml、示例 Agent、manifest.yaml
dimoorun dev        # 本地 dev mode 启动 server + worker + console
dimoorun validate   # 校验 manifest、dimoorun.yaml、capability、entrypoint
dimoorun worker     # 启动 worker
dimoorun up         # 启动 Docker Compose 依赖和服务
dimoorun down       # 停止本地服务
dimoorun doctor     # 检查 Python、Docker、Postgres、Redis、模型网关、配置
```

Phase 2 命令：

```text
dimoorun package
dimoorun deploy
dimoorun migrate
dimoorun logs
```

设计原则：

```text
1. CLI 不绕过 server 领域逻辑。
2. 本地开发可以直接读取 dimoorun.yaml。
3. 生产部署应通过 API 或迁移命令把配置写入平台。
4. validate 是所有 package / deploy / up 的前置能力。
5. doctor 用于降低本地环境和依赖排障成本。
```

---

## 17. Deployment Modes

DimooRun 支持三种运行模式，分别对应学习路径、生产路径和企业路径。

### 17.1 Dev Mode

目标：

```text
本地开发、快速调试、低成本上手。
```

形态：

```text
server: in-process
worker: in-process
metadata store: SQLite / in-memory
queue: in-process queue
event: local event log
agent execution: same process or local subprocess
command: dimoorun dev
```

适合：

```text
单开发者
示例项目
Agent Package 调试
LangGraph compatibility 验证
```

### 17.2 Production Mode

目标：

```text
单机或小集群生产。
```

形态：

```text
server: FastAPI API Server
worker: Worker Pool
metadata store: Postgres
queue: Redis
event: Redis Stream / Postgres Event
artifact store: local / S3-compatible
agent execution: worker process / container
deployment: Docker Compose / single K8s namespace
```

### 17.3 Enterprise Mode

目标：

```text
多租户、高隔离、高可用、大规模运行。
```

形态：

```text
server: API Server replicas
worker: Worker Pool / remote worker / K8s worker
sandbox: container pool
metadata store: Postgres HA
queue: Redis Cluster / Kafka / Temporal
event: Kafka / Redis Stream
artifact store: object storage
observability: OpenTelemetry + external sinks
policy: centralized Policy Engine
deployment: K8s / Helm / multi-namespace
```

模式原则：

```text
1. 三种模式共享同一领域模型。
2. Dev Mode 可以简化基础设施，但不能创造独立语义。
3. Production Mode 是默认落地目标。
4. Enterprise Mode 通过替换 Backend / Provider 扩展，不重写核心。
```

---

## 18. Execution Isolation & Sandbox

Agent Package 是用户代码，DimooRun 不能把它当作普通业务插件在宿主进程中无限信任。

执行隔离是企业级 Agent Runtime 的基础能力之一。

隔离等级：

| 等级 | 形态                 | 适用阶段             | 风险说明                       |
| ---- | -------------------- | -------------------- | ------------------------------ |
| L0   | trusted in-process   | 本地开发 / Demo       | 无隔离，仅适合可信代码           |
| L1   | dedicated venv       | MVP / 内部可信环境     | 依赖隔离，但进程、网络和文件风险仍在 |
| L2   | worker subprocess    | 单机生产前置形态       | 可控制超时、信号、资源回收         |
| L3   | container sandbox    | 生产推荐             | 隔离文件系统、网络、资源、环境变量   |
| L4   | remote isolated pool | 多租户 / 高安全场景    | Agent 在独立 Worker 集群运行      |

生产环境推荐至少 L3。

安全策略：

```text
package hash 校验
依赖锁定
依赖漏洞扫描
只读文件系统
临时工作目录
网络 egress policy
CPU / Memory / Timeout 限制
进程数限制
环境变量白名单
Secret 按需注入
Tool 调用强制走 Tool Gateway
Model 调用强制走 Model Gateway
```

ExecutionProfile 字段：

```text
id
tenant_id
project_id nullable
name
isolation_level
image nullable
python_version
dependency_lock_required
network_policy
filesystem_policy
cpu_limit
memory_limit
timeout_seconds
allowed_env
allowed_secret_refs
allowed_gateway_refs
created_at
updated_at
```

Worker 执行规则：

```text
1. Worker 根据 AgentVersion、Deployment 和 ExecutionProfile 创建执行环境。
2. Agent Package 的依赖安装、缓存和镜像构建必须与 package hash 绑定。
3. Secret 不写入镜像，不写入磁盘，运行时按最小权限注入。
4. Agent 产生的临时文件必须进入 workspace，并在 Run 结束后按 retention 策略清理或转存 Artifact Store。
5. 任何越权网络、文件、Secret、Tool、Model 访问都应产生 security.policy_violation 事件。
```

---

## 19. RuntimeContext

每次 Agent 执行时，DimooRun 注入 RuntimeContext。

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RuntimeContext:
    tenant_id: str
    project_id: str | None
    user_id: str
    session_id: str | None
    request_id: str
    run_id: str
    attempt_id: str | None
    task_id: str | None
    trace_id: str
    correlation_id: str | None
    idempotency_key: str | None
    agent_id: str
    agent_version: str
    deployment_id: str | None
    environment: str
    framework: str
    adapter: str
    thread_id: str | None
    deadline_at: datetime | None
    permissions: list[str]
    secrets: dict[str, str]
    config: dict[str, Any]
    metadata: dict[str, Any]
```

不同 Adapter 负责把 RuntimeContext 映射到各自框架：

* LangGraphAdapter：映射到 `configurable`。
* LangChainAgentAdapter：映射到 callbacks / metadata。
* DeepAgentsAdapter：映射到 Deep Agents 的运行配置、subagents 和 filesystem / middleware 上下文。

---

## 20. Event Model

事件模型分为通用事件和框架特定事件。

### 20.1 通用事件

```text
run.started
run.completed
run.failed
run.cancelled
run.timeout
attempt.started
attempt.completed
attempt.failed
agent.message
agent.stream_chunk
tool.called
tool.completed
tool.failed
model.started
model.completed
model.failed
checkpoint.created
human_interrupt.required
```

### 20.2 框架特定事件

```text
framework.langgraph.node.started
framework.langgraph.node.finished
framework.deepagents.subagent.started
framework.deepagents.filesystem.updated
framework.langchain.callback.chain.started
framework.langchain.callback.tool.started
```

原则：

```text
通用事件用于 Console 统一展示；
框架特定事件用于保留调试细节。
```

---

## 21. Streaming Runtime

Agent streaming 不是简单 HTTP chunk，而是运行时事件传输、断线重连、跨实例 fan-out 和 Console Timeline 的共同基础。

### 21.1 传输协议

默认协议：

```text
SSE
```

SSE 适合：

```text
浏览器
Console
普通 API stream
LangGraph-compatible stream
只需要服务端到客户端推送的场景
```

可选协议：

```text
WebSocket
```

WebSocket 适合：

```text
双向控制
交互式会话
实时取消
human-in-the-loop 输入
低延迟控制通道
```

### 21.2 事件序列

每个 stream event 必须具备：

```text
run_id
attempt_id nullable
sequence
event_id
type
payload_ref or payload
created_at
```

规则：

```text
event_id = run_id + ":" + sequence
sequence 在同一个 run 内单调递增
大 payload 写入 Artifact Store，stream 只传 ref
```

### 21.3 Replay Buffer

Replay Buffer 用于断线重连和短期回放。

后端：

```text
Redis Stream
Postgres event log
Kafka
```

策略：

```text
保留最近 N 条事件
保留最近 T 分钟事件
终态 Run 可从 Event Store 完整回放 Timeline
```

### 21.4 Reconnect

客户端断线后：

```text
1. 客户端携带 Last-Event-ID。
2. API Server 解析 run_id 和 sequence。
3. 服务端从 Replay Buffer 或 Event Store 继续发送。
4. 如果 buffer 已过期，返回 stream_replay_expired，并提示客户端查询 run events。
```

### 21.5 Cross-instance Fan-out

多 API Server 场景下，Worker 不应只把事件写给单个 API Server 内存。

推荐路径：

```text
Worker
  ↓
Event Store / Redis Stream / Kafka
  ↓
API Server subscriber
  ↓
SSE / WebSocket client
```

### 21.6 Backpressure

规则：

```text
1. 限制单 Run stream buffer 大小。
2. 慢消费者超过阈值后断开或降级为轮询。
3. 大 payload 不直接 stream。
4. 高频 token event 可以合并或采样，但关键状态事件不能丢。
5. API Server 和 Worker 之间必须解耦，不能因为前端慢消费者阻塞 Agent 执行。
```

### 21.7 Stream 终止语义

标准终止事件：

```text
stream.completed
stream.failed
stream.cancelled
stream.timeout
stream.replay_expired
```

规则：

```text
1. stream.completed 表示 Run 正常终态已写入。
2. stream.failed 表示 Run 失败或 stream 管道不可恢复。
3. stream.cancelled 表示 Run 或客户端主动取消。
4. stream.timeout 表示 Run 或连接达到超时策略。
5. stream.replay_expired 表示 Last-Event-ID 之前的 buffer 已过期，客户端应改查 /runs/{run_id}/events。
6. TCP 连接断开不等于 Run 结束。
7. 客户端必须以 terminal event 或 Run 查询结果判断最终状态。
```

---

## 22. 核心领域模型

本章描述 Runtime 最核心的领域对象。PublishedSurface、CatalogItem、PromptAsset、Dataset、MemoryBlock 等扩展对象在后续专题章节中定义，但它们同样属于平台领域模型。

### 22.0 通用审计与软删除字段

所有 Platform Metadata Store 表都必须具备统一审计字段和软删除字段。

通用字段：

```text
created_at
created_by nullable
updated_at
updated_by nullable
is_deleted
deleted_at nullable
deleted_by nullable
```

规则：

```text
1. 默认业务删除不是 hard delete，而是 soft delete。
2. soft delete 必须设置 is_deleted=true、deleted_at、deleted_by，并写 AuditLog。
3. 生命周期归档使用 status=archived，不等同于删除。
4. archive 表示资源仍作为历史事实保留，可查询、可审计、可回放。
5. is_deleted=true 表示默认列表和业务操作应过滤该记录，只有审计、恢复、retention、管理员视图可查询。
6. hard delete 只允许出现在 migration rollback、测试清理、retention purge job 或显式管理员物理清理任务中。
7. API、Repository 和 Console 默认不得执行物理删除。
8. 删除高风险资源时必须经过 Policy Engine，并记录 actor、request_id、resource_type、resource_id。
9. Repository 默认查询必须过滤 is_deleted=true；只有显式 include_deleted 且有权限时才能返回软删除记录。
10. AuditLog 是不可变合规事实，不能通过业务 API 更新、归档、软删除或物理删除。
11. created_at / created_by / updated_at / updated_by / is_deleted / deleted_at / deleted_by 必须由统一 mixin 提供，业务模型不得重复定义同名字段。
```

### 22.1 Tenant

企业租户。

字段：

```text
id
name
status
created_at
updated_at
```

### 22.2 Project / Workspace

租户下的项目或工作区，用于隔离不同业务线。

字段：

```text
id
tenant_id
name
description
status
created_at
updated_at
```

### 22.3 User

平台用户。

字段：

```text
id
tenant_id
email
name
status
created_at
updated_at
```

### 22.4 ServiceAccount

机器身份，用于 CI/CD、外部系统、Webhook、MCP server、Worker、自动化脚本和企业集成，不应默认挂在人类用户下面。

字段：

```text
id
tenant_id
project_id nullable
name
description
status
created_by
last_used_at
created_at
updated_at
```

规则：

```text
1. ServiceAccount 使用和 User 相同的 resource:action 权限模型。
2. ServiceAccount 权限必须显式授予，不能继承创建者的全部权限。
3. ServiceAccount 可创建 API Key，但 API Key scopes 必须是 ServiceAccount 权限子集。
4. 高风险 ServiceAccount 应支持过期时间、轮换策略和管理员审批。
5. ServiceAccount 的所有调用都必须进入 AuditLog，并标记 actor_type=service_account。
```

### 22.5 Role / Permission

权限使用资源动作模型：

```text
resource:action
```

示例：

```text
agent:read
agent:create
agent:update
agent:delete
agent:deploy
agent:invoke
run:read
run:cancel
run:retry
run:read_input
run:read_output
trace:read
trace:read_prompt
trace:read_tool_args
trace:export
task:read
tool:read
tool:call
tool:approve
secret:read
secret:create
secret:update
secret:delete
policy:read
policy:create
policy:update
policy:delete
artifact:read
artifact:create
artifact:delete
dataset:read
dataset:create
dataset:update
dataset:delete
experiment:read
experiment:create
experiment:run
schedule:read
schedule:create
schedule:update
schedule:delete
batch:read
batch:create
replay:create
memory:read
memory:create
memory:update
memory:delete
catalog:read
catalog:create
catalog:update
catalog:delete
prompt:read
prompt:create
prompt:update
prompt:delete
model_gateway:read
model_gateway:create
model_gateway:update
model_gateway:delete
published_surface:read
published_surface:create
published_surface:update
published_surface:delete
extension:read
extension:create
extension:update
extension:delete
alert:read
alert:create
alert:update
alert:delete
backup:read
backup:create
backup:restore
audit:read
user:manage
service_account:manage
role:manage
```

API Key scopes：

```text
1. API Key scopes 使用同一套 resource:action 权限模型。
2. API Key scopes 必须是创建者或绑定 service account 权限的子集。
3. Project-scoped API Key 不能访问其他 project。
4. API Key 禁用后，所有 Runtime / Admin / Compatibility API 均必须拒绝。
5. 高风险 scope，如 secret:read、tool:call、run:read_input、trace:read_prompt，应支持额外审批或管理员授权。
```

幂等记录：

```text
id
tenant_id
project_id nullable
endpoint
idempotency_key
request_hash
response_ref nullable
status
expires_at nullable
created_at
created_by nullable
updated_at
updated_by nullable
is_deleted
deleted_at nullable
deleted_by nullable
```

唯一约束：

```text
tenant_id + project_id + endpoint + idempotency_key
```

用途：

```text
1. 所有需要幂等的写 API 先写入或读取 IdempotencyRecord。
2. 同一 scope 下 request_hash 不一致时返回 idempotency_conflict。
3. response_ref 可指向 Run、Task、Artifact 或缓存响应。
4. 过期记录由 retention job 清理，不由普通 API 硬删除。
```

### 22.6 APIKey

外部系统调用凭证。

字段：

```text
id
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

### 22.7 Agent

逻辑智能体。

字段：

```text
id
tenant_id
project_id
name
description
owner_id
status
created_at
updated_at
```

### 22.8 AgentVersion

Agent 的不可变版本。

字段：

```text
id
agent_id
version
package_uri
framework
adapter
capabilities
entrypoint
manifest
status
created_at
created_by
```

### 22.9 Deployment

某个 AgentVersion 在某个环境中的部署。

字段：

```text
id
tenant_id
project_id
agent_id
agent_version_id
environment
desired_status
runtime_status
replicas
config
last_runtime_error nullable
created_at
updated_at
```

期望状态 desired_status：

```text
draft
active
paused
draining
stopped
archived
```

实际状态 runtime_status：

```text
not_loaded
warming_up
ready
degraded
failed
draining
stopped
```

状态语义：

```text
active：允许新 Run，Worker 可以按需加载 AgentInstance。
paused：不接收新 Run，已有 Run 继续执行，实例可以保留一段时间。
draining：不接收新 Run，等待已有 Run 完成，然后卸载实例。
stopped：不接收新 Run，并要求 Worker 卸载对应 AgentInstance。
archived：只读历史，不允许部署和运行。
```

### 22.10 AgentInstance

Worker 上真实加载出来的 Agent 运行实例。AgentInstance 是运行态对象，不是用户业务对象，也不改变 AgentVersion 的不可变语义。

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
error nullable
metadata
```

状态：

```text
loading
ready
busy
idle
draining
evicted
failed
```

规则：

```text
1. AgentInstance 由 Worker 通过 Adapter.load() 创建或复用。
2. AgentInstance 可以按 deployment_id + agent_version_id + execution_profile_id 缓存。
3. restart 不修改 AgentVersion，只驱逐当前实例并允许后续重新 load。
4. stop / drain 必须通过 Deployment desired_status 触发，不允许前端直接杀 Worker 内部对象。
5. 多 Worker 场景下，Deployment.runtime_status 是多个 AgentInstance 状态的聚合结果。
```

### 22.11 Session

用户会话，通常对应多轮交互。

字段：

```text
id
tenant_id
project_id
user_id
service_account_id nullable
agent_id
metadata
created_at
updated_at
```

### 22.12 Run

一次 Agent 执行。

字段：

```text
id
tenant_id
project_id
user_id
service_account_id nullable
agent_id
agent_version_id
deployment_id
session_id
framework
adapter
thread_id
trace_id
idempotency_key
status
input_ref
output_ref
error
started_at
finished_at
created_at
```

状态：

```text
pending
running
interrupted
succeeded
failed
cancelled
timeout
```

### 22.13 RunAttempt

一次 Run 的具体执行尝试。

字段：

```text
id
run_id
task_id
attempt_no
worker_id
status
started_at
finished_at
error
latency_ms
created_at
```

状态：

```text
running
succeeded
failed
timeout
cancelled
worker_lost
```

### 22.14 Task

调度系统中的异步任务。

字段：

```text
id
run_id
tenant_id
project_id
status
attempt
max_attempts
queue
priority
scheduled_at
started_at
finished_at
leased_until
worker_id
heartbeat_at
dedupe_key
idempotency_key
error
dead_letter_reason
created_at
```

状态：

```text
queued
leased
running
retrying
succeeded
failed
dead_letter
cancelled
```

### 22.15 Event

Agent 运行事件。

字段：

```text
id
run_id
attempt_id nullable
tenant_id
project_id
type
framework
payload_ref or payload
visibility_level
created_at
```

### 22.16 CheckpointIndex

Checkpoint 索引。

字段：

```text
id
run_id
thread_id
checkpoint_ns
checkpoint_id
payload_uri
created_at
```

### 22.17 Tool

平台注册工具。

字段：

```text
id
tenant_id
project_id
name
description
schema
risk_level
status
created_at
updated_at
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

### 22.18 Secret

密钥引用。

字段：

```text
id
tenant_id
project_id
name
provider
scope
status
last_used_at
created_at
updated_at
```

### 22.19 AuditLog

审计日志。

字段：

```text
id
tenant_id
project_id nullable
actor_user_id
actor_id
actor_type: user | service_account | system | agent
action
resource_type
resource_id
result
ip
user_agent
request_id
trace_id
metadata
created_at
```

---

## 23. Extended Domain Models

随着平台能力扩展，DimooRun 还需要一批非最小闭环但属于平台治理范围的扩展领域对象。

扩展对象清单：

```text
PublishedSurface
IngressRoute
AgentInstance
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

归类：

| 类别 | 对象 |
| ---- | ---- |
| 发布入口 | PublishedSurface / IngressRoute |
| 运行实例 | AgentInstance |
| 组件治理 | CatalogItem |
| 资产版本 | PromptAsset / ConfigAsset / TemplateAsset |
| 运行投影 | RunGraphNode / RunGraphEdge |
| 质量闭环 | Dataset / DatasetItem / Experiment / ExperimentRun / EvaluationResult / Feedback |
| 调度回放 | ScheduledRun / BatchRun / ReplayJob |
| 记忆治理 | MemoryBlock / SemanticStoreProvider |
| 模型网关 | ModelGateway / ModelPolicy / ModelUsageSnapshot |
| 策略治理 | Policy / PolicyDecision |
| HITL | HumanTask / ApprovalRequest / ApprovalPolicy |
| 产物存储 | Artifact |
| 告警通知 | NotificationChannel / AlertRule / IncidentEvent |
| 扩展机制 | WebhookSubscription / Extension |
| 备份恢复 | BackupPlan / RestoreJob |

原则：

```text
1. 扩展领域对象不得绕过 Tenant / Project / Policy / AuditLog。
2. 扩展领域对象需要进入权限资源模型。
3. 扩展领域对象的生命周期需要和 AgentVersion / Deployment / Run 保持可追溯关系。
4. MVP 可以只实现扩展对象的最小 metadata，但设计上应保留完整边界。
```

---

## 24. Agent Lifecycle

DimooRun 管理的不是单次 Agent 调用，而是 Agent 从包提交到生产运行、观测、评估、下线的完整生命周期。

标准生命周期：

```text
package
  ↓
validate
  ↓
register agent
  ↓
create agent version
  ↓
security scan
  ↓
compatibility check
  ↓
deploy
  ↓
run
  ↓
observe
  ↓
evaluate
  ↓
promote / rollback
  ↓
deprecate
  ↓
archive
```

生命周期状态：

```text
draft
validating
validated
rejected
registered
deploying
active
paused
deprecated
archived
```

每个阶段的职责：

| 阶段 | DimooRun 责任 |
| ---- | ------------- |
| package | 接收 Agent Package、记录 hash、来源和提交人 |
| validate | 校验 manifest、schema、entrypoint、capability、资源限制 |
| security scan | 检查依赖、危险配置、Secret 声明、网络策略 |
| compatibility check | 校验 adapter_api_version、framework_version、capability_schema_version |
| deploy | 绑定环境、配置、ExecutionProfile、ModelGateway、Policy |
| run | 创建 Run / Task / Attempt，执行 Adapter |
| observe | 写 Event、Trace、Metric、AuditLog、ModelUsageSnapshot |
| evaluate | 基于 Run 数据生成质量、稳定性、成本和安全评估 |
| promote | 将版本提升到目标环境或更高流量 |
| rollback | 回退 Deployment 到旧 AgentVersion |
| deprecate | 禁止新部署，但允许已有 Run / Session 收尾 |
| archive | 冻结版本和元数据，按 retention 保留或清理产物 |

生命周期原则：

```text
1. AgentVersion 不可变。
2. Deployment 指向一个明确的 AgentVersion。
3. Run 必须记录实际执行的 AgentVersion，而不是只记录 Agent。
4. 回滚通过切换 Deployment 指针完成，不修改历史 AgentVersion。
5. 下线 AgentVersion 不应破坏历史 Run、Trace、Event 和 Artifact 的可追溯性。
```

### 24.1 Deployment Runtime Control

Console 可以让用户控制“当前启用哪些 Agent”，但平台内部必须落到 Deployment 的期望状态，而不是直接启动或停止 Agent 对象。

核心对象关系：

```text
Agent
  逻辑智能体，不启动。

AgentVersion
  不可变版本，不启动。

Deployment
  某个 AgentVersion 在某个环境中的运行目标，由 Console / API 控制 desired_status。

AgentInstance
  Worker 上通过 Adapter.load() 加载出来的真实运行实例，由 Worker 管理生命周期。
```

控制动作：

```text
activate：允许新 Run，Worker 可按需加载实例。
pause：暂停接收新 Run，已有 Run 继续。
resume：从 paused 恢复为 active。
drain：停止接收新 Run，等待已有 Run 结束后卸载实例。
stop：停止接收新 Run，并要求 Worker 卸载实例。
restart：驱逐当前实例，下次 Run 重新 load，不修改 AgentVersion。
```

运行规则：

```text
1. 前端只修改 Deployment desired_status 或发起控制动作。
2. Worker 根据 desired_status 决定是否加载、保留、drain 或驱逐 AgentInstance。
3. Run 创建前必须检查 Deployment 是否允许接收新 Run。
4. active 不代表所有 Worker 都已经加载 Agent，只代表允许按需加载。
5. runtime_status 由 Worker heartbeat、AgentInstance 状态、最近错误和健康检查聚合得出。
6. paused / draining / stopped 都必须产生 AuditLog。
7. restart 是运维动作，不是版本发布；版本发布必须创建新的 AgentVersion 或切换 Deployment 指针。
```

---

## 25. Migration Story

DimooRun 需要为已有 Agent 项目提供迁移路径，尤其是 LangGraph / LangGraph Platform / Aegra 用户。

迁移目标不是承诺所有历史状态无损迁移，而是降低项目接入成本，自动生成 DimooRun 所需的配置和包规范。

支持来源：

```text
裸 LangGraph 项目
LangGraph Platform / LangSmith Deployments 项目
Aegra 项目
LangChain Agent 项目
```

CLI：

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
生成兼容性报告
```

迁移输出：

```text
manifest.yaml
dimoorun.yaml
migration_report.md
compatibility_warnings
manual_steps
```

Checkpoint 迁移原则：

```text
1. Checkpoint 是否可迁移取决于源后端、序列化格式、LangGraph 版本和 State Schema 兼容性。
2. DimooRun 提供 best-effort migration，不保证所有历史 checkpoint 可无损迁移。
3. 无法迁移 checkpoint 时，仍应允许迁移 Agent Package 和新 Run。
4. 迁移后的 checkpoint 必须写入 CheckpointIndex。
5. checkpoint_incompatible 必须明确指出原因。
```

迁移阶段：

```text
Phase 1:
  裸 LangGraph 项目迁移，生成 manifest.yaml / dimoorun.yaml。

Phase 2:
  LangGraph Platform / Aegra 项目迁移，兼容 assistants / threads / runs 配置。

Phase 3:
  checkpoint / store best-effort migration，生成完整迁移报告。
```

---

## 26. Published Runtime Surfaces

DimooRun 不是低代码 App Builder，但企业 Runtime 需要把已部署的 Agent 暴露为稳定、可治理的运行入口。

可吸收 Dify、Langflow、Flowise 的应用发布经验，但不吸收其可视化编排定位。

发布面：

```text
Native API endpoint
LangGraph-compatible endpoint
Chat endpoint
Task endpoint
Streaming endpoint
MCP server endpoint
Webhook endpoint
Embedded console link
```

PublishedSurface 字段：

```text
id
tenant_id
project_id
deployment_id
surface_type: api | chat | task | stream | mcp_server | webhook
path
auth_mode
rate_limit_policy_id nullable
visibility_policy_id nullable
status
created_at
updated_at
```

IngressRoute 字段：

```text
id
tenant_id
project_id
published_surface_id
path
custom_domain nullable
auth_mode: api_key | jwt | public | internal
cors_policy_id nullable
rate_limit_policy_id nullable
request_transform_ref nullable
response_transform_ref nullable
access_log_enabled
status
created_at
updated_at
```

规则：

```text
1. PublishedSurface 只暴露已部署 Agent，不创建或编排 Agent。
2. 所有入口都必须落到统一 Run / Task / Event / AuditLog。
3. MCP server endpoint 可以把某个 Deployment 暴露为 MCP tools，但必须经过 Tool Gateway 和 Policy Engine。
4. Chat endpoint 是 Runtime invocation surface，不是聊天应用构建器；不提供会话 UI builder、Prompt 编排、知识库配置等应用构建能力。
5. Console 可以管理发布入口、API key、限流、审计和访问日志。
6. IngressRoute 只负责受治理的入口映射，不允许绕过 Runtime API、Policy Engine 或 AuditLog。
7. public auth_mode 必须显式开启，并建议绑定限流、CORS、审计和 abuse protection。
```

---

## 27. Component, Tool, and MCP Catalog

Dify、Langflow、Flowise 的组件体系说明：生态扩展需要可发现、可描述、可校验的组件目录。

DimooRun 不提供低代码节点画布，但需要企业级组件目录，用于治理 Adapter、Tool、MCP server、Model Gateway、Store Provider、Evaluator 和 Extension。

Catalog 对象：

```text
AdapterCatalogItem
ToolCatalogItem
MCPServerCatalogItem
ModelGatewayCatalogItem
StoreProviderCatalogItem
EvaluatorCatalogItem
ExtensionCatalogItem
```

统一元数据：

```text
id
name
description
type
provider
version
schema
capabilities
risk_level
required_secrets
required_permissions
runtime_requirements
status
created_at
updated_at
```

MCP 设计：

```text
1. DimooRun 可以作为 MCP client 接入外部 MCP server。
2. DimooRun 可以把受控 Tool / Deployment 暴露为 MCP server。
3. MCP tool 名称、描述、schema 必须可审计，避免 Agent 错选工具。
4. MCP server 调用必须通过 Tool Gateway、Policy Engine、AuditLog。
5. 高风险 MCP tool 必须支持 approval / dry-run / rate limit。
```

原则：

```text
组件可发现，但执行必须受治理。
组件可扩展，但不能绕过 Runtime。
组件可复用，但不引入低代码编排作为核心定位。
```

---

## 28. Prompt, Config, and Template Assets

Langfuse 的 Prompt Management、Dify 的应用配置版本化、Langflow/Flowise 的模板生态都说明：生产 Agent 需要可版本化的非代码资产。

DimooRun 不负责设计 Prompt，但需要治理 Prompt、配置和模板资产的版本、引用、审计和发布关系。

资产类型：

```text
PromptAsset
ConfigAsset
AgentTemplate
DeploymentTemplate
PolicyTemplate
```

PromptAsset 字段：

```text
id
tenant_id
project_id
name
version
content_ref
variables_schema
visibility_level
created_by
created_at
metadata
```

ConfigAsset 字段：

```text
id
tenant_id
project_id
name
version
schema
content_ref
environment
created_by
created_at
```

模板原则：

```text
1. Template 用于快速创建 Agent Package / dimoorun.yaml / Deployment，不是低代码 Builder。
2. AgentVersion 必须记录引用的 PromptAsset / ConfigAsset 版本。
3. Prompt 和 Config 变更应产生 AuditLog。
4. 生产环境禁止隐式使用 latest，必须绑定明确版本。
5. Prompt 内容默认按 visibility policy 展示和脱敏。
6. PromptAsset / ConfigAsset 的大内容存入 Artifact Store，自身只保存 metadata、schema、version 和 content_ref。
7. Artifact retention 不能早于仍被 AgentVersion / Deployment 引用的 PromptAsset / ConfigAsset。
```

---

## 29. Runtime State Machines

DimooRun 必须显式定义状态机。状态机是重试、取消、恢复、幂等和 Console 展示的共同语义基础。

### 29.1 Run 状态机

```text
pending
  -> running
  -> interrupted
  -> succeeded
  -> failed
  -> cancelled
  -> timeout
```

合法流转：

```text
pending -> running
running -> interrupted
running -> succeeded
running -> failed
running -> cancelled
running -> timeout
interrupted -> running
interrupted -> cancelled
failed -> running      # retry
timeout -> running     # retry, if policy allows
```

终态：

```text
succeeded
failed
cancelled
timeout
```

### 29.2 Task 状态机

```text
queued
leased
running
retrying
succeeded
failed
dead_letter
cancelled
```

合法流转：

```text
queued -> leased
leased -> running
leased -> queued       # lease expired
running -> succeeded
running -> failed
running -> retrying
running -> cancelled
running -> dead_letter
retrying -> queued
failed -> retrying
failed -> dead_letter
```

### 29.3 RunAttempt 状态机

```text
running
succeeded
failed
timeout
cancelled
worker_lost
```

规则：

```text
1. 一个 Run 可以有多个 RunAttempt。
2. 同一时间一个 Run 只能有一个 active attempt。
3. Worker lease 过期后，新 Worker 可以创建新的 RunAttempt。
4. 旧 Worker 迟到写入结果时，必须通过 attempt_id 和 fencing token 拒绝覆盖新状态。
5. RunAttempt 是执行事实，不能删除，只能追加状态。
```

### 29.4 Interrupt / Resume 状态

```text
running -> interrupted
interrupted -> running
interrupted -> cancelled
interrupted -> timeout
```

中断规则：

```text
1. interrupted 不是失败，而是等待外部输入或人工审批。
2. interrupted Run 必须记录 interrupt_payload_ref。
3. resume 必须校验 capability、权限、thread_id、checkpoint_id 和 resume schema。
4. resume 会创建新的 RunAttempt 或恢复原框架线程，具体由 Adapter 决定。
```

### 29.5 幂等和并发控制

```text
1. Create Run 使用 tenant_id + project_id + endpoint + idempotency_key 去重。
2. Worker 完成 Task 使用 task_id + attempt_id + fencing_token 做并发保护。
3. cancel / retry / resume 都必须是幂等操作。
4. 终态 Run 不允许被普通 Worker 覆盖。
```

---

## 30. Checkpoint Boundary

Checkpoint 是 Agent 框架的运行时状态，不等同于 DimooRun 的平台状态。

边界：

| 概念 | 所属方 | 说明 |
| ---- | ------ | ---- |
| Run / Task / Attempt | DimooRun | 平台执行账本 |
| Event / AuditLog | DimooRun | 平台观测和审计事实 |
| Checkpoint payload | Agent Framework | LangGraph / DeepAgents 等框架状态 |
| CheckpointIndex | DimooRun | 平台对 checkpoint 的索引和治理元数据 |
| thread_id | 框架语义 + 平台索引 | 用于恢复、查询和会话关联 |

CheckpointIndex 只负责索引和治理，不强行理解业务 state：

```text
id
tenant_id
project_id
agent_id
agent_version_id
run_id
attempt_id nullable
session_id nullable
framework
thread_id
checkpoint_ns
checkpoint_id
checkpoint_uri
created_at
expires_at nullable
metadata
```

恢复规则：

```text
1. resume 必须同时校验 Run 状态和 checkpoint 可用性。
2. Run 状态以 DimooRun 为准；框架 checkpoint 是恢复输入。
3. 如果 Run 已终态，默认禁止 resume，除非显式开启 replay / fork。
4. checkpoint 缺失时返回 checkpoint_not_found。
5. checkpoint schema 或 adapter contract 不兼容时返回 checkpoint_incompatible。
6. checkpoint 清理不能破坏仍可 resume 的 Run。
```

生命周期策略：

```text
retention_by_agent
retention_by_environment
retention_by_run_status
manual_pin
legal_hold
archive_to_object_storage
```

---

## 31. Human-in-the-loop Governance

Human-in-the-loop 不是单个框架的 interrupt 特性，而是企业治理能力。

DimooRun 应把人工介入建模为一等对象。

核心对象：

```text
HumanTask
ApprovalRequest
ApprovalPolicy
ResumePayload
```

HumanTask 字段：

```text
id
tenant_id
project_id
run_id
attempt_id nullable
task_id nullable
type: approval | input_required | review | escalation
status: pending | approved | rejected | expired | cancelled
assignee_user_id nullable
assignee_role nullable
payload_ref
decision_ref nullable
expires_at nullable
created_at
updated_at
```

ApprovalPolicy 字段：

```text
id
tenant_id
project_id nullable
name
resource_type
action
risk_level
condition
required_role
timeout_seconds
on_timeout: reject | cancel_run | continue | escalate
```

运行规则：

```text
1. Adapter 可以产生 human_interrupt.required 事件。
2. Policy Engine 也可以在高风险 Tool、Model、Secret 或 Deployment 操作前创建 HumanTask。
3. HumanTask 必须进入审计日志。
4. 审批结果通过 resume payload 回到 Run。
5. 审批人不能审批自己触发的高风险操作，除非策略允许。
6. 审批超时必须有明确结果，不能无限悬挂。
```

---

## 32. Policy Engine

权限、Tool Gateway、Secret、Model Gateway、预算、审批和数据可见性不能各自为政，需要统一策略引擎。

Policy Engine 的职责是回答：

```text
谁，在什么上下文下，可以对什么资源，执行什么动作，附带什么限制。
```

策略类型：

```text
authz_policy
tool_policy
secret_policy
model_policy
data_visibility_policy
budget_policy
rate_limit_policy
approval_policy
execution_policy
retention_policy
```

Policy 输入：

```text
tenant_id
project_id
user_id
service_account_id nullable
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

Policy 决策：

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
expires_at nullable
metadata
```

原则：

```text
1. API、Worker、Tool Gateway、SecretProvider、ModelGatewayProvider 都必须调用 Policy Engine。
2. Policy Engine 不直接执行业务动作，只返回决策。
3. 所有 deny、require_approval、policy_violation 都必须写 AuditLog。
4. Policy 可以先用数据库规则实现，后续可替换 OPA / Cedar / Casbin / 自研 DSL。
5. Console 菜单权限只是 Policy 的展示结果，不是权限源头。
```

---

## 33. Artifact Store

Agent 运行过程中会产生大 payload 和文件，不能都塞进 Run、Event 或 Trace 表。

Artifact Store 用于存储：

```text
input payload
output payload
stream transcript
tool result
model raw response
retrieved context
generated file
uploaded file
trace attachment
evaluation dataset
error dump
```

Artifact 字段：

```text
id
tenant_id
project_id
run_id nullable
attempt_id nullable
event_id nullable
artifact_type
mime_type
size_bytes
storage_uri
checksum
visibility_level
retention_policy_id
created_by
created_at
expires_at nullable
metadata
```

存储后端：

```text
local filesystem for dev
S3-compatible object storage
MinIO
cloud object storage
database blob only for small payloads
```

访问规则：

```text
1. Run.input_ref、Run.output_ref、Event.payload_ref、Trace.attachment_ref 指向 Artifact。
2. Artifact 读取必须经过权限和数据可见性策略。
3. 大 payload 默认不进入日志。
4. Artifact retention 独立于 Run 元数据 retention。
5. 敏感 Artifact 应支持加密、脱敏和访问审计。
```

### 33.1 Backup / Restore / Disaster Recovery

Artifact、Event、CheckpointIndex 和平台元数据一旦进入生产环境，就需要明确备份恢复边界。DimooRun 不替代底层数据库或对象存储的备份系统，但需要定义平台级恢复语义。

备份范围：

```text
Platform Metadata Store
Event / AuditLog
Artifact metadata
Artifact object data
CheckpointIndex
Agent Package
PromptAsset / ConfigAsset / TemplateAsset
Policy
```

BackupPlan 字段：

```text
id
tenant_id
project_id nullable
name
scope: tenant | project | platform
targets
schedule
retention_days
storage_ref
status
created_at
updated_at
```

RestoreJob 字段：

```text
id
tenant_id
project_id nullable
backup_plan_id nullable
backup_ref
restore_scope
status
started_at
finished_at
validation_report_ref nullable
created_by
created_at
```

规则：

```text
1. restore 必须先做 dry-run validation，避免破坏现有 tenant / project 数据。
2. Artifact object data 和 metadata 必须校验 checksum。
3. 恢复后的历史 Run / Event / AuditLog 不应被重新解释为新执行。
4. checkpoint 恢复只恢复索引和可访问性，不保证跨框架版本可 resume。
5. Enterprise Mode 应定义 RPO / RTO 目标，并在 Console 展示最近备份状态。
```

---

## 34. Event / Trace / Audit 三账本模型

DimooRun 需要同时管理运行事实、观测链路和安全审计。三者相关，但不能混成一个概念。

| 账本 | 目的 | 示例 | 是否面向用户展示 |
| ---- | ---- | ---- | ---------------- |
| Event | 描述 Agent 执行过程中发生了什么 | run.started、tool.called、human_interrupt.required | 是 |
| Trace / Span | 描述调用链、耗时、模型和工具链路 | span、latency、token、cost | 是，偏调试 |
| AuditLog | 描述谁做了什么治理动作 | secret.read denied、run.cancel、policy_violation | 是，偏安全 |

关系：

```text
Run
  ├── Events
  ├── Trace / Spans
  ├── AuditLogs
  └── Artifacts
```

写入原则：

```text
1. Event 是 Runtime 语义，必须能支撑 Console Timeline。
2. Trace 是观测语义，可以导出到 OpenTelemetry、Langfuse、Phoenix。
3. AuditLog 是合规语义，不能因为 Trace 采样而丢失。
4. Event 可以采样一部分 payload，但关键状态变更不能采样。
5. AuditLog 默认不可变，保留周期通常长于 Trace。
6. Trace 可以关联 Event，但不能替代 Event。
7. 外部观测平台不可用时，DimooRun 仍必须保留最小 Event 和 AuditLog。
```

事件映射：

```text
framework event -> AgentEvent -> EventSink
callback span -> TraceSink
policy decision -> AuditLog
security violation -> Event + AuditLog
tool call -> Event + TraceSpan + optional AuditLog
model call -> Event + TraceSpan + ModelUsageSnapshot
```

---

## 35. Run Graph and Execution Provenance

Haystack 的 pipeline/component 抽象、Langflow/Flowise 的 workflow run log、Dify 的 workflow execution 都说明：复杂 AI 应用需要可解释的执行结构。

DimooRun 不定义用户 Agent 的内部编排 DSL，但可以把不同框架的执行过程映射为统一的 Run Graph，用于 Console、Trace、Eval 和排障。

Run Graph 是观测投影，不是编排源。

RunGraphNode 字段：

```text
id
run_id
attempt_id
node_key
node_type: model | tool | retriever | ranker | generator | router | human | custom
framework_node_id nullable
name
status
started_at
finished_at
latency_ms
input_ref nullable
output_ref nullable
metadata
```

RunGraphEdge 字段：

```text
id
run_id
source_node_id
target_node_id
edge_type
metadata
```

映射规则：

```text
1. LangGraph node event 映射为 RunGraphNode。
2. LangChain callback chain/tool/model 映射为 RunGraphNode。
3. Haystack pipeline component 映射为 RunGraphNode。
4. Tool Gateway 调用映射为 tool node。
5. Model Gateway 调用映射为 model node。
6. HumanTask 映射为 human node。
```

原则：

```text
1. Run Graph 用于可视化和分析，不参与调度决策。
2. 不能因为无法构建完整 Run Graph 而阻断 Run。
3. 未知框架细节可以退化为 custom node。
4. Run Graph 节点输入输出默认使用 Artifact ref，不直接存大 payload。
```

---

## 36. Dataset, Experiment, and Quality Loop

Langfuse 和 Phoenix 的经验说明：生产 Agent 平台不能只有在线 Trace，还需要 Dataset、Experiment、Eval 和反馈闭环。

DimooRun 的评估能力不应只是离线脚本，而应和 Run、AgentVersion、Deployment 绑定。

核心对象：

```text
Dataset
DatasetItem
Experiment
ExperimentRun
EvaluationResult
Feedback
```

Dataset 字段：

```text
id
tenant_id
project_id
name
description
source: manual | production_sample | failure_case | imported
schema
visibility_level
created_at
updated_at
```

Experiment 字段：

```text
id
tenant_id
project_id
name
agent_id
baseline_agent_version_id nullable
candidate_agent_version_id
dataset_id
evaluator_config
status
created_at
updated_at
```

反馈闭环：

```text
production run
  ↓
feedback / failure / sample
  ↓
dataset item
  ↓
experiment run
  ↓
evaluation result
  ↓
quality gate
  ↓
promote / block / rollback
```

原则：

```text
1. Dataset 可以来自生产 Run，但必须执行脱敏和权限检查。
2. ExperimentRun 必须记录 AgentVersion、PromptAsset、ConfigAsset、ModelPolicy。
3. EvaluationResult 不能覆盖原始 Run 事实，只能作为附加结果。
4. 质量门禁作用于 Deployment promotion，不直接修改 AgentVersion。
```

---

## 37. 存储边界

### 37.1 Platform Metadata Store

推荐使用 Postgres，存储：

* tenants
* projects
* users
* service_accounts
* roles
* permissions
* api_keys
* idempotency_records
* agents
* agent_versions
* deployments
* agent_instances
* published_surfaces
* ingress_routes
* execution_profiles
* scheduled_runs
* batch_runs
* replay_jobs
* runs
* run_attempts
* tasks
* events
* run_graph_nodes
* run_graph_edges
* artifacts
* tools
* catalog_items
* prompt_assets
* config_assets
* templates
* secrets
* model_gateways
* model_usage_snapshots
* policies
* human_tasks
* approval_requests
* approval_policies
* datasets
* experiments
* evaluation_results
* feedback
* memory_blocks
* notification_channels
* alert_rules
* incident_events
* backup_plans
* restore_jobs
* audit_logs

Platform Metadata Store 通用存储规则：

```text
1. 所有表包含通用审计与软删除字段。
2. 默认查询必须过滤 is_deleted=true，除非调用方显式请求 include_deleted 且具备权限。
3. 软删除不破坏历史 Run、Event、Trace、Artifact、AuditLog 的可追溯性。
4. retention purge job 可以物理清理已满足保留期的软删除数据，但必须生成 AuditLog 或 IncidentEvent。
5. 扩展 metadata 表也必须使用 tenant_id / project_id 外键，不能只存裸字符串。
6. 关键业务唯一性必须由数据库约束保护，例如 Project slug、Agent name、AgentVersion version、Deployment scope、API key hash、Idempotency key。
```

### 37.2 Framework Runtime Store

不同框架的运行时存储。

LangGraph：

* checkpoint
* thread state
* store

LangChain Agent：

* callbacks trace
* memory，可选

DeepAgents：

* checkpoint
* filesystem state
* subagent state

DimooRun 可以提供默认后端，但不强制接管用户业务存储。

### 37.3 Agent Memory Store

Agent Memory Store 是 Agent 用于长期记忆的 key-value / document memory。

它不等同于业务数据库，也不等同于框架 checkpoint。

用途：

```text
用户偏好
长期上下文
历史摘要
个性化记忆
Agent 内部资料
```

DimooRun 不强制接管所有 memory，但应提供可治理的 Store Provider。

治理能力：

```text
tenant 隔离
project 隔离
agent 隔离
权限控制
retention
redaction
audit
export / delete
```

MemoryBlock 字段：

```text
id
tenant_id
project_id
agent_id nullable
session_id nullable
subject_type: user | organization | agent | task | custom
subject_id
memory_type: profile | preference | fact | summary | instruction | custom
content_ref
source_run_id nullable
confidence nullable
visibility_level
retention_policy_id nullable
created_at
updated_at
```

Memory 规则：

```text
1. MemoryBlock 是长期记忆事实或摘要，不是 checkpoint。
2. Agent 可以读取被授权的 MemoryBlock，但不能默认读取整个租户记忆。
3. 写入 MemoryBlock 应产生 Event 和 AuditLog。
4. 用户相关 memory 必须支持导出、删除、retention 和 redaction。
5. Memory 召回可以通过 Semantic Store 实现，但 MemoryBlock 是治理对象。
```

### 37.4 Semantic Store

Semantic Store 是带 embedding / vector search 的 memory/store。

用途：

```text
长期语义记忆
相似历史检索
个性化上下文召回
Agent 经验沉淀
```

推荐后端：

```text
Postgres + pgvector
Qdrant
Milvus
Weaviate
Pinecone
Custom Vector Store
```

SemanticStoreProvider 字段：

```text
id
tenant_id
project_id nullable
name
provider_type
embedding_model
embedding_gateway_id nullable
connection_ref
retention_policy_id nullable
status
metadata
```

原则：

```text
1. DimooRun 不直接理解 memory 的业务语义。
2. 平台负责 Store Provider、权限、隔离、审计、retention 和 redaction。
3. embedding 调用应优先经过 Model Gateway。
4. Agent Package 声明需要的 memory / semantic store capability。
5. Console 可以查看 Store 配置和用量，但默认不展示敏感 memory 明文。
```

### 37.5 Agent Business Store

用户 Agent 自己访问的业务存储：

* 业务数据库
* 向量数据库
* 知识库
* 文件存储
* 用户自定义 memory store

DimooRun 不直接管理业务 schema，只负责连接、权限、Secret 和审计边界。

---

## 38. API 设计

### 38.1 API Surface Matrix

DimooRun API 分为 Native、Compatibility、Admin、Runtime、Extension 五类。

| API Surface | 路径前缀 | 目的 |
| ----------- | -------- | ---- |
| Native API | `/v1` | DimooRun 原生平台语义 |
| Compatibility API | `/compat/langgraph`、`/compat/agent-protocol` | 兼容 LangGraph / Agent Protocol 生态 |
| Admin API | `/v1/admin` | Tenant、Project、User、Role、Policy、Gateway 等管理 |
| Runtime API | `/v1/agents`、`/v1/runs`、`/v1/tasks` | Agent 调用、任务、Run 查询和控制 |
| Extension API | `/v1/extensions`、`/v1/webhooks` | 事件订阅、扩展注册、扩展审计 |

所有 API 都必须：

```text
auth
tenant / project scope
Policy Engine check
AuditLog for write / deny / high-risk action
request_id
idempotency for write operations
```

### 38.2 通用规则

所有写请求建议支持：

```http
Idempotency-Key: <key>
X-Request-Id: <request_id>
```

幂等规则：

```text
1. 同一个 tenant_id + project_id + endpoint + idempotency_key 在一定时间窗口内只产生一个业务结果。
2. 幂等状态统一记录到 idempotency_records。
3. 相同 idempotency_key 但 request_hash 不一致时返回 idempotency_conflict。
4. API 不允许只把幂等键散落在 Run / Task 表中。
```

删除规则：

```text
1. 所有 DELETE 语义默认执行 soft delete，不执行 hard delete。
2. archive 与 soft delete 分离：archive 是生命周期状态，soft delete 是默认业务可见性删除。
3. 需要恢复、保留期清理或物理清理时，必须通过明确的 Admin / Governance API 或后台任务完成。
```

### 38.3 Agent 管理 API

```http
POST   /v1/agents
GET    /v1/agents
GET    /v1/agents/{agent_id}
PATCH  /v1/agents/{agent_id}
DELETE /v1/agents/{agent_id}
```

### 38.4 Agent Version API

```http
POST /v1/agents/{agent_id}/versions
GET  /v1/agents/{agent_id}/versions
GET  /v1/agents/{agent_id}/versions/{version}
```

### 38.5 Deployment Runtime Control API

```http
GET  /v1/deployments
GET  /v1/deployments/{deployment_id}
POST /v1/deployments/{deployment_id}/activate
POST /v1/deployments/{deployment_id}/pause
POST /v1/deployments/{deployment_id}/resume
POST /v1/deployments/{deployment_id}/drain
POST /v1/deployments/{deployment_id}/stop
POST /v1/deployments/{deployment_id}/restart
GET  /v1/deployments/{deployment_id}/instances
```

规则：

```text
1. activate / pause / resume / drain / stop 修改 Deployment desired_status。
2. restart 不创建新版本，只驱逐 AgentInstance 并触发后续重新加载。
3. instances 返回 Worker 上的实际加载状态，用于 Console 展示和排障。
4. 所有控制动作必须经过 Policy Engine，并写 AuditLog。
```

### 38.6 Runtime API

同步调用：

```http
POST /v1/agents/{agent_id}/invoke
```

异步任务：

```http
POST /v1/agents/{agent_id}/tasks
GET  /v1/tasks/{task_id}
POST /v1/tasks/{task_id}/cancel
```

流式调用：

```http
POST /v1/agents/{agent_id}/stream
```

Run 查询：

```http
GET  /v1/runs/{run_id}
GET  /v1/runs/{run_id}/events
GET  /v1/runs/{run_id}/attempts
POST /v1/runs/{run_id}/cancel
POST /v1/runs/{run_id}/resume
POST /v1/runs/{run_id}/retry
POST /v1/runs/{run_id}/replay
```

如果 Agent 不支持 resume，则返回 capability_not_supported。

### 38.7 LangGraph Compatibility API

核心路由：

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

映射规则：

```text
assistant_id -> Deployment / AgentVersion
thread_id -> Session.thread_id / CheckpointIndex.thread_id
run_id -> Run.id
stream -> Streaming Runtime
checkpoint -> Framework Runtime Store + CheckpointIndex
```

约束：

```text
1. Compatibility API 创建的 Run 必须写入 DimooRun Run / Task / Event。
2. Compatibility API 不允许绕过 API Key、Tenant、Project、Policy。
3. 不支持的 LangGraph Platform 特性返回 compatibility_not_supported。
4. 返回结构尽量保持 LangGraph SDK 兼容，但内部状态以 DimooRun 状态机为准。
```

### 38.8 Admin / Governance API

```http
GET  /v1/policies
POST /v1/policies
GET  /v1/artifacts/{artifact_id}
GET  /v1/human-tasks
POST /v1/human-tasks/{task_id}/approve
POST /v1/human-tasks/{task_id}/reject
GET  /v1/model-gateways
POST /v1/model-gateways
GET  /v1/published-surfaces
POST /v1/published-surfaces
GET  /v1/ingress-routes
POST /v1/ingress-routes
GET  /v1/catalog/items
GET  /v1/datasets
POST /v1/datasets
GET  /v1/experiments
POST /v1/experiments
GET  /v1/service-accounts
POST /v1/service-accounts
GET  /v1/schedules
POST /v1/schedules
GET  /v1/batch-runs
POST /v1/batch-runs
GET  /v1/notifications/channels
POST /v1/notifications/channels
GET  /v1/alerts/rules
POST /v1/alerts/rules
GET  /v1/backups/plans
POST /v1/backups/plans
```

这些 API 可分阶段实现，但路径边界需要在设计期固定。

### 38.9 API Contract Governance

DimooRun 的 Native API、Compatibility API、Admin API 和 SDK 都需要明确兼容性治理，尤其是 LangGraph Compatibility Mode 不能只靠实现经验维持。

机制：

```text
OpenAPI schema source of truth
OpenAPI diff check
backward compatibility tests
Compatibility API golden tests
SDK version matrix
deprecated endpoint policy
error code registry
contract test fixtures
```

规则：

```text
1. API breaking change 必须提升 api_schema_version。
2. Compatibility API breaking change 必须提升 compat_api_version，并给出迁移说明。
3. OpenAPI diff 必须在 CI 中阻止未声明的 breaking change。
4. Python SDK / TypeScript SDK 需要记录支持的 server version range。
5. LangGraph-compatible API 需要维护 assistants / threads / runs / stream 的 golden fixtures。
6. 错误码必须稳定，前端和 SDK 不应依赖错误文本判断行为。
```

---

## 39. SDK Design

DimooRun SDK 的职责是封装 Runtime / Admin / Compatibility API，降低接入成本。

SDK 不负责实现 Agent 编排逻辑，不提供新的 Agent DSL。

SDK 类型：

```text
Python SDK
TypeScript SDK
LangGraph-compatible SDK usage
Generated SDK from OpenAPI
```

Python SDK：

```text
注册 Agent Package
创建 Run / Task
读取 Run / Event / Artifact
stream SSE events
resume / cancel / retry
调用 Compatibility API
```

TypeScript SDK：

```text
Console API client
浏览器 stream client
Run / Task 查询
Event Timeline 查询
HumanTask 审批
Dataset / Experiment 查询
```

SDK 原则：

```text
1. SDK 只封装平台 API，不隐藏平台状态机。
2. SDK 必须暴露 request_id、run_id、task_id、event_id。
3. SDK stream client 必须支持 Last-Event-ID 和 reconnect。
4. SDK 错误类型必须保留平台 error code。
5. TypeScript SDK 从 OpenAPI 生成，手写层只封装 ergonomics。
6. LangGraph-compatible 使用方式应尽量保持用户现有调用习惯。
7. CLI 应优先复用 Python SDK / API client，不直接绕过 server 领域逻辑。
```

示例：

```python
from dimoorun import DimooRun

client = DimooRun(api_key="...", base_url="...")

run = client.agents.invoke(
    agent_id="support-agent",
    input={"message": "hello"},
)
```

---

## 40. Task Scheduler

Task Scheduler 负责定义任务接口、排队、租约和执行流程。

HA / Scaling Design 负责分布式一致性、fencing token、lease reaper、quota、partition 和多实例扩展。

### 40.1 执行流程

```text
HTTP request
  ↓
Validate auth / permission / quota
  ↓
Check idempotency
  ↓
Create Run
  ↓
Create Task
  ↓
Enqueue
  ↓
Worker leases task
  ↓
Create RunAttempt
  ↓
Load Adapter
  ↓
Execute Agent
  ↓
Map Events
  ↓
Write result / trace
  ↓
Complete Run / Task
```

### 40.2 TaskBackend 接口

```python
from typing import Protocol


class TaskBackend(Protocol):
    async def enqueue(self, task: dict) -> str:
        ...

    async def lease(self, queue: str, worker_id: str, lease_seconds: int) -> dict | None:
        ...

    async def heartbeat(self, task_id: str, worker_id: str) -> None:
        ...

    async def complete(self, task_id: str, worker_id: str) -> None:
        ...

    async def fail(self, task_id: str, worker_id: str, error: dict) -> None:
        ...

    async def cancel(self, task_id: str) -> None:
        ...
```

### 40.3 生产级机制

必须设计：

```text
任务租约 lease
Worker heartbeat
任务回收
重试策略
指数退避
死信队列 DLQ
幂等 key
重复消费处理
队列优先级
并发限制
```

### 40.4 Scheduled / Batch / Replay Runtime

DimooRun 不提供业务编排 DSL，但企业运行时需要支持定时执行、批量执行和历史回放。这些能力属于 Task Scheduler 的运行形态，而不是 Agent 内部逻辑。

对象：

```text
ScheduledRun
BatchRun
ReplayJob
```

ScheduledRun 字段：

```text
id
tenant_id
project_id
deployment_id
schedule_type: once | cron
cron_expr nullable
run_at nullable
input_ref
status
created_by
created_at
updated_at
```

BatchRun 字段：

```text
id
tenant_id
project_id
deployment_id
source_type: dataset | file | query | manual
source_ref
status
total_count
succeeded_count
failed_count
created_by
created_at
updated_at
```

ReplayJob 字段：

```text
id
tenant_id
project_id
source_run_id nullable
source_dataset_id nullable
baseline_agent_version_id nullable
candidate_agent_version_id nullable
override_config_ref nullable
status
created_by
created_at
updated_at
```

规则：

```text
1. ScheduledRun / BatchRun / ReplayJob 最终都必须展开为 Run / Task。
2. replay 可以复用历史 input，但必须重新执行并产生新的 Run。
3. replay 不修改历史 Run / Event / Trace。
4. batch 必须受 tenant / project / agent 并发配额约束。
5. dataset replay 可用于回归评估和发布前验证。
6. cron 调度失败、跳过、补跑都必须可审计。
```

---

## 41. Worker Pool

Worker 职责：

* 拉取任务
* 获取任务租约
* 定期 heartbeat
* 加载 AgentVersion
* 按 Deployment desired_status 决定是否接收、加载、drain 或卸载 AgentInstance
* 读取 framework / adapter
* 选择 AgentAdapter
* 通过 Adapter.load() 创建或复用 AgentInstance
* 构建 RuntimeContext
* 注入 config / secrets / permissions
* 创建 RunAttempt
* 执行 Agent
* 处理 stream events
* 写 Run 状态
* 写 Attempt 状态
* 写 Event
* 写 CheckpointIndex，可选
* 写 Trace
* 处理失败、重试、取消、超时

Worker 应尽可能无状态。

AgentInstance 缓存规则：

```text
cache_key = deployment_id + agent_version_id + execution_profile_id
```

```text
1. Worker 可以缓存 AgentInstance 以避免每次 Run 冷加载。
2. 缓存不得改变 AgentVersion 不可变语义。
3. Deployment restart / stop / drain 可以要求 Worker 驱逐或卸载缓存实例。
4. Worker 必须上报 AgentInstance heartbeat、running_runs、last_used_at 和 error。
5. 长时间 idle 的实例可以按策略 evict。
6. Worker 崩溃后，AgentInstance 视为 lost；Run / Task 恢复仍由 Task lease 和 checkpoint 机制负责。
```

---

## 42. HA / Scaling Design

DimooRun 的生产运行能力依赖明确的任务租约、心跳、重试、取消和并发控制。

### 42.1 MVP 必须设计

```text
lease
heartbeat
lease timeout
retry
dead letter
idempotency
```

### 42.2 Production 必须实现

```text
lease reaper
fencing token
Redis pub/sub cancel
tenant concurrency quota
project concurrency quota
queue partition
```

### 42.3 Enterprise 演进

```text
run sharding
leaderless reaper
multi-region
Kafka partition
Temporal backend
worker autoscaling
```

Fencing token 规则：

```text
1. Worker A lease task，获得 token=1。
2. Worker A 卡住，lease 过期。
3. Worker B 重新 lease task，获得 token=2。
4. Worker A 恢复后尝试写结果。
5. 系统发现 token=1 已过期，拒绝 Worker A 写入。
```

Task 写入规则：

```text
1. Task 状态更新必须带 task_id + attempt_id + fencing_token。
2. 终态写入必须使用 compare-and-set。
3. lease reaper 只负责回收过期 lease，不直接判定业务失败。
4. cancel 应通过共享状态和 pub/sub 同时通知 Worker。
5. Worker 必须周期性 heartbeat，heartbeat 失败后进入可恢复路径。
```

队列分区：

```text
by tenant
by project
by priority
by agent
by resource class
```

并发配额：

```text
tenant_max_running_runs
project_max_running_runs
agent_max_concurrency
worker_max_concurrency
model_gateway_rate_limit
tool_gateway_rate_limit
```

---

## 43. 权限系统

### 43.1 权限分类

1. 平台权限

   * 创建 Agent、部署 Agent、调用 Agent、查看 Run、取消 Task、查看 Trace、管理 Secret、管理用户和角色。

2. Agent 运行时权限

   * Agent 对工具、数据、模型、知识库、外部系统的访问权限。

3. 数据可见性权限

   * 谁能看 input、output、prompt、tool arguments、retrieved context、error stack、trace export。

### 43.2 RBAC MVP

| 角色        | 权限范围                     |
| --------- | ------------------------ |
| Owner     | 管理租户内所有资源                |
| Admin     | 管理用户、权限、Agent、Deployment |
| Developer | 注册 Agent、发布版本、查看运行结果     |
| Operator  | 查看运行状态、取消、重试、回滚          |
| Auditor   | 查看审计日志和运行记录              |
| Viewer    | 只读查看                     |
| EndUser   | 调用授权 Agent               |

原则：

```text
权限基于 resource:action，不基于菜单。
菜单只是前端展示结果。
后端接口必须强制鉴权。
```

---

## 44. Tool Gateway

Tool Gateway 是企业 Agent Runtime 的核心安全边界。

```text
Agent
  ↓
Tool Gateway
  ↓
权限校验
  ↓
参数校验
  ↓
审计
  ↓
限流
  ↓
实际企业系统
```

职责：

* 工具注册
* 工具 schema
* 工具权限
* 租户 / 项目隔离
* 参数校验
* 调用审计
* 敏感操作二次确认
* 失败重试
* 超时控制
* 成本和频率限制
* dry-run
* 回滚策略

风险等级：

```text
read
write
external_side_effect
destructive
financial
privileged
```

高风险 Tool 应支持：

```text
human approval
dry-run
二次确认
审计
回滚策略
调用前后快照
```

---

## 45. Model Gateway / Provider Governance

DimooRun 不直接重做模型供应商聚合、渠道管理、倍率计费、余额、充值、分组额度、模型映射等专业资源管理能力。

模型资源治理默认通过外部 Model Gateway 完成，优先适配 New API 这类 OpenAI-compatible 的模型资源管理平台。

```text
Agent
  ↓
DimooRun RuntimeContext / Policy
  ↓
ModelGatewayProvider
  ↓
New API / LiteLLM / Cloud Gateway / Custom Gateway
  ↓
OpenAI / Anthropic / Gemini / DeepSeek / Qwen / Local Model
```

职责边界：

| 能力                       | DimooRun                        | Model Gateway / New API                 |
| ------------------------ | ------------------------------- | --------------------------------------- |
| Agent 执行归因              | 负责                              | 不负责                                     |
| Run / Task / Event 关联    | 负责                              | 不负责                                     |
| Tenant / Project 策略引用    | 负责                              | 可通过分组、令牌、渠道配合                         |
| 模型供应商 Key 管理           | 不直接管理，保存网关凭证引用                  | 负责                                      |
| 渠道路由、模型映射、倍率           | 不重复实现                           | 负责                                      |
| 余额、充值、最终计费             | 不重复实现                           | 负责                                      |
| 单次 Run 的 usage / cost 快照 | 记录网关返回值，用于审计、评估和展示              | 负责计算或返回                                |
| Agent 级预算、租户策略、熔断       | 负责运行时策略判断                       | 提供底层额度、限流和模型可用性                       |

DimooRun 需要保留的领域对象不是 `ModelProviderAccount`，而是模型网关引用和运行时策略：

```text
ModelGateway
ModelGatewayCredentialRef
ModelPolicy
ModelUsageSnapshot
BudgetPolicy
```

ModelGateway 字段：

```text
id
tenant_id
project_id nullable
name
provider_type: newapi | litellm | openai_compatible | custom
base_url
credential_ref
default_model_group nullable
status
metadata
created_at
updated_at
```

ModelPolicy 字段：

```text
id
tenant_id
project_id nullable
agent_id nullable
agent_version_id nullable
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

ModelUsageSnapshot 字段：

```text
run_id
attempt_id
gateway_id
gateway_request_id nullable
model
provider nullable
prompt_tokens
completion_tokens
total_tokens
cost
currency
raw_usage
created_at
```

运行时规则：

```text
1. Agent Package 不应直接暴露底层模型供应商 Key。
2. Worker 注入的是 Model Gateway endpoint 和受控 credential 引用。
3. 模型调用的最终路由、渠道选择、倍率和计费由 New API 等 Model Gateway 负责。
4. DimooRun 从 callback、网关响应或观测事件中提取 usage / cost，写入 ModelUsageSnapshot。
5. DimooRun 的预算策略用于运行时准入、熔断、审批和审计，不替代网关账务系统。
6. 如果 Agent 绕过 Model Gateway 直连模型供应商，平台应标记为 policy_violation 或 unsupported_usage_accounting。
```

MVP 可只支持 OpenAI-compatible Model Gateway：

```text
base_url
api_key_ref
default_model
usage extraction
run cost attribution
```

---

## 46. Secret 管理

SecretProvider 接口：

```python
from typing import Protocol


class SecretProvider(Protocol):
    async def get_secret(
        self,
        tenant_id: str,
        project_id: str | None,
        secret_name: str,
        context: RuntimeContext,
    ) -> str:
        ...
```

要求：

```text
前端不展示 secret 明文。
日志和 Trace 不记录 secret 明文。
Agent 只能获得被授权的 secret。
Secret 使用需要记录 last_used_at 和审计日志。
```

---

## 47. 可观测性

### 47.1 需要记录

* request_id
* run_id
* attempt_id
* task_id
* trace_id
* tenant_id
* project_id
* user_id
* agent_id
* agent_version
* framework
* adapter
* input
* output
* event
* tool call
* model usage
* latency
* cost
* error
* checkpoint

### 47.2 EventSink 接口

```python
from typing import Protocol


class EventSink(Protocol):
    async def emit(self, event: dict) -> None:
        ...
```

实现：

* PostgresEventSink
* RedisStreamEventSink
* KafkaEventSink
* OpenTelemetryEventSink
* LangfuseEventSink
* PhoenixEventSink

### 47.3 指标

```text
run_total
run_success_total
run_failed_total
run_timeout_total
run_cancelled_total
run_interrupted_total
task_queue_size
task_latency_seconds
run_latency_seconds
attempt_total
tool_call_total
tool_error_total
llm_token_total
llm_cost_total
checkpoint_total
worker_heartbeat_lag
```

### 47.4 脱敏、采样和保留策略

必须支持：

```text
Redaction Policy
Visibility Policy
Retention Policy
Sampling Policy
PII Handling
```

### 47.5 Notification / Alerting

DimooRun 的告警不是普通消息推送，而是 Runtime / Ops 事件的治理出口。它用于把失败、成本异常、队列积压、Worker 异常、审批超时和安全事件推送给负责人。

NotificationChannel 字段：

```text
id
tenant_id
project_id nullable
name
channel_type: email | webhook | slack | teams | feishu | dingtalk | pagerduty | custom
target_ref
secret_ref nullable
status
created_at
updated_at
```

AlertRule 字段：

```text
id
tenant_id
project_id nullable
name
condition
severity: info | warning | critical
channels
dedupe_window_seconds
cooldown_seconds
status
created_at
updated_at
```

IncidentEvent 字段：

```text
id
tenant_id
project_id nullable
alert_rule_id nullable
severity
status: open | acknowledged | resolved
source_event_id nullable
run_id nullable
task_id nullable
message
created_at
updated_at
```

典型告警：

```text
run_failed_rate_high
task_queue_backlog_high
worker_heartbeat_lag_high
model_cost_threshold_exceeded
budget_near_exhausted
human_task_timeout
policy_violation_detected
webhook_delivery_failed
backup_failed
```

规则：

```text
1. 告警触发来源必须可追溯到 Event、Metric、AuditLog 或 Backup/Restore 状态。
2. 通知发送失败不能影响核心 Runtime。
3. 高风险安全事件必须进入 AuditLog。
4. AlertRule 受 Tenant / Project 权限和 Policy Engine 管理。
5. Console 展示 incident 状态，但不替代企业 ITSM / Pager 系统。
```

---

## 48. 前端 Console 设计

### 48.1 定位

DimooRun Console 是 Runtime Control Plane 的主要交互入口，不是低代码 Agent Builder。

Console 的核心价值不是展示菜单，而是让用户清楚看到：

```text
Agent 当前是否可运行
Deployment 当前是否接收新请求
Worker 是否健康
AgentInstance 加载在哪些 Worker 上
Run 为什么失败
Task 为什么积压
成本和 Token 消耗在哪里
高风险 Tool / Secret / Model 调用是否合规
失败 Run 能否 replay、对比和沉淀为 Dataset
```

产品定位：

```text
Runtime Operations First
```

也就是首屏和核心交互优先服务运行、排障、治理和发布，而不是服务 Agent 编排创作。

Console 不做：

```text
拖拽 Agent 编排画布
Prompt 设计器
知识库构建器
业务 Workflow Builder
业务 Tool 开发 IDE
```

Console 必须做：

```text
运行状态可见
部署状态可控
失败原因可追
治理策略可审
成本用量可归因
历史运行可 replay
版本变化可对比
```

### 48.2 技术栈

```text
Vue 3
TypeScript
Vite
Vue Router
Pinia
Naive UI
ECharts
Monaco Editor
Axios / TanStack Query
openapi-typescript / orval
```

### 48.3 产品设计原则

```text
1. 信息密度高，但层次清晰。
2. 默认展示运行事实，不用营销式大卡片堆砌。
3. 状态颜色必须稳定：success / warning / danger / neutral / running。
4. 每个列表都支持过滤、搜索、排序和保存视图。
5. 每个资源详情页都能反查关联对象。
6. 任何高风险操作都必须二次确认并展示影响范围。
7. Console 菜单权限只是展示结果，真实权限以后端 Policy Engine 为准。
8. 所有 destructive / privileged 操作必须产生 AuditLog。
9. Debug 页面允许 replay 和对比，但不允许修改历史 Run。
10. 前端必须通过 OpenAPI 生成 SDK，不手写散落的请求逻辑。
```

视觉方向：

```text
风格：专业、克制、精致、工程化。
参考气质：Linear / Datadog / Grafana / Vercel / Supabase / Langfuse。
不采用：低代码画布风、营销落地页风、过度渐变装饰、玩具感后台。
布局：左侧主导航 + 顶部环境/项目切换 + 内容区。
核心组件：数据表、状态徽标、时间线、抽屉详情、命令菜单、差异对比、指标图。
```

### 48.4 信息架构

Console 以运行和治理组织信息，而不是按数据库对象机械排列。

一级分组：

```text
Overview
Runtime
Deployments
Observability
Governance
Quality
Platform
```

推荐导航：

```text
Overview
  Dashboard

Runtime
  Agents
  Deployments
  Runs
  Tasks
  Workers
  Agent Instances
  Debug / Replay

Observability
  Events
  Traces
  Run Graph
  Costs
  Alerts

Governance
  Policies
  Human Tasks
  Tools
  Model Gateways
  Secrets
  Service Accounts
  API Keys
  Audit Logs

Quality
  Datasets
  Experiments
  Evaluation Results

Platform
  Published Surfaces
  Compatibility
  Catalog
  Backups
  Users
  Roles
  Settings
```

### 48.5 MVP 菜单

```text
Dashboard
Agents
Deployments
Compatibility
Published Surfaces
Runs
Tasks
Events
Debug / Replay
Human Tasks
Policies
API Keys
Settings
```

MVP 菜单虽然简化，但页面设计要保留 Phase 2 信息架构，不要后续重构导航模型。

### 48.6 Phase 2 菜单

```text
Dashboard
Agents
Deployments
Runs
Tasks
Traces
Run Graph
Debug / Replay
Datasets
Experiments
Catalog
Tools
Model Gateways
Secrets
Service Accounts
API Keys
Users
Roles
Alerts
Backups
Audit Logs
Settings
```

### 48.7 核心页面

Dashboard：

* 今日 Run 数
* 成功率
* 失败率
* 平均耗时
* P95 耗时
* P99 耗时
* 队列积压
* Worker 状态
* Deployment 健康状态
* AgentInstance 数量
* Token 消耗
* 成本
* 错误趋势
* Top failed agents
* Top cost agents
* 最近 critical alerts

Dashboard 首屏布局：

```text
顶部：tenant / project / environment selector
第一行：核心 KPI compact cards
第二行：Run volume / success rate / cost trend
第三行：queue backlog / worker health / deployment health
第四行：recent failures / active alerts / pending human tasks
```

Agents：

* Agent 列表
* AgentVersion 列表
* framework / adapter
* capabilities
* manifest 查看
* 调用入口
* 关联 Deployments
* 最近 Run 状态
* 最近发布版本

Agent 详情应强调：

```text
Agent 是逻辑对象。
AgentVersion 是不可变包。
Deployment 才是运行入口。
AgentInstance 是 Worker 上的实际加载实例。
```

Deployments：

* deployment_id
* agent / version / environment
* desired_status / runtime_status
* activate / pause / resume / drain / stop / restart
* 当前 AgentInstance 数量
* running runs
* queue backlog
* 最近错误
* 所在 Worker
* 实例启动时间
* 最近 heartbeat
* 当前 ExecutionProfile
* 绑定 Policy / ModelGateway / Secret / PublishedSurface

Deployment 详情布局：

```text
Header:
  agent name / version / environment / desired_status / runtime_status

Operations:
  activate / pause / resume / drain / stop / restart / rollback

Health:
  readiness / recent errors / queue backlog / running runs / worker distribution

Instances:
  worker_id / status / loaded_at / running_runs / heartbeat_at / last_error

Config:
  execution_profile / policy / model_gateway / secrets / published surfaces

Activity:
  deployment events / audit logs / recent runs
```

Runs：

* run_id
* agent
* framework
* adapter
* version
* user
* status
* latency
* cost
* started_at
* finished_at
* trigger: api | schedule | replay | batch | compatibility
* deployment
* trace_id

Run 详情：

* input
* output
* attempts
* events
* tool calls
* model calls
* token / cost breakdown
* errors
* trace
* checkpoint
* artifacts
* audit trail
* replay actions

Run 详情是 Console 的核心页面，应以 Timeline 为主：

```text
左侧：event timeline
中间：当前选中 event / span / tool call / model call 详情
右侧：run metadata、cost、attempts、checkpoint、policy decisions
底部：input / output / artifacts / logs tabs
```

Timeline 事件类型：

```text
run.started
task.leased
adapter.loaded
agent.event
model.called
tool.called
human_interrupt.required
checkpoint.created
policy.decision
artifact.created
run.succeeded
run.failed
```

Tasks：

* task_id
* run_id
* status
* attempt
* queue
* worker_id
* heartbeat_at
* error
* lease_until
* fencing_token
* retry_count
* dead_letter_reason

Events / Trace：

* 以 Timeline 展示通用事件和框架特定事件。
* Trace 页面展示 span tree、latency waterfall、model/tool cost。
* Event 页面展示运行事实，不因 Trace 采样而消失。

Debug / Replay：

* 从历史 Run 派生 replay
* 使用相同 AgentVersion 复现问题
* 使用 candidate AgentVersion 对比结果
* override config / model / prompt version
* 对比 output、latency、cost、event sequence、error
* 将失败案例沉淀为 DatasetItem

Debug / Replay 工作流：

```text
选择失败 Run
  ↓
查看失败 event / trace / error
  ↓
创建 replay
  ↓
选择相同版本或 candidate version
  ↓
可选 override config / model / prompt asset
  ↓
执行 replay
  ↓
对比 output / latency / cost / events / errors
  ↓
沉淀 DatasetItem 或创建 Experiment
```

Human Tasks：

* 待审批任务
* 来源 Run / Tool / Secret / Model / Deployment
* 风险等级
* payload 摘要
* approve / reject / escalate
* 审批历史

Governance 页面：

```text
Policies：策略列表、匹配范围、最近命中、deny / approval 统计。
Tools：工具 schema、risk_level、approval policy、最近调用。
Model Gateways：gateway 状态、模型组、成本、限流、错误。
Secrets：secret 引用、last_used_at、使用审计，不展示明文。
Service Accounts：机器身份、scopes、API keys、last_used_at。
API Keys：创建、禁用、scope、过期时间、最近使用。
Audit Logs：按 actor / action / resource / result / request_id 检索。
```

API Keys：

* 创建 API Key
* 禁用 API Key
* 查看最近使用时间
* 绑定 scopes

Service Accounts / Alerts / Backups / Tools / Secrets / Users / Roles 可在 Phase 2+ 完善。

### 48.8 关键交互

全局能力：

```text
tenant / project / environment switcher
global search
command menu
saved filters
time range selector
live refresh / pause refresh
copy id / copy curl
deep link to resource
drawer detail view
bulk action with confirmation
```

高风险操作确认：

```text
pause deployment
drain deployment
stop deployment
restart deployment
rollback deployment
disable api key
rotate secret
approve destructive tool call
delete / archive resource
restore backup
```

确认弹窗必须展示：

```text
影响对象
影响环境
是否影响新 Run
是否影响已有 Run
是否会写 AuditLog
是否可回滚
```

### 48.9 状态与空态

状态表达必须统一：

```text
success: succeeded / ready / active
warning: degraded / retrying / pending approval
danger: failed / timeout / policy denied / dead letter
neutral: draft / paused / stopped / archived
running: running / warming_up / draining / loading
```

空态不写营销文案，应给出直接动作：

```text
No agents -> Register Agent
No deployments -> Deploy an AgentVersion
No runs -> Invoke Agent
No API keys -> Create API Key
No events -> Check Worker / EventSink
No replay -> Select a failed Run
```

### 48.10 前后端契约

```text
FastAPI OpenAPI
  ↓
openapi-typescript / orval
  ↓
生成 TypeScript SDK
  ↓
Vue 调用 SDK
```

前端数据规则：

```text
1. 所有 API 类型从 OpenAPI 生成。
2. 列表页使用 cursor pagination。
3. 时间统一使用 ISO 8601，前端按用户时区展示。
4. 金额和 token 使用后端返回的标准单位，不在前端自行推断。
5. 错误展示基于稳定 error code，不依赖 error message。
6. SSE stream client 支持 Last-Event-ID 和 reconnect。
7. 前端不可缓存 Secret 明文。
8. 前端展示权限由后端返回 capability / permission summary 决定。
```

### 48.11 MVP 前端验收标准

```text
1. Dashboard 能展示 Run、Task、Worker、成本和错误趋势。
2. Agents 页面能查看 AgentVersion、manifest 和 capabilities。
3. Deployments 页面能展示 desired_status / runtime_status，并发起 pause / resume / restart。
4. Runs 页面能过滤、搜索并进入 Run 详情。
5. Run 详情能展示 Event Timeline、input/output、attempts、error 和 cost。
6. Tasks 页面能查看 lease、heartbeat、retry 和 dead letter。
7. API Keys 页面能创建、禁用和查看 scopes。
8. Compatibility 页面能展示 LangGraph assistants / threads / runs 映射关系。
9. 前端使用生成 SDK 调用 API。
10. 所有高风险操作有确认弹窗和 AuditLog 关联提示。
```

---

## 49. 评估设计

### 49.1 评估定位

评估不是 MVP 的主流程，但可评估性必须从第一天设计进去。

DimooRun 的评估定位是：

```text
Runtime 内置评估能力 / Agent Quality Gate
```

### 49.2 第一阶段必须记录的数据

* input
* output
* trace
* event
* tool calls
* model usage
* latency
* error
* cost
* 可选 retrieved context
* 可选 citations

### 49.3 评估类型

Runtime 可靠性评估：

* success_rate
* timeout_rate
* retry_count
* tool_error_rate
* avg_latency
* p95_latency
* avg_token_cost
* interruption_rate
* schema validation
* cost threshold
* tool call count threshold

业务质量评估：

* answer correctness
* instruction following
* tool selection accuracy
* citation correctness
* faithfulness
* relevance
* safety

回归评估：

```text
Agent v1.0.3 vs Agent v1.0.4
```

线上抽样和人工反馈闭环：

```text
线上 Run 抽样
用户 thumbs up/down
人工标注
失败案例沉淀为 Dataset
Dataset 驱动回归评估
评估结果影响发布门禁
```

### 49.4 Evaluator 接口

```python
from typing import Any, Protocol


class Evaluator(Protocol):
    name: str

    async def evaluate(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        trace: dict[str, Any],
        expected: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...
```

---

## 50. 插件化设计

```text
AgentAdapter:
  LangGraph / LangChain Agent / DeepAgents

TaskBackend:
  Redis / RabbitMQ / Kafka / Temporal

CheckpointBackend:
  Postgres / Redis / S3 / Custom

EventSink:
  Postgres / Redis Stream / Kafka / OpenTelemetry / Langfuse / Phoenix

AuthProvider:
  Local / OAuth2 / OIDC / LDAP / SSO

IdentityProvider:
  User / ServiceAccount / OIDC Machine Identity / Custom

PolicyEngine:
  Database Rules / OPA / Cedar / Casbin / Custom

ArtifactStore:
  Local Filesystem / MinIO / S3-compatible Object Storage / Cloud Object Storage

SandboxBackend:
  In-process / venv / subprocess / container / remote worker pool

HumanTaskProvider:
  Built-in Console / Webhook / Enterprise Workflow / Ticket System

ModelGatewayProvider:
  New API / LiteLLM / OpenAI-compatible Gateway / Cloud Model Gateway / Custom

SecretProvider:
  Env / DB / Vault / Cloud Secret Manager / K8s Secret

Evaluator:
  Built-in / RAGAS / DeepEval / LLM Judge / Human Review

ToolProvider:
  Local Tool / HTTP Tool / MCP Tool / Enterprise Tool Gateway

CatalogProvider:
  Built-in Registry / Git-backed Catalog / Private Marketplace

PromptProvider:
  Built-in Versioned Prompt Store / Langfuse / Git-backed Prompt Assets

DatasetProvider:
  Built-in Dataset Store / Phoenix / Langfuse / External Dataset Registry

MemoryStoreProvider:
  Postgres / pgvector / Qdrant / Milvus / Weaviate / Custom

NotificationProvider:
  Email / Webhook / Slack / Teams / Feishu / DingTalk / PagerDuty / Custom

BackupProvider:
  Database Backup / Object Store Snapshot / Git-backed Export / Custom
```

Provider 生命周期：

```text
register
validate
enable
health_check
disable
upgrade
deprecate
remove
```

Provider 元数据：

```text
id
type
name
version
schema
capabilities
status
health_status
config_schema
secret_refs
created_at
updated_at
```

Provider 规则：

```text
1. Provider 注册时必须校验 schema 和 capabilities。
2. Provider 启用前必须通过 health_check。
3. Provider upgrade 必须执行兼容性检查。
4. disable 不删除历史 Run / Event / Artifact 引用。
5. deprecate 表示禁止新绑定，但保留旧对象可读。
6. remove 只能在没有活跃引用时执行。
7. Provider 调用必须经过 Policy Engine，Provider 不自行决定最终授权。
```

核心原则：

```text
核心领域模型不依赖具体基础设施。
Agent 框架只是 Adapter。
Redis 只是 queue backend。
Postgres 只是 repository 实现。
New API 只是 Model Gateway 实现。
S3 / MinIO 只是 ArtifactStore 实现。
OPA / Casbin 只是 PolicyEngine 实现。
Langfuse / Phoenix 可以作为 PromptProvider / DatasetProvider / TraceSink 实现。
Haystack pipeline component 只是 Run Graph 映射来源之一。
Notification / Backup Provider 是运维出口，不是核心 Runtime 账本。
```

---

## 51. Extension API

DimooRun 可以支持扩展，但不能把自定义后端路由变成绕过平台治理的安全漏洞。

扩展形态：

```text
Event Webhook Subscription
Custom API Routes
Plugin lifecycle hooks
Extension UI panels
External approval workflow
External ticket / incident integration
```

MVP 不实现 Custom Routes。

第一阶段推荐只实现更安全的事件订阅：

```text
Event Webhook Subscription
```

WebhookSubscription 字段：

```text
id
tenant_id
project_id nullable
name
event_types
target_url
secret_ref
status
retry_policy
created_at
updated_at
```

Custom Routes 风险：

```text
任意后端扩展
绕过 API 鉴权
绕过 Policy Engine
访问内部网络
访问 Secret
破坏多租户隔离
```

Custom Routes 进入 Phase 3 后才考虑，并必须满足：

```text
extension auth
extension permissions
extension sandbox
route namespace isolation
request audit
rate limit
Policy Engine enforcement
```

原则：

```text
1. 扩展必须显式声明能力。
2. 扩展不能默认访问平台内部对象。
3. 扩展调用必须产生 AuditLog。
4. 扩展失败不能影响核心 Runtime。
5. Webhook 比 Custom Route 更适合作为第一版扩展点。
```

---

## 52. 代码结构建议

仓库结构：

```text
dimoo-run/
├── apps/
│   ├── server/              # FastAPI Runtime API
│   ├── worker/              # Agent Worker
│   └── console/             # Vue Console
├── packages/
│   ├── sdk-python/          # Python SDK，可后置
│   └── sdk-js/              # JS/TS SDK，可后置
├── docs/
│   ├── DESIGN_SPEC.md
│   ├── DEV_SPEC.md
│   └── ROADMAP.md
├── examples/
│   ├── langgraph/
│   └── compatibility/
├── dimoorun.yaml
└── docker-compose.yml
```

后端结构：

```text
apps/server/dimoo_run/
├── core/
│   ├── models.py
│   ├── context.py
│   ├── runtime.py
│   ├── lifecycle.py
│   ├── state_machine.py
│   ├── events.py
│   └── interfaces.py
├── adapters/
│   ├── base/
│   │   ├── contract.py
│   │   ├── capabilities.py
│   │   └── events.py
│   ├── langgraph/
│   ├── langchain_agent/
│   ├── deepagents/
│   └── http_agent/
├── api/
│   ├── native/
│   └── compat/
│       ├── langgraph/
│       └── agent_protocol/
├── cli/
├── config/
├── scheduler/
├── replay/
├── persistence/
├── streaming/
├── observability/
├── notifications/
├── run_graph/
├── security/
├── identity/
├── policy/
├── artifacts/
├── backup/
├── gateway/
├── catalog/
├── prompts/
├── datasets/
├── sandbox/
├── hitl/
├── model_gateway/
├── memory/
├── migration/
├── extensions/
├── tools/
├── evals/
├── worker/
└── server.py
```

前端结构：

```text
apps/console/
├── src/
│   ├── api/
│   ├── components/
│   ├── layouts/
│   ├── pages/
│   │   ├── dashboard/
│   │   ├── agents/
│   │   ├── runs/
│   │   ├── tasks/
│   │   ├── replay/
│   │   ├── traces/
│   │   ├── datasets/
│   │   ├── experiments/
│   │   ├── human-tasks/
│   │   ├── policies/
│   │   ├── catalog/
│   │   ├── tools/
│   │   ├── secrets/
│   │   ├── alerts/
│   │   ├── backups/
│   │   └── settings/
│   ├── router/
│   ├── stores/
│   └── main.ts
├── package.json
└── vite.config.ts
```

---

## 53. MVP 范围

MVP 分为两条路径：

```text
Dev MVP:
  目标是让开发者本地快速跑通。
  默认 SQLite / in-process queue / in-process worker。
  对应 dimoorun dev。

Runtime MVP:
  目标是验证生产运行时最小闭环。
  默认 Postgres / Redis / server + worker / Docker Compose。
  对应 dimoorun up + worker。
```

### 53.1 Dev MVP 必须包含

```text
Adapter-first 核心抽象
Capability Model
Adapter Conformance Test Kit 基础框架
LangGraph Compatibility Mode 路由和模型映射
LangGraphAdapter
Agent Package 标准
manifest.yaml / dimoorun.yaml
Agent 注册
AgentVersion 管理
Runtime API
基础 PublishedSurface：Native API / Compatibility API
基础 SSE Streaming Runtime
异步 Task
in-process Worker 执行
SQLite / in-memory Run Store
Run / RunAttempt / Task / Event 记录
in-process Queue
基础 Checkpoint 接入
基础 lease / heartbeat / retry / dead letter
基础 Run Graph projection
CLI：init / dev / validate / worker / up / down / doctor
API Key 鉴权
基础 Tenant / Project / User
基础权限：admin / developer / viewer
基础 OpenAPI 生成和错误码注册
基础 Console：Dashboard / Agents / Runs / Tasks / Events / API Keys
```

### 53.2 Runtime MVP 必须包含

```text
FastAPI server
独立 Worker 进程
Postgres Run Store
Redis Queue
Redis Stream / Postgres Event
Docker Compose 启动
API Key 鉴权
Idempotency-Key
Task lease / heartbeat / retry / dead letter
LangGraphAdapter 执行
Compatibility API 核心 assistants / threads / runs
Compatibility API golden tests
基础 Console
```

### 53.3 MVP 暂缓

```text
LangChainAgentAdapter
DeepAgentsAdapter
复杂 Web Console
完整 Deployment 管理
灰度发布
回滚
动态菜单
复杂组织架构
复杂 ABAC
完整审批流
完整评估平台
完整 Scheduled / Batch / Replay Runtime
完整 Agent Gateway / IngressRoute
完整 ServiceAccount / Machine Identity
完整 Alerting / Incident
完整 Backup / Restore
K8s Operator
多集群部署
Service Mesh
复杂计费系统
```

### 53.4 MVP 最小闭环

```text
注册一个 LangGraph Agent
  ↓
创建 AgentVersion
  ↓
通过 API 创建异步任务
  ↓
创建 Run / Task
  ↓
Worker 选择 LangGraphAdapter
  ↓
Worker 执行 LangGraph Agent
  ↓
记录 RunAttempt / Event / Output
  ↓
Console 查看 Run / Task / Event
  ↓
API 返回结果
```

### 53.5 MVP 验收标准

```text
1. Dev MVP 可以通过 dimoorun dev 本地启动 server、worker 和基础 Console。
2. Runtime MVP 可以通过 Docker Compose 一键启动 server、worker、console、postgres、redis。
3. 可以通过 API 注册一个 Agent Package。
4. AgentVersion 能保存 framework、adapter、capabilities。
5. 可以通过 API 创建异步 Task。
6. Worker 可以通过 LangGraphAdapter 执行 LangGraph Agent。
7. 可以查询 Run、RunAttempt、Task、Event。
8. Console 可以查看 Agent 列表、Run 列表、Run 详情、Event Timeline。
9. 支持 API Key 鉴权。
10. 同一个 Idempotency-Key 重复请求不会创建多个 Run。
11. Worker 执行失败后 Task 状态可见。
12. 基础 checkpoint/thread_id 能和 LangGraph 正常配合。
13. 对不支持的 capability 能返回明确错误。
14. dimoorun validate 可以校验 manifest.yaml 和 dimoorun.yaml。
15. Compatibility API 可以完成核心 assistants / threads / runs 调用。
16. SSE stream event 支持 sequence 和 event_id。
17. LangGraphAdapter 至少通过 invoke / stream / capability negative tests。
18. OpenAPI 能生成基础 TypeScript SDK。
```

---

## 54. Roadmap

### Phase 1A：Local Runnable

目标：能跑起来。

功能：

```text
AgentAdapter Contract
Adapter Contract Versioning
Adapter Conformance Test Kit scaffold
LangGraph Compatibility Mode
Capability Model
Framework-neutral Event Model
Streaming Runtime
Runtime State Machines
Agent Lifecycle
LangGraphAdapter
Agent Package 标准
manifest.yaml / dimoorun.yaml
CLI MVP commands
Runtime API
异步 task
in-process Worker
SQLite / in-memory run store
in-process queue
基础 Event
基础 PublishedSurface
基础 API Contract Governance
基础 Policy Engine
基础 Artifact metadata
基础 Run Graph projection
基础 Console
```

验收：

```text
可以注册并运行一个 LangGraph Agent。
可以查看 Run / Task / Event。
dimoorun dev 一键启动。
```

### Phase 1B：Runtime MVP

目标：验证生产运行时最小闭环。

功能：

```text
FastAPI server
独立 Worker 进程
Postgres run store
Redis queue
Redis Stream / Postgres Event
Docker Compose
docker compose dependencies
API Key 鉴权
Idempotency-Key
Task lease / heartbeat / retry / dead letter
Compatibility API 核心 assistants / threads / runs
Compatibility API golden tests
基础 Console
```

验收：

```text
Docker Compose 一键启动 server、worker、console、postgres、redis。
Worker 可以执行 LangGraph Agent。
同一个 Idempotency-Key 不会创建多个 Run。
```

### Phase 2：LangChain Ecosystem Adapters + Production Runtime

目标：支持 LangChain 生态更多 Agent，提升稳定性。

功能：

```text
LangChainAgentAdapter
DeepAgentsAdapter
Callback event mapping
Tool call trace mapping
Checkpoint 持久化
CheckpointIndex 生命周期
LangGraph Studio / Agent Protocol 兼容细节
Migration Story：LangGraph / Aegra / LangGraph Platform
Semantic Store Provider
Component / Tool / MCP Catalog
PromptAsset / ConfigAsset versioning
ServiceAccount / Machine Identity
ScheduledRun / BatchRun / ReplayJob 基础模型
Debug / Replay Console
流式输出
Replay Buffer / reconnect
任务取消
失败重试
任务 lease
Worker heartbeat
Dead Letter Queue
fencing token
lease reaper
Redis pub/sub cancel
并发限制
超时控制
租户 / 项目隔离
Secret 管理
ExecutionProfile / container sandbox
HumanTask / approval policy
基础 RBAC
OpenTelemetry
Langfuse / Phoenix 集成
OpenAPI diff check
```

验收：

```text
LangChain Agent 和 DeepAgents 可以接入运行。
Worker 崩溃后任务可恢复或进入可见失败状态。
支持 stream event。
支持任务取消。
支持 checkpoint resume，如果对应 Adapter 支持。
支持基础权限控制。
支持从历史 Run 创建 Debug / Replay Run。
支持 ServiceAccount 调用基础 Runtime API。
```

### Phase 3：Enterprise Ops

目标：企业可运维。

功能：

```text
完整 Web Console
Deployment 管理
Agent 版本管理
灰度发布
回滚
运行审计
成本统计
告警
Notification / Alerting
Tool Gateway
New API / Model Gateway 集成
统一 Policy Engine
Artifact Store
Extension API：Event Webhook Subscription
Dataset / Experiment / Feedback loop
Published MCP server endpoint
Agent Gateway / IngressRoute
Backup / Restore / DR
Secret Provider 扩展
Trace 脱敏和保留策略
```

验收：

```text
可以通过 Console 管理 Agent 版本和部署。
可以查看成本、错误趋势、审计日志。
高风险 Tool 可配置审批策略。
可以配置告警通知和受治理的发布入口。
可以查看备份状态并执行恢复 dry-run。
```

### Phase 4：Cloud Native

目标：云原生部署和大规模运行。

功能：

```text
K8s 部署
Helm Chart
Worker autoscaling
多环境
多集群
Temporal backend
Kafka event bus
S3 / MinIO artifact store
Custom Routes / Extension sandbox
multi-region / run sharding
```

验收：

```text
可以部署到 Kubernetes。
Worker 可以水平扩容。
队列积压时可以扩容 Worker。
LangChain 生态 Adapter 可以在云原生环境稳定运行。
```

### Phase 5：Quality Gate

目标：上线质量门禁。

功能：

```text
Eval Dataset
Eval Run
版本对比
自动评估
人工评分
LLM Judge
RAG 评估
发布门禁
线上抽样评估
反馈沉淀 Dataset
```

验收：

```text
Agent 新版本发布前可以跑回归集。
评估不通过时阻止发布到 prod。
线上失败案例可以沉淀为 Dataset。
```

---

## 55. 可参考开源项目

| 项目                      | 地址                                                                                               | 参考重点                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| Aegra                   | [https://github.com/aegra/aegra](https://github.com/aegra/aegra)                                 | 开源 LangGraph Platform / LangSmith Deployments 替代品    |
| Dify                    | [https://github.com/langgenius/dify](https://github.com/langgenius/dify)                         | 应用管理、工作流、知识库、权限、部署、控制台                               |
| Langflow                | [https://github.com/langflow-ai/langflow](https://github.com/langflow-ai/langflow)               | Workflow 发布、API 化、组件体系、MCP server                    |
| Flowise                 | [https://github.com/FlowiseAI/Flowise](https://github.com/FlowiseAI/Flowise)                     | 节点组件、工具集成、运行日志、部署方式                                  |
| Letta                   | [https://github.com/letta-ai/letta](https://github.com/letta-ai/letta)                           | Stateful Agent Server、Memory、状态管理、API 设计             |
| Langfuse                | [https://github.com/langfuse/langfuse](https://github.com/langfuse/langfuse)                     | Trace、Session、Cost、Eval、Prompt 管理                    |
| OpenLLMetry / Traceloop | [https://github.com/traceloop/openllmetry](https://github.com/traceloop/openllmetry)             | LLM 调用链路追踪                                           |
| Phoenix                 | [https://github.com/Arize-ai/phoenix](https://github.com/Arize-ai/phoenix)                       | Trace、Eval、Dataset、实验分析                              |
| New API                 | [https://github.com/Calcium-Ion/new-api](https://github.com/Calcium-Ion/new-api)                 | 模型渠道、额度、倍率、OpenAI-compatible API、模型资源管理             |
| Haystack                | [https://github.com/deepset-ai/haystack](https://github.com/deepset-ai/haystack)                 | Pipeline、Component、Retriever / Ranker / Generator 抽象 |
| SuperAGI                | [https://github.com/TransformerOptimus/SuperAGI](https://github.com/TransformerOptimus/SuperAGI) | 早期 Agent 平台、Agent 管理、工具和任务运行模型                       |

---

## 56. 架构学习目标

DimooRun 可以作为企业架构训练场。

通过本项目可以系统学习：

* 分层架构
* 六边形架构
* Adapter-first 架构
* LangGraph compatibility 设计
* 控制平面 / 数据平面
* 领域建模
* Agent 生命周期治理
* Deployment Runtime Control
* AgentInstance 生命周期
* Adapter 协议版本化
* Adapter conformance 测试
* 开发者体验和 CLI 设计
* 配置文件规范设计
* API 设计
* API 契约治理
* 任务队列
* Scheduled / Batch / Replay Runtime
* Worker Pool
* Streaming Runtime
* 状态机建模
* Checkpoint 边界设计
* Semantic Store / Memory 边界
* 事件驱动架构
* Event / Trace / Audit 三账本
* 插件化架构
* 沙箱和执行隔离
* 多租户
* RBAC / ABAC
* Policy Engine
* Human-in-the-loop 治理
* Secret 管理
* Artifact Store
* Model Gateway 集成
* 可观测性
* 评估和质量门禁
* Docker / K8s 部署
* 高并发和高可用设计
* Migration Story
* Extension API 安全边界
* Agent Gateway / Ingress 发布入口
* ServiceAccount / Machine Identity
* Notification / Alerting
* Backup / Restore / DR

建议逐步沉淀专题文档：

```text
01-domain-model.md
02-runtime-api-design.md
03-agent-adapter-contract.md
04-task-queue-design.md
05-run-state-machine.md
06-permission-model.md
07-observability-design.md
08-evaluation-design.md
09-deployment-architecture.md
10-console-design.md
11-security-design.md
12-agent-lifecycle.md
13-policy-engine.md
14-checkpoint-boundary.md
15-artifact-store.md
16-hitl-governance.md
17-langgraph-compatibility.md
18-streaming-runtime.md
19-dev-prod-enterprise-modes.md
20-migration-story.md
21-extension-api.md
22-adapter-conformance-test-kit.md
23-api-contract-governance.md
24-scheduled-batch-replay-runtime.md
25-agent-gateway-ingress.md
26-service-account-identity.md
27-notification-alerting.md
28-backup-restore-dr.md
29-deployment-runtime-control.md
```

---

## 57. 总结

DimooRun 的核心价值不是再造 Agent 框架，而是为不同 Agent 框架生成的智能体提供企业级运行时。

最终定位：

```text
Agent 框架负责 Agent 怎么思考；
DimooRun 负责 Agent 如何稳定、安全、可观测、可治理地运行在企业环境中。
```

核心边界：

```text
业务黑盒，运行白盒。
```

架构原则：

```text
战略上：LangChain 生态优先的企业级 Agent Runtime
架构上：Adapter-first
兼容上：LangGraph Compatibility Mode 降低迁移成本
MVP 上：LangGraphAdapter + 核心 Compatibility API
后续：补完整 LangChain Agent / DeepAgents，先不扩展更多 Agent Adapter
```

MVP 聚焦：

```text
AgentAdapter Contract
Adapter Contract Versioning
LangGraph Compatibility Mode
Capability Model
Streaming Runtime
Runtime State Machines
LangGraphAdapter
Agent Package
manifest.yaml / dimoorun.yaml
CLI / DX
Agent Registry
Runtime API
Redis Queue
Agent Worker
Postgres Run Store
RunAttempt / Event / Trace
Policy Engine
Artifact Store
Execution Isolation
基础 lease / heartbeat / retry / dead letter
基础 Auth / RBAC
基础 Console
Docker Compose
```

长期演进方向：

```text
开源的企业级 Agent Runtime Platform。
```
