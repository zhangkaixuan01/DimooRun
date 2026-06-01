# 03 Agent Package 与 Adapter 执行计划

> **给执行 Agent 的要求：** Adapter 是 DimooRun 的核心边界。实现时必须保证核心 Runtime 只依赖通用 `AgentAdapter` 协议，不直接依赖 LangGraph / LangChain / DeepAgents。

**目标：** 实现 Agent Package 规范、manifest 校验、RuntimeContext、Capability Model、Adapter Contract、Adapter Contract Versioning、Adapter Conformance Test Kit，以及 LangGraph / LangChain Agent / DeepAgents 三个早期 Adapter。

**架构说明：** 用户 Agent 业务逻辑是黑盒。Adapter 只负责把 DimooRun 的 RuntimeContext、输入、事件、stream、checkpoint、resume、interrupt、tool/model usage 映射到具体框架。

**设计覆盖：** `DESIGN_SPEC.md` 第 10、11、11.1、14、19、24、30 章。

**当前状态：** 已完成 contract-level 基础实现，等待后续 `04-runtime-task-worker-streaming.md` 接入真实 Worker / Task Queue / Event persistence。

**本阶段完成内容：**

- Agent Package `manifest.yaml` Pydantic 校验。
- Package entrypoint loader，支持在调用 entrypoint 构建 Agent 时保持 package path，并临时隔离 / 恢复 package 根目录下的同名 helper module。
- `RuntimeContext`、`AgentEvent`、`AgentResult`，其中 Adapter 事件带 `run_id`、`sequence`、`event_id`、`created_at` 基础字段，RuntimeContext metadata 默认过滤 `None` 并避免用户 metadata 覆盖平台字段。
- `AgentAdapter` Protocol。
- `CapabilityModel` 与 `capability_not_supported` 错误。
- Adapter 版本治理基础字段与兼容性判断。
- Adapter Conformance Test Kit scaffold，当前覆盖 invoke / stream 基础项，并对 checkpoint / resume / cancel / interrupt / idempotency / error mapping 标记 `unsupported` 或 `not_exercised`。
- `LangGraphAdapter`、`LangChainAgentAdapter`、`DeepAgentsAdapter` 的 duck-typed contract-level 实现。
- `AgentVersion` 模型和 migration 增加 adapter/version/compatibility 字段。
- `dimoorun[langgraph]`、`dimoorun[langchain]`、`dimoorun[deepagents]` optional extras。

**边界说明：**

- 本阶段不把 LangGraph / LangChain / DeepAgents 加入 core dependency，只通过 optional extras 声明固定测试基线。
- 当前 Adapter 测试使用 fake graph / fake runnable / fake deep agent，验证 DimooRun contract 映射，不启动真实 Worker。
- 当前不认证 checkpoint / resume 能力，避免 Worker 未接入前对外暴露半成品语义。
- 真实 Run / Task / Event 持久化、stream replay、checkpoint index 写入、resume 恢复由 `04` 和 `07` 阶段继续接入。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 9.4 章：LangChain Ecosystem Version Policy。
- [x] 第 10 章：Adapter-first Agent Contract。
- [x] 第 11 章：Adapter Contract Versioning。
- [x] 第 11.1 章：Adapter Conformance Test Kit。
- [x] 第 14 章：Agent Package 规范。
- [x] 第 19 章：RuntimeContext。
- [x] 第 24 章：Agent Lifecycle。
- [x] 第 30 章：Checkpoint Boundary。
- [x] 第 53.1 章：Dev MVP 必须包含。

## 1. 实现边界

本计划负责：

- [x] `AgentAdapter` 协议。
- [x] `AgentResult` / `AgentEvent`。
- [x] `CapabilityModel`。
- [x] `RuntimeContext`。
- [x] `manifest.yaml` Pydantic 模型。
- [x] Package entrypoint loader。
- [x] Adapter 版本字段和兼容检查。
- [x] Conformance Test Kit。
- [x] LangGraphAdapter。
- [x] LangChainAgentAdapter。
- [x] DeepAgentsAdapter。

本计划不负责：

- [x] Task Queue：不在本阶段，进入 `04-runtime-task-worker-streaming.md`。
- [x] Worker lease：不在本阶段，进入 `04-runtime-task-worker-streaming.md`。
- [x] Console 页面：不在本阶段，进入 `08-console-product-plan.md`。
- [x] Policy Engine 实际判定：不在本阶段，进入 `06-governance-security-and-model-gateway.md`。
- [x] New API 调用：不在本阶段，进入 `06-governance-security-and-model-gateway.md`。

## 1.1 LangChain 生态固定测试基线

本计划采用 `DESIGN_SPEC.md` 第 9.4 章定义的固定测试基线：

```text
langchain      1.3.1
langchain-core 1.4.0
langgraph      1.2.1
deepagents     0.6.3
langsmith      0.8.5
```

实现要求：

- [x] 从 LangChain 1.x / LangGraph 1.x 生态起步，不从 0.x 兼容历史起步。
- [x] `langchain-core` 显式依赖。
- [x] `langchain` / `langgraph` 使用 1.x LTS 语义。
- [x] 默认不自动升级；升级必须先更新版本矩阵并通过 conformance tests。
- [x] `deepagents` 当前未到 1.0，生产必须锁定到已测试版本。
- [x] `langsmith` 用于 trace/eval/dataset 相关集成，必须记录版本。
- [x] AgentVersion 保存实际 `framework_version`。
- [x] Conformance report 保存测试时的 `framework_version`、`adapter_api_version`、测试时间和失败项。

固定测试矩阵：

```text
langchain==1.3.1
langchain-core==1.4.0
langgraph==1.2.1
deepagents==0.6.3
langsmith==0.8.5
```

## 1.2 依赖安装边界

LangChain 生态包不能全部塞进 DimooRun core dependency，否则会让最小 server 变重，也会影响不同 Agent Package 的依赖隔离。

依赖分层：

```text
DimooRun core dependencies:
  FastAPI / Pydantic / SQLAlchemy / Redis / OpenAPI 等平台依赖。
  不直接强依赖 langgraph / langchain / deepagents。

Adapter extras:
  dimoorun[langgraph]
  dimoorun[langchain]
  dimoorun[deepagents]

Agent Package dependencies:
  用户 Agent 自己的 manifest / lockfile 声明。
  和平台 runtime 依赖分开记录。

Worker image:
  按 ExecutionProfile 安装需要的 adapter extras。
  生产环境可为不同 adapter 构建不同 worker image。
```

建议 extras：

```text
[project.optional-dependencies]
langgraph = [
  "langchain==1.3.1",
  "langchain-core==1.4.0",
  "langgraph==1.2.1",
  "langsmith==0.8.5",
]

langchain = [
  "langchain==1.3.1",
  "langchain-core==1.4.0",
  "langsmith==0.8.5",
]

deepagents = [
  "langchain==1.3.1",
  "langchain-core==1.4.0",
  "deepagents==0.6.3",
  "langsmith==0.8.5",
]
```

规则：

- [x] core server 可以不安装任何 adapter extra 并启动。
- [x] Worker 执行 LangGraph Agent 前必须具备 `dimoorun[langgraph]`。
- [x] AgentVersion 记录 Agent Package lockfile，而不是只记录平台 extra。
- [x] Adapter Conformance Test Kit 在安装对应 extra 后运行。

## 2. 必须实现的文件

```text
apps/server/dimoo_run/core/context.py
apps/server/dimoo_run/core/events.py
apps/server/dimoo_run/adapters/base/contract.py
apps/server/dimoo_run/adapters/base/capabilities.py
apps/server/dimoo_run/adapters/base/versioning.py
apps/server/dimoo_run/adapters/base/conformance.py
apps/server/dimoo_run/adapters/langgraph/adapter.py
apps/server/dimoo_run/adapters/langchain_agent/adapter.py
apps/server/dimoo_run/adapters/deepagents/adapter.py
apps/server/dimoo_run/packages/manifest.py
apps/server/dimoo_run/packages/loader.py
tests/adapters/test_contract.py
tests/adapters/test_manifest.py
tests/adapters/test_langgraph_adapter.py
tests/adapters/test_langchain_agent_adapter.py
tests/adapters/test_deepagents_adapter.py
tests/adapters/test_conformance.py
tests/adapters/test_loader.py
```

## 3. RuntimeContext 设计

字段必须包含：

```text
tenant_id
project_id
run_id
task_id nullable
agent_id
agent_version_id
deployment_id nullable
user_id nullable
service_account_id nullable
thread_id nullable
session_id nullable
request_id nullable
attempt_id nullable
trace_id nullable
correlation_id nullable
idempotency_key nullable
environment nullable
framework nullable
adapter nullable
agent_version nullable
deadline_at nullable
permissions
secrets
config
metadata
```

语义：

- [x] RuntimeContext 是 DimooRun 注入给 Adapter 的运行上下文。
- [x] RuntimeContext 不是用户 Agent 的业务 State。
- [x] Adapter 可以把 RuntimeContext 映射到框架参数。
- [x] `to_metadata()` 默认过滤 `None` 字段，必要时可通过 `include_none=True` 输出完整字段。
- [x] 用户自定义 metadata 放入 `metadata` 子字段，不允许覆盖 `tenant_id`、`run_id`、`trace_id` 等平台身份字段。
- [x] LangGraph 映射到 `configurable`。
- [x] LangChain Agent 映射到 callbacks / metadata。
- [x] DeepAgents 映射到 runtime config、subagents、filesystem / middleware 上下文。

## 4. Capability Model

能力字段：

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

规则：

- [x] API 调用不支持能力时返回 `capability_not_supported`。
- [x] capability 声明不能只信 manifest，必须通过 conformance tests 验证。
- [x] AgentVersion 保存 capabilities 快照。
- [x] 不同 Adapter 允许支持不同 capability。
- [x] 当前 capability 快照只代表已通过本阶段 contract scaffold 验证的能力；checkpoint / resume 等依赖 Worker 和持久化的能力，在 `04` 接入前不得认证为可用。

错误响应：

```json
{
  "error": "capability_not_supported",
  "capability": "resume",
  "framework": "langchain-agent-python"
}
```

## 5. AgentAdapter 协议

必须定义：

```python
class AgentAdapter(Protocol):
    framework: str

    async def load(
        self,
        package_uri: str,
        manifest: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> Any: ...

    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult: ...

    async def stream(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AsyncIterator[AgentEvent]: ...

    async def resume(
        self,
        agent: Any,
        run_id: int,
        payload: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult: ...

    async def cancel(self, run_id: int, context: RuntimeContext) -> None: ...
```

## 6. Agent Package Manifest

必须支持：

```yaml
name: support-agent
version: 0.1.0
schema_version: "1.0"

runtime:
  framework: langgraph
  adapter: langgraph
  entrypoint: agent:build_graph
  python: ">=3.11"

capabilities:
  invoke: true
  stream: true
  checkpoint: true
  resume: true
  interrupt: true
  tool_events: true
  token_usage: true

dependencies:
  - langgraph
  - langchain

required_secrets:
  - OPENAI_API_KEY

security:
  network_policy: restricted
  allow_file_system_write: false
```

Package 安全边界：

- [x] 不允许 Agent Package 随意读取宿主环境变量。
- [x] Secret 只能通过 SecretProvider 注入。
- [x] 依赖必须可锁定。
- [x] 生产环境至少支持容器隔离计划。
- [x] package hash 绑定依赖安装、缓存、镜像构建。
- [x] `schema_version` 当前只接受 `"1.0"`，未来 schema migration 必须显式处理。
- [x] `framework` 和 `adapter` 必须匹配，避免 manifest 声明和 Adapter 路由不一致。
- [x] entrypoint 构建期间保持 package path，支持 `agent.py` 内部导入 package helper。
- [x] entrypoint loader 临时隔离 package 根目录下的同名 helper module，并在构建后恢复宿主模块缓存。

## 7. Adapter 版本治理

AgentVersion 必须记录：

```text
adapter_api_version
framework_version
manifest_schema_version
capability_schema_version
event_schema_version
compatibility_status
compatibility_checked_at
```

framework_version 获取规则：

- [x] 优先通过包元数据读取实际安装版本。
- [x] 读取失败时记录 `unknown`，但 production profile 不允许 unknown。
- [x] 版本写入 AgentVersion、RunAttempt metadata、conformance report。

兼容状态：

```text
compatible
compatible_with_warning
migration_required
unsupported
```

规则：

- [x] Worker 执行前检查 Adapter 兼容性。
- [x] breaking change 提升 `adapter_api_version`。
- [x] capability 语义变化提升 `capability_schema_version`。
- [x] event payload breaking change 提升 `event_schema_version`。
- [x] 不兼容时返回 `adapter_contract_incompatible`。

## 8. Adapter Conformance Test Kit

必须覆盖：

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

本阶段实现的是 Conformance Test Kit scaffold：

- [x] `invoke` contract test。
- [x] `stream` contract test。
- [x] `cancel` 结果槽位；当前未接入 Worker cancel token / pubsub / task state，标记 `not_exercised`。
- [x] `resume` unsupported / failed result 记录。
- [x] `checkpoint` / `interrupt` / `idempotency` / `error_mapping` 预留结果项，当前标记 `not_exercised`。
- [x] 报告状态可区分 `certified`、`certified_with_limitations`、`failed`。
- [x] 完整 checkpoint / resume / interrupt / idempotency 行为认证已明确移交给 `04-runtime-task-worker-streaming.md`，需要接入 Worker、Task、Event、Checkpoint 索引后完成。

认证结果：

```text
certified
certified_with_limitations
experimental
failed
```

规则：

- [x] 官方 Adapter 发布前必须通过 conformance test。
- [x] 第三方 Adapter 可以 experimental，但不能默认进 production profile。
- [x] Compatibility API Adapter 需要额外 golden tests。
- [x] conformance report 记录 framework version、adapter_api_version、测试时间、失败项和未执行项。

## 9. LangGraphAdapter 实现要求

入口：

```python
def build_graph(config: dict[str, Any]):
    ...
```

必须支持：

- [x] `load()` import entrypoint 并调用 `build_graph(runtime_config)`。
- [x] `invoke()` 调用 `ainvoke` 或兼容同步 invoke。
- [x] `stream()` 映射 LangGraph stream chunk 为 `AgentEvent`。
- [x] 当前 contract scaffold 不认证 `resume()`；真实 LangGraph thread/checkpoint 恢复进入 `04`。
- [x] `RuntimeContext.thread_id` 映射到 `configurable.thread_id`。
- [x] `RuntimeContext.run_id` 映射到 `configurable.run_id` 或 metadata。
- [x] 当前 contract scaffold 不写 checkpoint metadata；Runtime 层索引等待 `04` 的 Task/Event/Checkpoint persistence。
- [x] interrupt 映射成 `human_interrupt.required` 或框架特定事件。

测试：

- [x] fake graph 收到正确 `configurable.thread_id`。
- [x] invoke 返回 AgentResult。
- [x] stream 产生 `agent.stream_chunk`。
- [x] 不支持能力时返回明确错误。
- [x] checkpoint / resume 在 Worker 持久化接入前不认证为可用能力。

## 10. LangChainAgentAdapter 实现要求

入口：

```python
def create_agent(config: dict[str, Any]):
    ...
```

必须支持：

- [x] `load()` import entrypoint 并调用 `create_agent(runtime_config)`。
- [x] `invoke()` 映射到 Runnable / AgentExecutor。
- [x] callbacks 捕获 tool/model events。
- [x] metadata 包含 run_id、tenant_id、project_id、agent_version_id。
- [x] 如果 checkpoint/resume 不支持，返回 `capability_not_supported`。

测试：

- [x] fake runnable 收到 metadata。
- [x] tool callback 被映射成 AgentEvent。
- [x] resume negative test 返回 capability 错误。

## 11. DeepAgentsAdapter 实现要求

入口：

```python
def create_deep_agent(config: dict[str, Any]):
    ...
```

必须支持：

- [x] `filesystem` capability。
- [x] `subagents` capability。
- [x] middleware / tool / model events 映射。
- [x] RuntimeContext 注入 Deep Agents 运行配置。
- [x] filesystem 权限和 sandbox policy 对接。

测试：

- [x] capability 声明包含 filesystem 和 subagents。
- [x] fake deep agent 可 invoke。
- [x] 未声明 filesystem 时访问 filesystem 返回 policy/capability 错误。
- [x] checkpoint / resume 在 Worker 持久化接入前不认证为可用能力。

## 12. 验收清单

- [x] `uv run pytest tests/adapters -q` 通过。
- [x] LangGraphAdapter 通过 invoke / stream / capability negative tests。
- [x] LangChainAgentAdapter 通过 invoke / callback mapping tests。
- [x] DeepAgentsAdapter 通过 filesystem / subagents tests。
- [x] Conformance report 可生成，并能表达 `certified_with_limitations`。
- [x] AgentVersion 能保存 Adapter 版本字段。
- [x] manifest 校验能识别 entrypoint、capabilities、dependencies、required_secrets，并拒绝 framework / adapter 不一致和 unsupported schema version。

## 13. 提交建议

```text
feat(adapters): add agent package and adapter contracts
```

## 14. 设计回查清单

- [x] LangChain 生态依赖策略符合第 9.4 章。
- [x] 依赖安装边界明确区分 core、adapter extras、Agent Package、Worker image。
- [x] `AgentAdapter` 方法签名与第 10.1 章一致。
- [x] Capability 字段完整覆盖第 10.2 章。
- [x] Adapter 优先级与第 10.3 章一致，没有引入 HTTP / CrewAI / LlamaIndex / SemanticKernel Adapter。
- [x] Adapter 版本字段覆盖第 11 章。
- [x] Conformance Test Kit scaffold 覆盖第 11.1 章列出的测试结果槽位；完整 checkpoint / resume / idempotency 行为认证进入 `04`。
- [x] manifest 字段覆盖第 14.2 章。
- [x] RuntimeContext 字段覆盖第 19 章。
- [x] Checkpoint 只做索引，不解释业务 State，符合第 30 章。

## 15. 后续进入 04 前的注意事项

- 当前 Adapter 只验证 contract-level 映射；真实 Worker 执行、Task lease、RunAttempt、Event persistence 在 `04` 接入。
- `ConformanceReport` 已能记录版本、测试结果、失败项和未执行项，后续需要扩展 checkpoint / resume / interrupt / idempotency 的真实集成测试。
- Agent Package 依赖已经通过 optional extras 和 manifest dependencies 分层；生产隔离、package hash、镜像构建进入 Worker / Enterprise 阶段继续落地。
