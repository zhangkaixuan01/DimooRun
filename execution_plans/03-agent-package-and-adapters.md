# 03 Agent Package 与 Adapter 执行计划

> **给执行 Agent 的要求：** Adapter 是 DimooRun 的核心边界。实现时必须保证核心 Runtime 只依赖通用 `AgentAdapter` 协议，不直接依赖 LangGraph / LangChain / DeepAgents。

**目标：** 实现 Agent Package 规范、manifest 校验、RuntimeContext、Capability Model、Adapter Contract、Adapter Contract Versioning、Adapter Conformance Test Kit，以及 LangGraph / LangChain Agent / DeepAgents 三个早期 Adapter。

**架构说明：** 用户 Agent 业务逻辑是黑盒。Adapter 只负责把 DimooRun 的 RuntimeContext、输入、事件、stream、checkpoint、resume、interrupt、tool/model usage 映射到具体框架。

**设计覆盖：** `DESIGN_SPEC.md` 第 10、11、11.1、14、19、24、30 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [ ] 第 9.4 章：LangChain Ecosystem Version Policy。
- [ ] 第 10 章：Adapter-first Agent Contract。
- [ ] 第 11 章：Adapter Contract Versioning。
- [ ] 第 11.1 章：Adapter Conformance Test Kit。
- [ ] 第 14 章：Agent Package 规范。
- [ ] 第 19 章：RuntimeContext。
- [ ] 第 24 章：Agent Lifecycle。
- [ ] 第 30 章：Checkpoint Boundary。
- [ ] 第 53.1 章：Dev MVP 必须包含。

## 1. 实现边界

本计划负责：

- [ ] `AgentAdapter` 协议。
- [ ] `AgentResult` / `AgentEvent`。
- [ ] `CapabilityModel`。
- [ ] `RuntimeContext`。
- [ ] `manifest.yaml` Pydantic 模型。
- [ ] Package entrypoint loader。
- [ ] Adapter 版本字段和兼容检查。
- [ ] Conformance Test Kit。
- [ ] LangGraphAdapter。
- [ ] LangChainAgentAdapter。
- [ ] DeepAgentsAdapter。

本计划不负责：

- [ ] Task Queue。
- [ ] Worker lease。
- [ ] Console 页面。
- [ ] Policy Engine 实际判定。
- [ ] New API 调用。

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

- [ ] 从 LangChain 1.x / LangGraph 1.x 生态起步，不从 0.x 兼容历史起步。
- [ ] `langchain-core` 显式依赖。
- [ ] `langchain` / `langgraph` 使用 1.x LTS 语义。
- [ ] 默认不自动升级；升级必须先更新版本矩阵并通过 conformance tests。
- [ ] `deepagents` 当前未到 1.0，生产必须锁定到已测试版本。
- [ ] `langsmith` 用于 trace/eval/dataset 相关集成，必须记录版本。
- [ ] AgentVersion 保存实际 `framework_version`。
- [ ] Conformance report 保存测试时的 `framework_version`、`adapter_api_version`、测试时间和失败项。

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

- [ ] core server 可以不安装任何 adapter extra 并启动。
- [ ] Worker 执行 LangGraph Agent 前必须具备 `dimoorun[langgraph]`。
- [ ] AgentVersion 记录 Agent Package lockfile，而不是只记录平台 extra。
- [ ] Adapter Conformance Test Kit 在安装对应 extra 后运行。

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
deadline_at nullable
permissions
secrets
config
metadata
```

语义：

- [ ] RuntimeContext 是 DimooRun 注入给 Adapter 的运行上下文。
- [ ] RuntimeContext 不是用户 Agent 的业务 State。
- [ ] Adapter 可以把 RuntimeContext 映射到框架参数。
- [ ] LangGraph 映射到 `configurable`。
- [ ] LangChain Agent 映射到 callbacks / metadata。
- [ ] DeepAgents 映射到 runtime config、subagents、filesystem / middleware 上下文。

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

- [ ] API 调用不支持能力时返回 `capability_not_supported`。
- [ ] capability 声明不能只信 manifest，必须通过 conformance tests 验证。
- [ ] AgentVersion 保存 capabilities 快照。
- [ ] 不同 Adapter 允许支持不同 capability。

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
        run_id: str,
        payload: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult: ...

    async def cancel(self, run_id: str, context: RuntimeContext) -> None: ...
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

- [ ] 不允许 Agent Package 随意读取宿主环境变量。
- [ ] Secret 只能通过 SecretProvider 注入。
- [ ] 依赖必须可锁定。
- [ ] 生产环境至少支持容器隔离计划。
- [ ] package hash 绑定依赖安装、缓存、镜像构建。

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

- [ ] 优先通过包元数据读取实际安装版本。
- [ ] 读取失败时记录 `unknown`，但 production profile 不允许 unknown。
- [ ] 版本写入 AgentVersion、RunAttempt metadata、conformance report。

兼容状态：

```text
compatible
compatible_with_warning
migration_required
unsupported
```

规则：

- [ ] Worker 执行前检查 Adapter 兼容性。
- [ ] breaking change 提升 `adapter_api_version`。
- [ ] capability 语义变化提升 `capability_schema_version`。
- [ ] event payload breaking change 提升 `event_schema_version`。
- [ ] 不兼容时返回 `adapter_contract_incompatible`。

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

认证结果：

```text
certified
certified_with_limitations
experimental
failed
```

规则：

- [ ] 官方 Adapter 发布前必须通过 conformance test。
- [ ] 第三方 Adapter 可以 experimental，但不能默认进 production profile。
- [ ] Compatibility API Adapter 需要额外 golden tests。
- [ ] conformance report 记录 framework version、adapter_api_version、测试时间、失败项。

## 9. LangGraphAdapter 实现要求

入口：

```python
def build_graph(config: dict[str, Any]):
    ...
```

必须支持：

- [ ] `load()` import entrypoint 并调用 `build_graph(runtime_config)`。
- [ ] `invoke()` 调用 `ainvoke` 或兼容同步 invoke。
- [ ] `stream()` 映射 LangGraph stream chunk 为 `AgentEvent`。
- [ ] `resume()` 通过 LangGraph thread/checkpoint 语义恢复。
- [ ] `RuntimeContext.thread_id` 映射到 `configurable.thread_id`。
- [ ] `RuntimeContext.run_id` 映射到 `configurable.run_id` 或 metadata。
- [ ] checkpoint metadata 写给 Runtime 层索引。
- [ ] interrupt 映射成 `human_interrupt.required` 或框架特定事件。

测试：

- [ ] fake graph 收到正确 `configurable.thread_id`。
- [ ] invoke 返回 AgentResult。
- [ ] stream 产生 `agent.stream_chunk`。
- [ ] 不支持能力时返回明确错误。

## 10. LangChainAgentAdapter 实现要求

入口：

```python
def create_agent(config: dict[str, Any]):
    ...
```

必须支持：

- [ ] `load()` import entrypoint 并调用 `create_agent(runtime_config)`。
- [ ] `invoke()` 映射到 Runnable / AgentExecutor。
- [ ] callbacks 捕获 tool/model events。
- [ ] metadata 包含 run_id、tenant_id、project_id、agent_version_id。
- [ ] 如果 checkpoint/resume 不支持，返回 `capability_not_supported`。

测试：

- [ ] fake runnable 收到 metadata。
- [ ] tool callback 被映射成 AgentEvent。
- [ ] resume negative test 返回 capability 错误。

## 11. DeepAgentsAdapter 实现要求

入口：

```python
def create_deep_agent(config: dict[str, Any]):
    ...
```

必须支持：

- [ ] `filesystem` capability。
- [ ] `subagents` capability。
- [ ] middleware / tool / model events 映射。
- [ ] RuntimeContext 注入 Deep Agents 运行配置。
- [ ] filesystem 权限和 sandbox policy 对接。

测试：

- [ ] capability 声明包含 filesystem 和 subagents。
- [ ] fake deep agent 可 invoke。
- [ ] 未声明 filesystem 时访问 filesystem 返回 policy/capability 错误。

## 12. 验收清单

- [ ] `uv run pytest tests/adapters -q` 通过。
- [ ] LangGraphAdapter 通过 invoke / stream / capability negative tests。
- [ ] LangChainAgentAdapter 通过 invoke / callback mapping tests。
- [ ] DeepAgentsAdapter 通过 filesystem / subagents tests。
- [ ] Conformance report 可生成。
- [ ] AgentVersion 能保存 Adapter 版本字段。
- [ ] manifest 校验能识别 entrypoint、capabilities、dependencies、required_secrets。

## 13. 提交建议

```text
feat: add agent package and adapter contracts
```

## 14. 设计回查清单

- [ ] LangChain 生态依赖策略符合第 9.4 章。
- [ ] 依赖安装边界明确区分 core、adapter extras、Agent Package、Worker image。
- [ ] `AgentAdapter` 方法签名与第 10.1 章一致。
- [ ] Capability 字段完整覆盖第 10.2 章。
- [ ] Adapter 优先级与第 10.3 章一致，没有引入 HTTP / CrewAI / LlamaIndex / SemanticKernel Adapter。
- [ ] Adapter 版本字段覆盖第 11 章。
- [ ] Conformance tests 覆盖第 11.1 章列出的测试类型。
- [ ] manifest 字段覆盖第 14.2 章。
- [ ] RuntimeContext 字段覆盖第 19 章。
- [ ] Checkpoint 只做索引，不解释业务 State，符合第 30 章。
