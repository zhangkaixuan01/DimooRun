# LangGraph Examples

这里放标准 LangGraph Agent 示例，同时演示这些 Agent 如何接入 DimooRun 企业级运行时。

## 示例定位

这些示例首先应该是 LangGraph 开发者熟悉的项目形态：

- 使用 `langgraph.json` 声明 LangGraph 原生入口。
- Agent 代码可以直接用 `langgraph dev`、`langgraph up` 或 LangGraph Platform 工作流运行。
- DimooRun 兼容信息通过额外的 `manifest.yaml` 提供，不要求重写 Agent。

## 当前示例

- `support-agent/`：一个确定性的客服支持 Agent，LangGraph 原生入口为 `./agent.py:build_graph`，DimooRun 入口为 `agent:build_graph`。
- `enterprise-support-agent/`：一个生产形态客服支持 Agent，使用 OpenAI-compatible 模型网关、真实 secret 声明、LangChain tools、token usage 和高风险 interrupt 审批。

## 兼容 DimooRun 的方式

现有 LangGraph 项目接入 DimooRun 时，推荐保留原有 LangGraph 项目结构，只补充 DimooRun 运行时元数据：

1. 保留 `agent.py`、包结构和 `langgraph.json`。
2. 新增 `manifest.yaml`，声明 `framework`、`adapter`、`entrypoint`、能力、依赖、密钥和安全策略。
3. 在 Console 注册 AgentVersion，填写包地址、框架、适配器和入口。
4. 基于 AgentVersion 创建 Deployment。
5. 通过 DimooRun 的 Task / Run 入口执行，由运行时注入 `thread_id`、`run_id`、`task_id` 等上下文。

`langgraph.json` 使用 LangGraph CLI 的文件路径形式：

```json
{
  "graphs": {
    "support_agent": "./agent.py:build_graph"
  }
}
```

`manifest.yaml` 使用 DimooRun 加载包后的 Python import 形式：

```yaml
runtime:
  framework: langgraph
  adapter: langgraph
  entrypoint: agent:build_graph
```

两者指向同一个 `build_graph` 函数，只是面向的平台入口格式不同。

## Secret、Tool 和模型网关

企业级示例不把 API key 写进代码或 manifest。Agent Package 只在
`required_secrets` 中声明需要的 secret 引用：

```yaml
required_secrets:
  - MODEL_GATEWAY_API_KEY
```

本地 LangGraph 开发时，secret 可以来自 `.env`。接入 DimooRun 后，secret
应由 Console / Secret Provider 管理，并在运行时注入。模型访问建议走 New
API 或其他 OpenAI-compatible Model Gateway，由平台统一做模型权限、限流、成本和审计。

工具也应该是 Agent 代码里的业务黑盒，但工具调用事实需要被运行时观测。示例中的
`enterprise-support-agent` 使用 LangChain tools，并把 tool input / output 映射到
`tool_events`，这样 Console 的 Event Timeline / Run Detail 可以展示工具调用证据。
高风险动作通过 LangGraph `interrupt()` 暂停，交给平台的人审 / 恢复流程处理。

## 能力覆盖要求

LangGraph 示例至少应覆盖：

- invoke
- stream
- thread_id
- checkpoint
- interrupt / resume
- tool events
- model events
- token usage
