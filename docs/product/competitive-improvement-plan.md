# DimooRun 竞争定位与优化改进计划

更新时间：2026-07-02

## 结论

DimooRun 不应该把自己定位成又一个 agent framework、低代码 agent builder、LLM
observability 工具或 AI gateway。更清晰、更有防守空间的定位是：

```text
DimooRun is the runtime control plane for agent code you already have.
```

中文表述：

```text
DimooRun 是面向现有 agent 代码的运行时控制平面。
```

产品核心承诺应该是：

```text
Bring your existing agent. DimooRun makes it deployable, governable,
replayable, and auditable.
```

即：用户已经写好的 LangGraph、LangChain Agent、DeepAgents 或其他 agent 代码，不需要重写到
DimooRun 里；DimooRun 负责把它变成可发布、可部署、可治理、可回放、可审计、可排障的生产运行单元。

## 实施原则：不做 MVP 降级

本文档不是最小 MVP 规格，而是 DimooRun 的护城河版 beta 产品规格。

后续实现必须遵守：

- 不允许把目标降级为“先做一个最小 demo”或“先做一个可点击壳子”。
- 可以分阶段交付，但每个阶段都必须朝本文档定义的完整验收标准收敛。
- 如果某项能力太大，应拆成可验证的子任务，而不是删除 trusted package、adapter certification、runtime evidence、governance、replay、promotion/rollback、integration proof 等核心要求。
- 新增实现必须优先服务 `existing agent code -> trusted package -> deploy -> run -> evidence -> replay/approval -> rollback/audit` 这条护城河路径。
- 对外文档、README、Console、CLI、SDK 的体验必须围绕 runtime control plane，而不是泛化成 agent builder、observability dashboard、AI gateway 或通用 workflow engine。
- 每个功能完成时必须提供对应验收证据：测试、CLI/Console 路径、文档、截图或可复现 artifact。

推荐给实现代理或工程任务使用的约束语：

```text
严格按 docs/product/competitive-improvement-plan.md 实现，不做 MVP 降级。
每个功能必须满足文档里的验收标准。
如果某项太大，拆阶段实现，但不能改变最终验收目标。
```

目标分级：

| 层级 | 含义 |
|---|---|
| MVP | 只跑通 publish、deploy、run，不足以形成护城河 |
| Moat Beta | 跑通 trusted package、adapter certification、evidence demo、CLI 简化、核心集成 |
| Production-grade | 在 Moat Beta 基础上补齐 hosted proof、安全/发布/运维证据、稳定 CI、真实用户反馈 |

本文档的目标是推进到 `Moat Beta`，并为后续 `Production-grade` 留出明确证据要求。

## Moat Beta 范围边界

为了避免“做着做着变成另一个大平台”，Moat Beta 必须清楚区分必须完成、可以预留、明确不做。

### Moat Beta 必须完成

- Existing agent import：至少一条 LangGraph 或 LangChain Agent 示例能从现有代码发布，不要求用户重写业务逻辑。
- Trusted package evidence：AgentVersion 能展示 validation、digest、signature/SBOM 状态、sandbox profile、secret refs。
- Runtime evidence：Run detail 能贯通 agent version、deployment、events、attempts、artifacts、policy/audit、trace link。
- Operator action：失败 run 能从 Console/CLI 发起 triage、replay、approval 或 rollback。
- Adapter boundary：支持的框架能力必须通过 certification matrix 明确展示，不能笼统承诺“全部支持”。
- Integration proof：至少有 LiteLLM、Langfuse 或 OpenTelemetry 中两个最小可运行集成示例。
- First-run proof：fresh checkout 到 Console 看到 run evidence 的路径小于 10 分钟，并有可复现脚本或 e2e。
- Console proof：Dashboard、AgentVersion、Deployment、Run Detail 至少形成一条完整 operator workflow。
- Product workflow proof：quality/eval、scheduled/batch、cost/budget、incident/notification、published surface、catalog asset 至少形成本地可操作闭环，不能只作为分散页面存在。

### Moat Beta 可以预留

- Hosted SaaS、多租户计费、用量套餐、企业采购流程。
- 完整企业 SSO、SCIM、复杂组织架构同步。
- 全量云市场发布、托管 SLA、企业支持承诺。
- 完整 BI 报表、成本预测、跨组织趋势分析。
- 所有 agent 框架的一次性全面认证。

### Moat Beta 明确不做

- 不做低代码 agent builder。
- 不做 prompt IDE。
- 不做 LangGraph、LangChain、CrewAI、DeepAgents 的替代框架。
- 不做 Langfuse、LiteLLM、Temporal 的正面替代。
- 不为了缩短排期删除 trusted package、runtime evidence、replay、governance、adapter certification 这些护城河能力。

## 执行总览与阶段 DoD

后续实现应按阶段交付，但不能把阶段交付解释为 MVP 降级。每个阶段必须留下可复现证据。

| 阶段 | 目标 | 必须产物 | 硬性验收 | 不可降级项 |
|---|---|---|---|---|
| P0-A First-Run Path | 新用户 10 分钟内看到第一个 run evidence | productized CLI、quickstart、demo seed、Dashboard next actions、2-3 张截图 | fresh checkout 脚本或 e2e 能跑通 publish/deploy/run/open | 不能只做静态截图或可点击壳子 |
| P0-B Evidence Path | 打穿护城河 demo | failed run、triage、replay、approval、promotion/rollback、audit export | browser e2e 覆盖 golden operator demo 主路径 | 不能只展示 run 列表而没有 evidence chain |
| 4-8 周 Integration Proof | 证明与相邻生态互补 | LiteLLM、Langfuse、OTel、adapter certification、trust evidence page | 至少两个集成有最小可运行配置和 run detail 证据 | 不能把集成写成纯概念文档 |
| 8-12 周 Credible Beta | 补生产可信度 | hosted/browser proof、Compose proof、Helm smoke、release evidence、SDK metadata | readiness scorecard 中关键 partial 项有证据更新 | 不能把 local proof 宣称为 hosted production proof |

阶段完成必须同时满足：

- 文档：README、quickstart、reference 或 comparison 中对应入口已更新。
- API：OpenAPI schema、SDK 类型、错误码文档与实现一致。
- Console：关键路径有可点击工作流，不只是路由存在。
- CLI：关键路径能通过命令完成，并输出下一步动作或 deep link。
- 测试：至少包含单元/API/e2e 中与功能风险匹配的一类自动化验证。
- Evidence：截图、CI artifact、seed script、export file 或 replay record 至少保留一种可复现证据。

## 执行依赖顺序

为了避免先做 UI 壳或先堆低优先级集成，建议按以下依赖顺序实现：

| 目标能力 | 前置依赖 | 后续解锁 |
|---|---|---|
| `dimoorun publish` | package validation、agent create/find、AgentVersion ready state | quickstart、demo seed、package trust page |
| `dimoorun deploy` | deployment create、activate、按 name/env 查询 | first-run path、Dashboard next actions |
| `dimoorun run` | deployment resolve、task submit、run watch、deep link 输出 | run evidence、e2e、time-to-first-run |
| Golden demo seed | publish/deploy/run wrappers、sample agent、failure fixture、approval fixture | screenshots、browser e2e、README demo |
| Run triage UX | runtime events、attempts、artifacts、audit、trace id | replay UX、incident workflow、operator dashboard |
| Promotion/rollback UX | promotion preview API、quality gate、active run check、rollback target | golden operator demo、audit export |
| Package trust UI | validation token、digest、signature/SBOM status、sandbox profile | production trust claim、security docs |
| Adapter certification UI | conformance report schema、capability statuses、real framework smoke | README support boundary、package validation warning |
| LiteLLM/Langfuse/OTel proof | exporter/gateway config、correlation ids、failure evidence | integration docs、external ecosystem conversion |
| Quality feedback loop | run capture、dataset、experiment result、quality gate preview | safer promotion、comparison docs、operator demo extension |
| Scheduled/batch workflow | deployment resolve、schedule preview、batch item state、retry/dead-letter | recurring production use、queue/capacity planning |
| Cost/budget governance | model usage attribution、budget policy、approval/reject decision、notification sink | enterprise governance、finance/security evaluation |
| Incident/notification workflow | failed run triage、alert rule、webhook delivery evidence、ack state | on-call trust、postmortem evidence |
| Environment drift control | scope model、deployment config diff、promotion path、policy inheritance | staging/prod confidence、safe rollout |
| Published agent surface | deployment routing、auth/quota/redaction、request log、rollout controls | external endpoint adoption、API productization |
| Catalog asset lifecycle | prompt/config/template versions、diff、dependency graph、environment binding | reproducible agent behavior、asset governance |

如果某项前置依赖缺失，应先补最小可验证接口，而不是用 mock UI 假装闭环已经存在。

## 当前位置

仓库已经具备较完整的生产形状：

- 后端存在 API、runtime、worker、scheduler、governance、identity、observability、replay、artifact、audit、CLI、SDK 等模块。
- 前端 Console 覆盖 agents、deployments、runs、tasks、replay、governance、identity、observability、settings、ops、catalog 等大量页面。
- Docker、Compose、Helm、OpenAPI、CI、release workflow、operations runbook、trust/security 文档都已经存在。
- 项目文档已经保持谨慎口径：`Production-shaped foundation: yes. External production-grade platform: not yet.`

当前主要风险不是“有没有功能雏形”，而是：

- 核心价值叙事还不够尖锐，容易被误解为又一个平台大杂烩。
- 第一次使用路径偏工程验证，不够产品化。
- 运行治理证据链没有通过一个足够短、足够有冲击力的 demo 打穿。
- 与 Langfuse、LiteLLM、Temporal/Hatchet 这类相邻工具的关系需要明确为“集成/互补”，而不是正面替代。

## ICP And Personas

DimooRun 的第一批用户不应定义为“所有想用 agent 的人”。更准确的 ICP 是：

```text
已经有 agent 代码，并且开始遇到上线、治理、排障、审计和多环境运行问题的工程团队。
```

### Primary ICP

| 维度 | 描述 |
|---|---|
| 团队类型 | AI platform team、应用平台团队、企业内部 AI 工程团队 |
| 当前状态 | 已经用 LangGraph、LangChain、CrewAI、DeepAgents 或自研 agent 跑出业务 demo |
| 主要痛点 | 无法安全发布、无法治理模型/工具/secret、失败后不可解释、缺少回放/审计、运维依赖脚本 |
| 购买/采用动机 | 让已有 agent 从“能跑”变成“可上线、可治理、可排障、可审计” |
| 不适合人群 | 只想拖拽搭一个简单聊天机器人、只需要 prompt playground、只需要 LLM proxy 的用户 |

### Personas

| Persona | 关心问题 | DimooRun 必须证明 |
|---|---|---|
| AI 应用工程师 | 我能不能不重写 agent 直接接入？失败后怎么 debug？ | import/publish 简单，run detail 能定位失败 |
| 平台工程负责人 | 多个 agent 如何版本化、部署、回滚、扩容、排障？ | deployment、worker、promotion、rollback、runtime metrics 可操作 |
| 安全/治理负责人 | secret、模型、工具、审批、审计是否可控？ | policy、approval、audit、package trust、secret ref 留痕 |
| 运维/on-call | 半夜失败时我看哪里？下一步做什么？ | dashboard next actions、triage、incident、replay、rollback |
| 开源评估者 | 15 分钟内能否看到真实价值？项目是否可信？ | quickstart、demo seed、screenshots、readiness evidence |

验收标准：

- README、quickstart、Console first-run guide 都明确服务上述 ICP。
- 文档入口按 persona 分流，而不是只按模块分流。
- 每个 P0 功能都能对应至少一个 persona 的关键问题。

## 相邻项目地图

以下数据来自 2026-07-02 使用 GitHub CLI 查询到的公开仓库元数据。

### Agent 框架与低代码上下文

这些项目不是 DimooRun 最直接的 runtime/governance 竞品，但它们占据了用户心智入口。
DimooRun 需要从它们的成熟用户中转化“已经有 agent 代码、现在需要运行治理”的团队。

| 类别 | 项目 | Stars | 定位 | 对 DimooRun 的启示 |
|---|---:|---:|---|---|
| 低代码/应用平台 | `langgenius/dify` | 147,382 | Production-ready platform for agentic workflow development | 不要和 Dify 拼低代码搭建；要转化复杂代码和治理需求溢出的用户 |
| 低代码/可视化 builder | `FlowiseAI/Flowise` | 54,196 | Build AI Agents, Visually | 不要主打 visual builder；主打 existing agent code 的生产运行 |
| Agent framework | `langchain-ai/langgraph` | 36,312 | Build resilient agents | 不替代 LangGraph；把 LangGraph app 发布成可治理 deployment |
| Agent framework | `crewAIInc/crewAI` | 54,760 | Multi-agent orchestration framework | 不替代 CrewAI；接管上线后的运行、审批、回放和审计 |
| Agent framework | `microsoft/autogen` | 59,430 | A programming framework for agentic AI | 作为高认知度 framework 参照；DimooRun 应避免落入 framework 竞争 |

这组项目证明了一件事：用户已经接受“用框架或低代码工具构建 agent”。DimooRun 的切入点不是再教用户构建
agent，而是在用户进入下一阶段时提供运行控制：

```text
The agent already works. Now make it deployable, governable, replayable, and auditable.
```

### 运行、治理、监控相邻项目

| 类别 | 项目 | Stars | 定位 | 对 DimooRun 的压力 |
|---|---:|---:|---|---|
| LLM/Agent 观测 | `langfuse/langfuse` | 30,298 | evals、observability、prompt、datasets | 会吃掉“观测/评估平台”叙事 |
| LLM/Agent 观测 | `Arize-ai/phoenix` | 10,374 | AI observability & evaluation | 会吃掉 tracing/eval 叙事 |
| LLM 观测代理 | `Helicone/helicone` | 5,893 | 一行代码监控、评估、实验 | 会吃掉简单接入监控场景 |
| AI engineering | `openlit/openlit` | 2,569 | OTel-native observability、guardrails、evals | 会吃掉 OpenTelemetry-native 叙事 |
| Agent 监控 | `AgentOps-AI/agentops` | 5,675 | agent monitoring、cost、benchmarking | 更接近 agent 运行监控 |
| AI gateway | `BerriAI/litellm` | 52,395 | LLM proxy、cost、guardrails、routing | 会吃掉模型入口治理 |
| AI gateway | `Portkey-AI/gateway` | 12,286 | AI gateway + guardrails | 会吃掉 gateway/guardrails 叙事 |
| Guardrails | `guardrails-ai/guardrails` | 7,081 | LLM 输出约束/校验 | 会吃掉输出安全叙事 |
| Guardrails | `NVIDIA-NeMo/Guardrails` | 6,590 | programmable conversational guardrails | 会吃掉对话护栏叙事 |
| Eval/安全测试 | `promptfoo/promptfoo` | 22,844 | prompt/agent/RAG 测试、red teaming | 会吃掉测试/红队叙事 |
| 通用 durable runtime | `temporalio/temporal` | 21,378 | durable workflow execution | 会吃掉通用可靠执行叙事 |
| 通用 workflow/AI runtime | `hatchet-dev/hatchet` | 7,447 | background tasks、AI agents、durable workflows | 会吃掉 durable AI workflow 叙事 |
| 通用 workflow runtime | `inngest/inngest` | 5,552 | stateful step functions and AI workflows | 会吃掉 stateful workflow 叙事 |

更准确的判断：

```text
DimooRun 的真正竞品不是单个开源项目，而是：

Langfuse / AgentOps
+ LiteLLM / Portkey
+ Temporal / Hatchet
+ 自研 Console / 审计 / 部署系统
```

DimooRun 的机会是把这些分散能力收敛成一个 agent-native runtime control plane。

## 护城河定义

### 不应主打的方向

不要把 DimooRun 主要包装成：

- agent framework
- low-code builder
- prompt IDE
- LLM observability platform
- AI gateway
- generic workflow engine
- guardrails library

这些方向都有强势竞品，且用户心智已经较稳定。

### 应主打的方向

DimooRun 应该主打：

```text
Agent Runtime Operations
```

对应的产品边界：

- 用户负责业务逻辑和 agent 框架选择。
- DimooRun 负责 agent package、version、deployment、task、run、worker、event、artifact、approval、policy、audit、replay、rollback。
- DimooRun 不替代 LangGraph、CrewAI、LangChain、LiteLLM、Langfuse、Temporal，而是在 agent runtime 层把它们纳入可操作、可治理、可解释的流程。

### 可防守能力

最值得沉淀为护城河的是以下组合：

- Adapter-first：接入已有 agent，而不是要求用户重写。
- Agent-native deployment：Agent、AgentVersion、Deployment、Run、Task 是一等领域对象。
- Trusted package runtime：agent package 的来源、版本、依赖、验证 token、OCI digest、签名、SBOM、secret 引用和 sandbox profile 都可验证。
- Evidence-first runtime：每次运行都能追踪版本、部署、事件、artifact、审批、策略、审计。
- Replay and triage：失败后能回放、比较、定位、升级、回滚。
- Promotion and rollback safety：版本晋级、质量门禁、活动运行压力、回滚目标和审计原因是内建工作流。
- Governance at runtime：模型、工具、secret、人审、策略在 runtime 层执行和留痕。
- Adapter certification：不同 agent 框架的 invoke、stream、resume、checkpoint、interrupt、cancel、idempotency、error mapping 通过可见矩阵说明支持边界。
- Operator Console：给平台团队、安全团队、运维团队使用，而不是只给 SDK 开发者。
- Framework-neutral ops：同一套控制面管理 LangGraph、LangChain Agent、DeepAgents 等多种 agent 形态。

## 护城河功能补强

### Trusted Agent Package Runtime

这是 DimooRun 区别于 observability 工具和通用 workflow engine 的关键能力。用户不仅要能把 agent
发布进来，还要相信这个 agent package 是可追踪、可复现、可隔离、可治理的。

当前代码已有基础：

- package validation 会生成 validation token。
- production runtime 已经限制非 dev 模式只允许 `oci://` package URI。
- manifest 已经包含 runtime、entrypoint、capabilities、secret refs 等信息。
- sandbox、secret provider、model gateway、tool gateway、policy engine 已有模块基础。

需要产品化补齐：

- OCI digest pinning：AgentVersion 应记录 immutable digest，而不是只记录可变 tag。
- Package signing：支持签名校验，至少记录 signer、signature、verification status。
- SBOM and dependency evidence：发布 agent version 时保存依赖清单和风险摘要。
- Runtime sandbox profile：deployment 绑定 sandbox profile，展示网络、文件系统、env、secret、gateway 权限。
- Secret reference audit：禁止 raw secret 进入 manifest、run input、artifact；只允许 governed secret ref。
- Package provenance view：Console 的 AgentVersion 页面展示来源、验证 token、digest、签名、SBOM、sandbox、required secrets。

验收标准：

- 一个 agent version 能回答“代码从哪里来、是否被验证、依赖是什么、运行时允许访问什么”。
- production mode 下无法运行未验证、未 digest pin、或 sandbox profile 缺失的 package。
- run detail 能反向链接到 agent version 的 package trust evidence。

### Adapter Certification Matrix

Adapter-first 只有在支持边界清晰时才是护城河。否则用户会担心“接入了，但关键能力不一定能用”。

当前代码已有基础：

- adapters 目录已经区分 LangGraph、LangChain Agent、DeepAgents。
- conformance suite 已经覆盖 invoke、stream、resume 的基础检测。
- conformance report 已有 `certified`、`certified_with_limitations`、`experimental`、`failed` 等状态。

需要产品化补齐：

| Capability | 意义 | 应展示状态 |
|---|---|---|
| invoke | 基础调用 | certified / failed |
| stream | 流式事件 | certified / unsupported |
| checkpoint | 状态持久化 | certified / declared / unsupported |
| resume | 中断后恢复 | certified / unsupported |
| interrupt | human-in-the-loop 中断 | certified / not exercised / unsupported |
| cancel | 取消运行 | certified / not exercised / unsupported |
| idempotency | 重复请求安全 | certified / not exercised / failed |
| error mapping | 框架错误归一化 | certified / not exercised / failed |
| token usage | token/cost 归集 | certified / partial / unsupported |
| tool/model events | 工具和模型事件 | certified / partial / unsupported |

需要新增的产品面：

- `docs/reference/adapter-certification.md`
- Console compatibility page 展示每个 framework adapter 的认证矩阵。
- Package validation 结果中返回 adapter compatibility status。
- CI 中定期运行真实 framework smoke，不只依赖 fake adapter。

验收标准：

- 用户能在发布前知道自己的 framework 能否支持 replay、HITL、stream、checkpoint。
- README 不笼统说“支持 LangGraph/LangChain/DeepAgents”，而是链接到认证矩阵。
- 未认证能力不能在 Console 中被当作已可用能力展示。

### Integration Product Specs

DimooRun 不应该正面替代 Langfuse、LiteLLM、OpenTelemetry，而应该把它们变成 runtime control plane 的外部能力。

#### LiteLLM / Portkey as Model Gateway

产品目标：

```text
模型路由、provider fallback、模型 cost 和 guardrails 可以由 LiteLLM / Portkey 管；
DimooRun 负责把这些 gateway decision 纳入 deployment、run、policy、audit。
```

需要落地：

- Deployment config 可绑定 model gateway。
- Run event 记录 model gateway id、provider、model、decision、fallback、cost。
- Policy/audit 记录 gateway allow/deny/approval/fallback。
- Console model gateway 页面提供 test、validate、usage、fallback preview。
- 文档提供 `Integrate LiteLLM with DimooRun` 和 `Integrate Portkey with DimooRun`。

验收标准：

- 用户能用一个 LiteLLM base URL 跑通 example agent。
- Run detail 能看到 gateway decision 和 cost attribution。
- Gateway deny / fallback / approval 能产生 audit evidence。

#### Langfuse / Phoenix / AgentOps as Trace Targets

产品目标：

```text
继续让用户用已有 observability 工具看 trace；
DimooRun 负责把 trace 和 runtime evidence 对齐到同一个 run。
```

需要落地：

- Run detail 展示 external trace link。
- Event/exporter payload 带 `run_id`、`attempt_id`、`deployment_id`、`agent_version_id`、`trace_id`。
- 支持 Langfuse/Phoenix/AgentOps exporter 配置示例。
- 当 exporter 失败时，DimooRun 保留 delivery failure evidence。

验收标准：

- 从 DimooRun run detail 可以跳转到外部 trace。
- 从外部 trace metadata 可以回到 DimooRun run。
- exporter failure 不影响 run 执行，但会产生可见告警或 evidence。

#### OpenTelemetry Export

产品目标：

```text
把 DimooRun runtime events、worker metrics、audit evidence 接入现有企业监控栈。
```

需要落地：

- OTLP exporter 配置。
- Prometheus metrics 与 OTLP spans/logs 的字段映射文档。
- trace/request/correlation id 在 API、worker、run event 中贯通。

验收标准：

- 本地 Compose 能启动一个最小 OTLP collector 示例。
- docs 中有字段表：DimooRun field -> OTEL attribute。
- 运行失败、policy deny、approval required、replay created 都能导出。

### 失败与降级模式

集成能力必须明确失败语义。否则用户会担心 DimooRun 把外部工具接进来后，反而增加运行不确定性。

| 场景 | 默认行为 | 必须产生的 evidence | Console 必须展示 |
|---|---|---|---|
| Trace exporter 不可用 | 不阻断 run | exporter failure event、retry count、last error | run detail 中显示 trace delivery failed 和重试状态 |
| Model gateway 不可用 | 按 deployment policy 决定 fail closed 或 fallback | gateway decision、fallback target、policy reason | gateway 状态、fallback/deny 原因、影响范围 |
| Package verification 失败 | production mode 阻断 deployment 或 run | verification failure、package uri、digest/signature 状态 | AgentVersion trust panel 显示阻断原因和修复动作 |
| Secret ref 解析失败 | 阻断需要该 secret 的 run | secret ref id、provider、resolution error | Run detail 显示 secret ref，不暴露 raw secret |
| Policy engine 不可用 | 高风险 action fail closed，低风险 action 按配置降级 | policy unavailable event、action scope、decision mode | action preflight 显示 fail closed/fallback 规则 |
| Worker 断连 | run 标记 stale 或 retryable | heartbeat gap、worker id、attempt state | Dashboard 和 Run detail 给出重试、取消或转移建议 |
| Audit sink 写入失败 | 阻断危险操作，普通 run 保留本地 audit backlog | audit backlog record、flush status | Settings/Ops 页面显示 audit backlog health |

验收标准：

- 每个外部集成都有 failure fixture 或测试覆盖。
- Run detail 不只展示 happy path，也展示外部依赖失败后的下一步动作。
- 安全相关失败默认保守处理，不能为了“跑通 demo”静默忽略。

### Golden Operator Demo

当前 demo 应从“功能展示”升级为“护城河证明”。推荐主 demo：

```text
Publish -> Deploy -> Promote with Quality Gate -> Run -> Fail ->
Triage -> Replay -> Approval -> Rollback -> Audit Export
```

必须包含：

- Publish：发布 existing LangGraph example，不重写业务逻辑。
- Deploy：创建 local/staging deployment。
- Promote：候选版本通过 quality gate preview 后晋级。
- Run：提交任务并生成 run timeline。
- Fail：触发一个可解释失败或 policy deny。
- Triage：Console 展示 attempt、events、artifact、trace id、gateway decision。
- Replay：从失败 run 创建 replay job，并对比 source/candidate。
- Approval：触发 human approval 或高风险 action audit reason。
- Rollback：回滚到上一 agent version。
- Audit Export：导出或展示完整操作证据链。

验收标准：

- 一条 seed script 可以准备 demo 数据。
- 一条 browser e2e 覆盖主路径。
- 文档中有稳定截图或 CI artifact。
- demo 明确说明哪些步骤是本地 proof，哪些步骤仍不是 hosted production proof。

### CLI Productization Layer

当前 CLI 已有工程化命令：

- `dimoorun agent publish`
- `dimoorun deployment create`
- `dimoorun deployment task submit`
- `dimoorun run watch`
- `dimoorun run replay`

但第一天用户需要的是更短的产品命令。建议新增薄封装，不删除现有命令：

```bash
dimoorun publish ./my-agent
dimoorun deploy support-agent --env local
dimoorun run support-agent --input input.json
dimoorun open
```

这些命令应做的是组合现有 API：

- `publish`：validate package -> create/find agent -> create ready version。
- `deploy`：create deployment -> optionally activate。
- `run`：resolve deployment by name/env -> submit task -> optionally watch。
- `open`：打开 Console URL 或打印明确地址。

验收标准：

- quickstart 不再需要复制大段 Python。
- 老的显式命令仍保留给自动化和 CI。
- 新命令输出下一步动作和 Console deep link。

## 扩展产品功能闭环

这些功能不是 DimooRun 的一句话护城河，但它们决定平台是否像一个可长期使用的 runtime control plane，而不是只能演示单次运行的工具。它们应作为 P1 产品闭环纳入路线图。

### Quality Feedback Loop

目标：把 replay 和 promotion 从“能重新跑”升级为“能判断新版本是否值得上线”。

推荐路径：

```text
Run -> Capture Dataset -> Run Experiment / Eval -> Quality Gate -> Promotion Decision -> Audit
```

需要补齐：

- Run detail 支持把 input/output/error/event subset 捕获为 dataset item，并记录 redaction 策略。
- Dataset 页面展示来源 run、agent version、deployment、capture reason、敏感字段处理状态。
- Experiment 页面支持对候选 agent version 跑同一 dataset，并输出 pass/fail、score、cost、latency、diff。
- Quality gate preview 能把 experiment result、replay comparison、cost/budget、policy decision 合并成 promotion 建议。
- Promotion audit 记录“为什么允许/拒绝晋级”，而不是只记录操作发生。

验收标准：

- 用户能从失败或关键 run 创建 dataset，并用候选版本跑一次对比。
- Deployment promotion 页面能看到 quality gate 的证据来源。
- 质量证据能反向链接到 dataset、experiment、source run 和 candidate run。

### Scheduled And Batch Runtime Operations

目标：支持真实生产中的周期性 agent 任务和批量任务，而不是只支持人工提交一次 run。

推荐路径：

```text
Deployment -> Schedule / Batch -> Queue -> Partial Failure -> Retry / Dead Letter -> Summary Evidence
```

需要补齐：

- Schedule preview：展示 cron/interval、timezone、next fire times、missed run policy。
- Schedule controls：pause、resume、trigger now、run once、catch up、skip missed。
- Batch run：支持 dataset/input list、item-level status、partial failure、retry failed、cancel remaining。
- Queue/capacity 联动：展示 schedule/batch 对 worker capacity、queue backlog、quota 的影响。
- Evidence：每个 schedule fire 和 batch item 都能链接到 task/run/audit。

验收标准：

- Console 能创建或查看一个 schedule，并预览未来触发时间。
- Batch run 能展示每个 item 的 status、error、retry/dead-letter 状态。
- 取消、暂停、重试都产生 audit evidence。

### Cost Budget And Quota Governance

目标：把成本从观测指标升级为 runtime governance。企业用户需要在运行前、运行中和运行后都知道成本风险。

推荐路径：

```text
Model Usage -> Cost Attribution -> Budget Policy -> Reject / Approval / Notify -> Audit
```

需要补齐：

- Cost attribution：按 tenant/project/environment/deployment/agent version/run/model/tool 归因。
- Budget policy：支持 warn、require approval、reject 三类动作。
- Budget preview：提交 task、schedule、batch、promotion 前展示预计成本和策略命中。
- Quota enforcement：run/task 创建时根据 budget/quota 决定 allow、deny 或 approval required。
- Notification：预算触发时写 delivery attempt，并能通过 webhook/Slack/PagerDuty-compatible sink 扩展。

验收标准：

- 一个超预算 run 能被 reject 或进入 approval，并在 audit 中说明原因。
- Cost 页面能从总览 drill down 到具体 run、model call 或 gateway decision。
- 预算策略命中不会静默失败，通知失败也必须有 delivery evidence。

### Incident Alert And Webhook Workflow

目标：让 failed run 从“页面上的错误”升级为可处理、可通知、可复盘的 operator workflow。

推荐路径：

```text
Failed Run -> Incident -> Alert Rule -> Notification / Webhook -> Ack -> Resolution -> Postmortem Evidence
```

需要补齐：

- Alert rules：按 run failure、policy deny、budget hit、worker stale、exporter failure、queue pressure 触发。
- Incident triage：聚合相关 runs、deployment、agent version、worker、events、audit、external trace。
- Notification delivery：记录 channel、payload digest、delivery status、retry、last error。
- Ack/resolution：记录 operator、时间、原因、关联 rollback/replay/approval。
- Postmortem export：导出事件时间线、操作、证据链接和 redaction 状态。

验收标准：

- 一个 failed run 能升级为 incident，并触发至少一个本地 webhook delivery attempt。
- Incident 页面能回答“影响什么、谁处理了、采取了什么动作、证据在哪里”。
- 通知失败不能丢失，必须进入 visible delivery failure state。

### Environment Topology And Drift Control

目标：让平台团队清楚知道每个环境运行什么版本、配置是否一致、变更如何从 staging 到 prod。

推荐路径：

```text
Environment -> Deployment Config -> Drift Diff -> Promotion Path -> Policy / Approval -> Rollback
```

需要补齐：

- Environment map：展示 dev/staging/prod 或自定义环境中的 active deployments、versions、runtime health。
- Config diff：比较 agent version、package digest、sandbox、model gateway、tool gateway、secret refs、policy bindings。
- Drift detection：标记“desired config”和“actual runtime config”不一致的 deployment。
- Promotion path：定义允许从哪个环境晋级到哪个环境，以及需要哪些 gate/approval。
- Scope inheritance：tenant/project/environment 的 policy、budget、secret、gateway 配置继承关系可见。

验收标准：

- 用户能一眼看到 staging/prod 是否运行同一 agent version 和关键配置。
- promotion/rollback 前能看到跨环境 diff 和阻断原因。
- scope inheritance 不能只存在于请求 header，需要在 Console 中可解释。

### Published Agent Surface

目标：把 deployment 变成可受治理地对外调用的 agent endpoint，而不是只能通过内部 task API 触发。

推荐路径：

```text
Deployment -> Published Surface -> Auth / Quota / Redaction -> Request Log -> Rollout / Rollback
```

需要补齐：

- Published endpoint：为 deployment 暴露受治理 route，支持版本/环境/rollout 绑定。
- Auth and quota：支持 API key/service account/scope，按 surface 限速、限额和审计。
- Request log：记录 request id、surface id、deployment、run/task、redaction status、error mapping。
- Route test：Console 中可测试 route，并显示命中的 policy、quota、gateway、run evidence。
- Rollout controls：surface 层支持 canary、pause、rollback、disable，并保留 audit reason。

验收标准：

- 用户能通过 published endpoint 调用一个 agent，并在 Run detail 看到 surface/request log 来源。
- request log 不暴露 raw secret 或敏感 payload，redaction 状态可见。
- surface disable/rollback 是高风险操作，必须有 preflight 和 audit。

### Catalog And Runtime Asset Lifecycle

目标：治理 agent 运行依赖的非代码资产，例如 prompt、config、template、MCP endpoint、semantic store，而不是只治理 package。

推荐路径：

```text
Asset -> Version / Diff -> Dependency Graph -> Environment Binding -> Runtime Evidence
```

需要补齐：

- Asset types：prompt、config、template、MCP endpoint、semantic store、runtime component。
- Version and diff：展示 asset 版本差异、变更原因、作者、关联 agent/deployment。
- Dependency graph：AgentVersion/Deployment 显示依赖哪些 assets，以及是否有未发布或漂移版本。
- Environment binding：不同环境可绑定不同 asset version，但 promotion 前必须显示 diff。
- Runtime evidence：Run detail 能记录实际使用的 asset version，而不是只记录 agent package。

验收标准：

- 用户能看到一个 agent 运行时使用了哪些 prompt/config/MCP/semantic store 版本。
- asset 变更能触发影响分析，说明哪些 deployment 会受影响。
- asset drift 能出现在 deployment/environment diff 中。

## 前端与 Console 体验优化

护城河功能解决“为什么要用 DimooRun”，Console 体验解决“用户是否愿意继续用 DimooRun”。如果前端只是功能堆叠，
平台团队会相信能力存在，但业务用户、评估者和开源社区不一定愿意深入试用。

### Console 产品目标

Console 不应只是 API 的管理后台，而应成为 operator workbench：

```text
Publish -> Deploy -> Run -> Triage -> Replay / Approval -> Promote / Rollback -> Audit
```

前端体验必须服务这条路径：

- 新用户知道第一步该做什么。
- 运维人员知道当前最需要处理什么。
- 安全/治理人员能快速看到 policy、approval、audit evidence。
- 工程人员能从 run 反查 package、adapter、deployment、trace、artifact。

### 视觉方向

推荐方向：专业 B2B SaaS 控制台，强调清晰、可信、密度适中，而不是炫技。

设计原则：

- Typography-first：标题、分组、状态、说明文案要有清晰层级。
- Evidence-first cards：关键卡片不只展示数字，还要展示下一步动作。
- Flat and fast：少用重阴影和复杂动效，优先清晰边界、状态色、快速反馈。
- Strong status semantics：ready、running、failed、waiting approval、policy denied、replayed、rolled back 必须有稳定视觉语言。
- No decorative noise：避免 emoji 图标、过度渐变、无意义装饰和通用 AI dashboard 风格。
- Accessibility by default：键盘焦点、颜色对比、loading/empty/error/offline 状态必须完整。

建议设计系统：

| Token | 建议 |
|---|---|
| Primary | 深蓝/靛蓝系，用于控制面导航和主操作 |
| Success / CTA | 绿色系，仅用于成功、可继续、明确 CTA |
| Warning | 琥珀色，用于 approval、risk、pending |
| Danger | 红色，用于 failed、policy denied、destructive action |
| Neutral | slate/zinc 系，用于大量表格、详情、审计内容 |
| Typography | Plus Jakarta Sans 或同级别现代 SaaS 字体；保持中文 fallback |
| Motion | 150-250ms 状态过渡；支持 `prefers-reduced-motion` |

### 信息架构优化

当前 Console 页面覆盖面广，但需要更强的信息架构，避免“菜单很多但不知道怎么开始”。

建议主导航按 operator journey 分组：

- `Start`: Dashboard, Package Registration, Agents
- `Operate`: Deployments, Runs, Tasks, Events, Replay
- `Govern`: Policies, Human Tasks, Model Gateways, Tool Gateways, Secrets, Catalog
- `Observe`: Audit Logs, Artifacts, Costs, Budgets, Evaluations, Feedback
- `Runtime`: Workers, Agent Instances, Capacity, Schedules, Batches
- `Admin`: Identity, Settings, Providers, Recovery, Alerts, Webhooks

验收标准：

- 任意一级菜单都能回答“这个页面服务哪一步 operator journey”。
- Dashboard 首页能把用户带到 Publish、Deploy、Run、Triage、Approval、Audit 的下一步。
- 详情页之间可反向跳转：Run -> Deployment -> AgentVersion -> Package Trust Evidence -> Audit/Trace。

### 关键页面优化

#### Dashboard

目标：从 metric dashboard 升级为 operator command center。

必须展示：

- `Next best actions`: publish missing, deployment unhealthy, run failed, approval pending, policy denied。
- `Runtime health`: queue、worker readiness、latency、dead letters。
- `Risk queue`: approvals、danger actions、policy denies、failed replays。
- `Evidence freshness`: last successful smoke, last screenshot artifact, last release evidence。

验收标准：

- 首页不是只看指标，而是能直接进入待处理工作。
- 空状态指导用户发布第一个 agent，而不是显示空表格。

#### Package / AgentVersion

目标：体现 trusted package runtime。

必须展示：

- package URI、OCI digest、validation token、manifest、entrypoint。
- adapter certification status。
- required secrets、sandbox profile、model/tool gateway bindings。
- SBOM/signature/provenance 状态。

验收标准：

- 用户能在一个页面判断“这个 agent version 是否可信、是否可上线”。

#### Deployment Detail

目标：体现 runtime control。

必须展示：

- desired status vs runtime status。
- active runs、queued tasks、worker assignment。
- promotion preview、quality gate、rollback target。
- bound package trust evidence、gateway policy、sandbox profile。

验收标准：

- promotion/rollback 前有 impact preview。
- 高风险操作必须要求 audit reason。

#### Run Detail / Triage

目标：体现 evidence-first runtime。

必须展示：

- timeline、attempts、events、input/output、error summary。
- source package、agent version、deployment、worker、trace id。
- artifacts、audit records、policy decisions、gateway decisions。
- replay action、candidate comparison、approval state。

验收标准：

- 一个失败 run 能在页面内回答“为什么失败、影响什么、下一步是什么”。

#### Settings / Admin / Identity

目标：让企业用户相信平台可控。

必须展示：

- scope boundary：tenant/project/environment。
- bootstrap/admin safety warnings。
- provider validation、danger action preflight、audit reason。
- service account、API key、role/permission matrix。

验收标准：

- 管理员操作不会像普通 CRUD，而是有风险解释、预检、回滚或恢复指引。

### 前端质量门

每个关键 Console 页面都应满足：

- Loading、empty、error、offline 四态完整。
- 移动端 375px 不横向滚动，桌面 1440px 信息密度合理。
- 表格支持筛选、排序、空态、错误态、行级 CTA。
- 所有危险操作有确认、影响说明、audit reason。
- 所有状态色有文本/图标辅助，不只依赖颜色。
- Playwright 覆盖关键 operator journey。
- Axe 或等价可访问性检查覆盖核心页面。

量化门槛：

| 类别 | 门槛 |
|---|---|
| First meaningful screen | 本地 demo 数据下 Dashboard 首屏 2 秒内可交互 |
| Critical path clicks | 从 Dashboard 到 failed run replay 不超过 4 次主要点击 |
| Responsive | 375px、768px、1024px、1440px 无横向滚动和遮挡 |
| Accessibility | 核心页面 axe critical/serious violations 为 0 |
| Keyboard | 关键操作可 Tab 到达，danger dialog 可键盘确认/取消 |
| Motion | 动效 150-300ms，尊重 `prefers-reduced-motion` |
| Status clarity | 每个状态同时有文本、图标或说明，不只依赖颜色 |
| Error recovery | 每个错误态提供 retry、copy diagnostics 或 docs link 至少一个动作 |
| Visual consistency | tokens、spacing、status color、icon set、typography 在核心页面一致 |
| Screenshot evidence | P0/P1 页面变更必须更新或新增稳定截图 artifact |

视觉约束：

- Console 应像 operator workbench，而不是通用后台 CRUD。
- 首页和核心详情页应突出 workflow、next action、risk、evidence，不堆等权指标。
- 使用统一 SVG icon set，不使用 emoji 作为功能图标。
- 避免默认紫白 SaaS 模板感；颜色应服务运行状态、风险等级和证据层级。
- Hover 不应造成布局位移，focus ring 必须清晰可见。
- 字体、间距、卡片密度应围绕高信息密度运维场景优化，而不是 landing page 式留白。

### 前端实施优先级

| 优先级 | 项目 | 价值 | 验收 |
|---|---|---|---|
| P0 | Dashboard command center | 第一眼证明平台有用 | 首页给出 next actions |
| P0 | Run triage redesign | 证明 evidence-first runtime | failed run 能完成定位和 replay |
| P0 | Deployment promotion/rollback UX | 证明 runtime control | promotion preview 和 rollback 全链路可点 |
| P1 | Package trust evidence page | 证明 trusted runtime | AgentVersion 展示 trust evidence |
| P1 | Adapter certification UI | 降低接入疑虑 | Compatibility 页面展示 capability matrix |
| P1 | Design system hardening | 提升专业可信度 | tokens、status、typography、spacing 统一 |
| P2 | Public screenshot gallery | 提升外部转化 | 每个核心页面有可维护截图 evidence |

## 配套产品功能优化

这些能力不是护城河主功能，但会显著影响 adoption、留存和社区传播。如果缺失，用户即使认可 runtime control plane
定位，也可能因为“难上手、不好集成、不放心运维”而流失。

### Onboarding And Activation

目标：新用户从 fresh checkout 到第一个 run evidence 小于 10 分钟。

需要补齐：

- `dimoorun quickstart`：自动检查 Docker、uv、Node、端口、浏览器。
- `dimoorun demo seed`：创建 demo agent、deployment、run、failed run、approval、replay 数据。
- Console first-run guide：只引导 3 步，不展示全部功能。
- Copy-paste friendly examples：每个命令都有 expected output。

验收标准：

- 新用户不需要理解全部架构也能完成第一次成功。
- Quickstart 失败时能给出具体修复建议，而不是堆栈。

### Docs And Learning Path

目标：不同用户有不同入口。

建议文档路径：

- `Evaluator path`: 15 分钟看价值。
- `Developer path`: 接入已有 LangGraph/LangChain/DeepAgents。
- `Operator path`: 处理失败 run、approval、rollback。
- `Security path`: package trust、secret、policy、audit。
- `Platform path`: Helm、observability、release evidence。

验收标准：

- README 只保留最短路径和定位，不承载所有细节。
- 每条 path 都有完成标准和下一步链接。

### SDK And API Developer Experience

目标：工程团队能把 DimooRun 接入现有系统。

需要补齐：

- Python/TypeScript SDK API parity matrix。
- SDK examples：publish、deploy、submit task、watch、replay、audit query。
- Typed errors：error code、request id、retryability、remediation。
- OpenAPI generated client story：说明哪些 SDK 是手写、哪些可生成。

验收标准：

- SDK 用户无需读 FastAPI 源码就能完成核心路径。
- 每个 API error 都能指导下一步。

### Enterprise Readiness

目标：让平台团队、安全团队、采购/评估者放心继续投入。

需要补齐：

- Deployment hardening checklist。
- Backup/restore drill evidence。
- RBAC and scope model examples。
- Audit export format。
- Data retention and redaction policy。
- Upgrade/migration guide。

验收标准：

- 评估者能回答“如何备份、如何升级、如何审计、如何限制权限、如何删除数据”。

### Community And Ecosystem

目标：让开源项目更容易被理解、试用、贡献和传播。

需要补齐：

- Issue templates 针对 bug、adapter request、integration request、docs gap。
- Good first issue 列表，优先围绕 adapters、examples、docs、Console polish。
- Example gallery：LangGraph、LangChain Agent、DeepAgents、LiteLLM、Langfuse。
- Comparison docs 的维护策略。
- Public roadmap 对齐 `Moat Beta`，避免泛泛列功能。

验收标准：

- 外部贡献者知道从哪里开始。
- 用户能提交“我要接入某个框架/网关/观测工具”的标准化请求。

### Open Source Conversion Path

目标：让 GitHub 访问者在最短时间内理解“为什么不是又一个 agent 框架”，并愿意试用。

需要补齐：

- README 首屏截图：展示 Dashboard command center、Run triage、Package trust evidence。
- Example gallery：每个 example 都有适用场景、启动命令、预期 run evidence。
- Demo script/video：用同一条 golden operator demo 生成截图、短视频和文档。
- Comparison pages：每页都说明什么时候继续用对方，什么时候引入 DimooRun。
- Issue templates：adapter request、integration request、operator workflow gap、docs gap。
- Roadmap labels：`moat-beta`、`first-run`、`evidence-path`、`integration-proof`、`console-polish`。

验收标准：

- 新访问者 2 分钟内能判断 DimooRun 是否适合自己。
- GitHub README 到 quickstart 到 golden demo 的跳转路径不超过 3 次点击。
- 每个 good first issue 都能对应文档中的一个具体验收项。

### Operational Quality

目标：减少“看起来功能很多，但跑起来不稳”的风险。

需要补齐：

- API test runtime profiling and split。
- Smoke test matrix：unit、contract、browser、compose、helm、release。
- Flaky test quarantine policy。
- Performance budget：Console bundle、API latency、run queue latency。
- Local cleanup command：清理 test-results、playwright reports、compose diagnostics。

验收标准：

- 贡献者能在合理时间内跑完核心验证。
- CI artifact 能证明核心路径，不只证明单元测试。

### Packaging And Open Source Boundary

目标：避免功能做完后仍然不知道“什么属于开源核心，什么属于企业增强”。

建议边界：

| 层级 | 建议范围 |
|---|---|
| OSS core | package validation、agent/version/deployment、run/task、worker、events、replay、basic policy、audit log、CLI、SDK、Compose、basic Console |
| OSS integrations | LiteLLM、Langfuse、OpenTelemetry、local/standard exporters、example adapters |
| Enterprise-ready docs | hardening checklist、backup/restore、RBAC examples、audit export schema、retention guide |
| Potential enterprise add-ons | SSO/SAML、advanced RBAC、long-term audit retention、hosted trust center、multi-org administration、managed HA operations |

约束：

- 不要为了商业化假设削弱 OSS core 的完整性。
- 护城河主路径必须在 OSS/self-hosted 下可验证。
- 如果某能力未来可能 enterprise，文档必须说明 OSS 下的替代路径或边界。

验收标准：

- `docs/product/product-overview` 或独立 packaging 文档能解释 OSS core 与 enterprise-ready surfaces。
- JS SDK license/package metadata 与仓库 license 策略一致。
- README 不暗示当前项目已经提供商业 SLA。

### API Stability And Migration Policy

目标：让用户敢把 DimooRun 接入现有系统。

需要定义：

- OpenAPI versioning：`/v1` 的稳定承诺和 breaking change 规则。
- Manifest schema version：agent package manifest 的版本策略。
- Adapter API version：adapter certification matrix 应记录 adapter API version。
- SDK parity：Python 与 TypeScript SDK 哪些 API 已同步，哪些是 pending。
- Deprecation policy：字段、endpoint、CLI 命令废弃前的保留周期和替代路径。
- Migration guide：从旧 manifest、旧 deployment config、旧 SDK 调用迁移的步骤。

验收标准：

- 每次 release 能说明 API/manifest/SDK 是否兼容。
- OpenAPI diff 失败时不会被当作小问题，而是 release blocker。
- 文档中明确哪些 API 是 stable，哪些是 experimental。

### Compliance Readiness

目标：不是宣称已经合规，而是定义进入企业评估所需的证据。

需要补齐：

- Audit export schema：操作、actor、scope、resource、result、reason、request id、trace id。
- Tenant/project/environment isolation proof：测试和文档证明 scope 边界。
- PII and secret redaction：run input、artifact、event、screenshot 的脱敏策略。
- Data retention controls：events、artifacts、audit、logs 的保留和删除策略。
- Security evidence pack：threat model、startup guards、package trust、secret provider、SBOM/provenance。
- Incident evidence：incident timeline、linked run/task/event、resolution summary。

验收标准：

- 可以生成一份 `trust evidence bundle`，给安全/平台团队评估。
- 文档不声称 SOC2/GDPR 已完成，但说明通向这些评估的 evidence map。
- Demo 和 screenshot 默认使用 deterministic fixtures，不使用真实客户数据。

### Integration Extension Model

目标：新增集成不能靠一次性硬编码，应形成可扩展接口。

建议扩展点：

| Extension Point | 用途 | 示例 |
|---|---|---|
| Model gateway provider | 模型路由和策略 | LiteLLM、Portkey、OpenAI-compatible |
| Trace/export sink | 外部观测 | Langfuse、Phoenix、AgentOps、OTLP |
| Secret provider | secret 解析 | local、Kubernetes、Vault-compatible |
| Artifact store | artifact 存储 | local、S3、MinIO |
| Notification sink | 告警通知 | webhook、Slack-compatible、PagerDuty-compatible |
| Policy plugin | 企业策略 | cost policy、tool policy、approval policy |
| Adapter plugin | agent 框架接入 | LangGraph、LangChain Agent、DeepAgents、future adapters |

验收标准：

- 每个扩展点都有最小接口、配置 schema、测试 fixture、失败语义。
- Console 能展示 extension health，而不是只有后端配置。
- 新增一个集成时不需要修改核心 runtime state machine。

### 配套功能优先级

| 优先级 | 项目 | 价值 | 验收 |
|---|---|---|---|
| P0 | Quickstart / demo seed | 降低首次试用阻力 | 10 分钟看到 run evidence |
| P0 | Docs learning paths | 降低理解成本 | evaluator/developer/operator/security/platform 五条路径 |
| P1 | SDK/API DX | 提升工程接入 | SDK parity matrix 和 typed error guide |
| P1 | Enterprise readiness docs | 提升采购/平台信任 | backup/RBAC/audit/retention/upgrade 文档 |
| P1 | API stability policy | 提升长期接入信心 | stable/experimental/deprecated 边界清晰 |
| P1 | Compliance evidence map | 提升安全评估信任 | trust evidence bundle 可生成 |
| P1 | Extension model | 降低集成扩展成本 | gateway/exporter/secret/artifact/policy/adapter 接口清晰 |
| P1 | Operational quality split | 提升贡献体验 | 核心验证可快速运行 |
| P1 | Quality feedback loop | 提升版本晋级可信度 | dataset/experiment/quality gate 反向链接到 promotion |
| P1 | Scheduled and batch operations | 支持真实运行负载 | schedule preview、batch retry/dead-letter、audit 可见 |
| P1 | Cost budget and quota governance | 降低企业采用风险 | budget policy 能 reject/approval/notify 并留痕 |
| P1 | Incident alert and webhook workflow | 提升 on-call 可用性 | failed run 可升级 incident 并产生 delivery evidence |
| P1 | Environment drift control | 提升多环境上线信心 | staging/prod diff、scope inheritance、promotion path 可见 |
| P1 | Published agent surface | 提升对外调用能力 | deployment 可暴露受治理 endpoint 并关联 run evidence |
| P2 | Catalog asset lifecycle | 治理 prompt/config/MCP 等运行资产 | asset version/diff/dependency/runtime evidence 可见 |
| P2 | Community ecosystem | 提升传播和贡献 | examples、issue templates、roadmap、good first issues |

## 用户迁移动机

### 从 Langfuse / AgentOps 转化

用户现状：

- 已经能看到 trace、cost、eval、prompt。
- 但部署、版本、审批、回放、rollback、worker 状态仍然分散在自研系统里。

DimooRun 的转化理由：

```text
继续用 Langfuse / AgentOps 看 traces；用 DimooRun 管 agent 的发布、部署、运行治理和事故证据链。
```

优先动作：

- 提供 Langfuse export/integration 指南。
- 在 Run detail 中展示外部 trace link。
- 把 DimooRun 定位为 runtime control，不定位为 observability replacement。

### 从 LiteLLM / Portkey 转化

用户现状：

- 已经有模型代理、cost tracking、provider routing、guardrails。
- 但 agent package、deployment、worker、run replay 仍然缺控制面。

DimooRun 的转化理由：

```text
LiteLLM / Portkey 管模型入口；DimooRun 管 agent runtime。
```

优先动作：

- 内置 LiteLLM model gateway 配置示例。
- Console 里把 model gateway 作为 deployment/runtime policy 的一个绑定项。
- 运行事件中记录 model gateway policy decision。

### 从 Temporal / Hatchet / Inngest 转化

用户现状：

- 已经有 durable workflow 或 background task engine。
- 但 agent 领域模型、Console、审批、审计、replay、artifact 需要自研。

DimooRun 的转化理由：

```text
你可以用通用 workflow engine 自己搭，也可以直接使用 agent-native runtime control plane。
```

优先动作：

- 写一页 `DimooRun vs Temporal/Hatchet for agents`。
- 强调 AgentVersion、Deployment、Run、Replay、HITL、Policy Evidence 是内建语义。
- 避免声称比 Temporal 更强的通用可靠执行，而是强调更贴近 agent 运维场景。

### 从 LangGraph / CrewAI / LangChain 用户转化

用户现状：

- 已经写好 agent 代码。
- 上线时需要部署、任务入口、worker、审计、回放、审批、运维控制台。

DimooRun 的转化理由：

```text
不重写 agent。把现有 agent 发布为可治理的 runtime deployment。
```

优先动作：

- `dimoorun publish ./my-agent`
- `dimoorun deploy --agent support-agent --env staging`
- `dimoorun run --deployment support-agent-staging --input input.json`
- Console 自动出现 run events、artifacts、audit、replay。

### 从 Dify / Flowise 用户转化

用户现状：

- 低代码体验好。
- 但复杂业务代码、企业运行治理、审计、版本化部署可能受限。

DimooRun 的转化理由：

```text
当低代码平台放不下你的复杂 agent 代码时，把代码带到 DimooRun 运行控制面。
```

优先动作：

- 不直接攻击低代码平台。
- 明确适用边界：DimooRun 适合已有工程代码、复杂运行治理、平台团队、安全团队。

## 核心功能完善度判断

### 已有基础

从当前项目结构看，以下核心模块已经具备基础：

- Agent package validation
- Agent / AgentVersion / Deployment
- Task submission / Run inspection
- Worker execution
- Runtime events
- Replay
- Policy / approval
- Identity / scopes
- Model / tool / secret governance surfaces
- Artifact / audit / observability
- Console / CLI / Python SDK / TypeScript SDK
- Docker / Compose / Helm / OpenAPI
- Cost / budget / quota surfaces
- Scheduled / batch runtime surfaces
- Quality / datasets / experiments surfaces
- Incident / alert / webhook surfaces
- Published surfaces and request-log surfaces
- Catalog / asset lifecycle surfaces

### 主要缺口

这些缺口会影响护城河兑现：

- First-run activation path 太长，用户第一次体验需要复制较大 Python 片段。
- Demo 不是围绕 `Publish -> Deploy -> Run -> Triage -> Replay -> Audit` 的一条强路径组织。
- Console 页面很多，但需要更明显地区分“已完整闭环的 operator workflow”和“已有页面/局部功能”。
- 与 Langfuse、LiteLLM、Temporal/Hatchet 的互补关系还没有产品化文档和集成示例。
- Hosted/default-browser proof、public screenshot evidence、release/trust proof 仍不足。
- API 测试套件耗时较高，影响开发者信心和贡献者体验。
- Helm defaults、SDK package metadata、placeholder-level extension domain 等细节仍削弱生产可信度。
- Quality/eval 能力需要串成 `dataset -> experiment -> quality gate -> promotion`，否则 promotion 证据不够强。
- Scheduled/batch、cost/budget、incident/notification、published surface、catalog asset 已有产品面迹象，但主路径证据和文档入口仍需收敛。
- 多环境 drift、scope inheritance、published endpoint governance 需要变成可视化 operator workflow，而不是只靠 API 或配置约定。

## 易用性改造方案

### P0：把首次成功压到 10 分钟

目标：

```text
fresh checkout -> one example agent deployed -> one run visible in Console
```

建议命令：

```bash
dimoorun init
dimoorun up
dimoorun publish examples/langgraph/support-agent
dimoorun deploy support-agent --env local
dimoorun run support-agent --input examples/langgraph/support-agent/input.json
dimoorun open
```

说明：

- 这些是目标产品命令，不是当前 CLI 的完整现状。
- 当前工程化命令应保留；P0 是新增更短的 productized wrapper。

验收标准：

- README 的 quickstart 不需要大段内联 Python。
- 用户能在 10 分钟内看到 Console run detail。
- run detail 中能看到 version、deployment、input、output、events、artifact/audit link。

### P0：做一条护城河 demo

Demo 名称：

```text
Publish -> Promote -> Failed Run -> Replay -> Approval -> Rollback -> Audit
```

必须展示：

- 发布一个 agent version。
- 创建 deployment。
- 通过 promotion preview 展示 candidate readiness、quality gate、active runs、queued tasks、rollback target。
- 提交一个会失败或需要审批的 task。
- Console 展示 run timeline、attempt、event、artifact、policy decision。
- 触发 human approval 或 replay。
- 对比 replay 结果。
- 生成 audit evidence。
- 执行 rollback 或 deployment action。

验收标准：

- 一条脚本可以 seed demo 数据。
- 一条 e2e 测试覆盖主路径。
- 文档中有截图或稳定 artifact 链接。

### P1：把 Console 首页改成 operator journey

当前风险：

- 当前 dashboard 已有指标、recent failures、worker health、pending approvals。
- 下一步应从 metric dashboard 升级为 operator journey dashboard，而不是从零重做。

建议首页结构：

- `Publish`: 最近 agent versions 和 package readiness。
- `Deploy`: active deployments、drift、health。
- `Run`: queue、running、failed、waiting approval。
- `Triage`: failed runs、incidents、replay candidates。
- `Govern`: pending approvals、policy denies、secret/model/tool gateway events。
- `Evidence`: audit exports、artifacts、trace links。

验收标准：

- 用户打开 Console 后知道下一步该做什么。
- 首页每个卡片能跳到一个可执行工作流，而不是只展示指标。

### P1：补互补集成，而不是替代叙事

建议优先集成：

- LiteLLM as model gateway
- Langfuse as trace/eval target
- OpenTelemetry export

文档页面：

- `Integrate LiteLLM with DimooRun`
- `Send DimooRun run evidence to Langfuse`
- `DimooRun with OpenTelemetry`

验收标准：

- 每个集成有最小可运行配置。
- Run detail 能显示外部 trace/eval 链接。
- Policy/audit 事件里能看到外部 gateway decision 或 trace id。

### P1：发布 adapter certification matrix

建议页面：

- `docs/reference/adapter-certification.md`
- Console `Compatibility` 页面中的 certification tab

验收标准：

- 每个 adapter 都展示 invoke、stream、checkpoint、resume、interrupt、cancel、idempotency、error mapping 状态。
- Package validation 返回能力边界。
- 未认证能力不出现在默认成功路径中。

### P1：强化 trusted package runtime

建议能力：

- OCI digest pinning
- Package signing / verification status
- SBOM and dependency evidence
- Sandbox profile binding
- Secret ref policy and audit

验收标准：

- AgentVersion 页面能展示 package trust evidence。
- production mode 拒绝不满足 trust policy 的 package。
- Run detail 能链接到 package trust evidence。

### P1：做对比页

建议页面：

- `DimooRun vs Langfuse`
- `DimooRun vs LiteLLM`
- `DimooRun vs Temporal/Hatchet`
- `DimooRun vs Dify/Flowise`

核心写法：

- 不贬低对方。
- 明确用户什么时候应该继续用对方。
- 明确什么时候需要 DimooRun。
- 给迁移路径，不只给概念对比。

### P2：完善生产可信度

需要补齐：

- Hosted Compose smoke artifact
- KinD/Helm smoke artifact
- public screenshot gallery
- release evidence index
- SBOM/provenance/trust verification 链接
- Helm production defaults
- JS SDK license/package metadata
- API suite runtime profiling

验收标准：

- `docs/readiness/scorecard.md` 可以把更多 `partial` 项推进到 `complete`。
- 外部用户可以基于公开 artifact 复现核心路径。

## 产品路线图

### 0-2 周：P0-A First-Run Path

目标：

- 修正 quickstart 体验。
- 明确产品叙事。
- 让新用户在 10 分钟内看到第一个 run evidence。

任务：

- 简化 CLI：`publish`、`deploy`、`run`。
- 将 README 首屏改成 runtime control plane 叙事。
- Dashboard 增加 next actions。
- 增加 `dimoorun demo seed` 或等价 demo 数据准备脚本。
- 新增 evaluator/developer/operator/security/platform learning path 入口。
- 新增 2-3 张关键 Console 截图。

### 2-4 周：P0-B Evidence Path

目标：

- 完成一条能证明护城河的强 demo。
- 建立 run triage、promotion、rollback、audit 的第一版可信体验。

任务：

- 新增 `Failed Run -> Replay -> Audit` demo。
- 把 promotion preview、quality gate、rollback 纳入主 demo。
- Run detail 强化 evidence-first triage。
- Deployment detail 强化 promotion preview 和 rollback UX。
- AgentVersion 页面展示第一版 package trust evidence。
- Quality gate preview 反向链接 dataset、experiment、source run、candidate run。
- Incident triage 能从 failed run 升级并产生本地 notification/webhook delivery evidence。
- Browser e2e 覆盖 golden operator demo 主路径。
- 新增 `DimooRun vs Langfuse/LiteLLM/Temporal` 初版文档。

### 4-8 周：集成和证据

目标：

- 让相邻生态用户觉得 DimooRun 是补强，而不是替代。

任务：

- LiteLLM integration example。
- Langfuse trace link example。
- OpenTelemetry export example。
- Adapter certification matrix。
- Trusted package runtime evidence page。
- Package/AgentVersion trust evidence UI。
- SDK parity matrix 和 typed error guide。
- API stability and migration policy。
- Compliance evidence map。
- Extension model docs and fixtures。
- Scheduled run preview、pause/resume/trigger workflow。
- Batch run partial-failure、retry failed、dead-letter、cancel summary workflow。
- Cost budget policy 的 reject/approval/notify runtime enforcement proof。
- Environment topology、config diff、drift detection、promotion path proof。
- Published agent surface route test、request log、redaction、rollback proof。
- Hosted/default-browser e2e proof。
- Clean-machine Compose proof。
- Helm KinD smoke proof。

### 8-12 周：生产可信度

目标：

- 从 production-shaped foundation 推进到 credible beta。

任务：

- Helm production defaults。
- Release attestation evidence。
- SDK publication metadata。
- Extension domain hardening。
- Catalog asset lifecycle：prompt/config/template/MCP/semantic store version、diff、dependency、environment binding。
- Notification sink hardening：webhook、Slack-compatible、PagerDuty-compatible delivery/retry evidence。
- API test performance work。
- Operator workflow completeness audit。
- Enterprise readiness docs：backup、RBAC、audit export、retention、upgrade。
- Public screenshot gallery 和 example gallery。

## 实现任务模板

后续把本文档拆成 issue、PR 或交给 AI 实现时，应使用同一任务模板，避免只实现表面功能。

```markdown
## 背景

说明该任务服务哪条护城河路径、哪个 persona、哪个阶段 DoD。

## 目标

列出用户可感知结果，不只列技术改动。

## 非目标

明确本任务不做什么，避免 scope creep。

## 设计与接口影响

说明 API、DB、SDK、CLI、Console、docs 是否需要同步变化。

## 验收标准

列出可运行命令、Console 路径、测试、截图或 artifact。

## 失败模式

说明外部依赖失败、权限不足、数据缺失时的行为。

## 证据

记录测试输出、截图路径、demo seed、e2e artifact 或 audit export。
```

## 变更检查表

涉及核心产品面的 PR 必须检查以下项目：

| 变更类型 | 必查项 |
|---|---|
| API | OpenAPI 更新、错误码、request id、retryability、SDK 影响 |
| DB | migration、rollback path、seed/demo data、backfill 风险 |
| CLI | help text、expected output、exit code、deep link、非交互失败提示 |
| Console | loading/empty/error/offline、权限态、危险操作确认、截图 evidence |
| SDK | Python/TypeScript parity、typed error、example、版本兼容说明 |
| Runtime | event/audit/artifact、idempotency、retry、cancel、worker failure 行为 |
| Security | secret redaction、policy decision、audit reason、scope/RBAC |
| Docs | quickstart、reference、comparison、readiness 或 migration 是否需要更新 |
| Tests | unit/API/e2e/compose/helm 中至少选择与风险匹配的一类 |
| Evidence | CI artifact、screenshot、demo output、audit export 或 replay record |

如果某项检查不适用，PR 说明中必须写明原因，不能默认跳过。

## 北极星指标

建议跟踪以下指标：

- Time to first successful run：新用户从 checkout 到 Console 看到 run detail 的时间，目标小于 10 分钟。
- Existing agent import success rate：已有 LangGraph/LangChain/DeepAgents 示例一次导入成功率。
- Run evidence completeness：每个 run 是否具备 version、deployment、events、attempts、artifacts、audit、trace link。
- Replay success rate：失败 run 是否能通过 Console/CLI 发起 replay 并生成对比结果。
- Governance decision coverage：模型、工具、secret、human approval 是否都有 runtime 事件和 audit。
- Package trust completeness：每个 ready AgentVersion 是否具备 validation token、digest、signature/SBOM 状态、sandbox profile。
- Adapter certification coverage：每个 supported adapter 的核心 capability 是否有认证状态。
- Public proof freshness：公开 screenshot/e2e/release evidence 是否在最近一次 release 后更新。
- API suite feedback time：核心测试在本地和 CI 的完成时间。
- Activation conversion：fresh checkout 到第一个 run evidence 的成功率和耗时。
- Console task completion：用户从 failed run 到 replay/rollback/audit 的完成率。
- Docs path completion：五条 learning path 是否都有明确完成标准。
- Demo completion rate：评估者从 quickstart 到 golden operator demo 完成率。
- Time to second run：用户完成第一次 run 后，提交第二次真实/自定义 run 的时间。
- Returning evaluator rate：首次试用后再次打开 Console 或运行 CLI 的比例。
- Integration request volume：用户请求新增 gateway/exporter/adapter 的数量和类型。
- API compatibility incidents：release 后由 breaking change 引发的问题数量。
- Quality gate decision traceability：promotion decision 是否能追溯到 dataset、experiment、replay、policy、cost evidence。
- Scheduled/batch reliability：schedule fire、batch item retry、dead-letter、cancel summary 是否都有 run/audit 证据。
- Budget governance effectiveness：预算策略触发后 reject、approval、notify 是否符合预期且可审计。
- Incident response completion：failed run 到 incident ack、resolution、postmortem export 的完成率。
- Environment drift detection freshness：deployment config drift 是否能被及时发现和解释。
- Published surface reliability：endpoint request 到 run evidence、request log、redaction 状态的关联完整度。
- Asset dependency traceability：Run detail 是否能追踪 prompt/config/MCP/semantic store 等 asset version。

## Beta 用户反馈闭环

Moat Beta 不能只靠内部判断完成度，需要用真实用户问题验证护城河是否成立。

### 推荐验证对象

| 用户类型 | 验证问题 | 成功信号 |
|---|---|---|
| LangGraph/LangChain 工程师 | 能否不重写 agent 完成 publish/deploy/run | 用户能指出接入阻塞点而不是质疑定位 |
| 平台工程负责人 | DimooRun 是否减少自研 Console/审计/部署胶水 | 愿意用自己的 agent 跑一条 evidence demo |
| 运维/on-call | failed run 页面是否能指导下一步 | 能独立完成 replay、rollback 或导出 audit |
| 安全/治理负责人 | package trust、secret、approval、audit 是否足够评估 | 能提出具体 policy/RBAC 缺口 |
| 开源评估者 | 15 分钟内是否看到差异化 | 能复述 runtime control plane 定位 |

### 反馈进入路线图规则

- 如果反馈阻塞 `existing agent code -> trusted package -> deploy -> run -> evidence -> replay/approval -> rollback/audit`，优先级至少为 P0/P1。
- 如果反馈只增强通用 dashboard、报表、低代码搭建或 hosted SaaS 商业化，默认放入 P2 或 Moat Beta 之后。
- 每个 beta 反馈必须归类到 persona、workflow、missing evidence、bug、docs gap、integration request 中至少一类。
- 每轮 beta 后更新 quickstart、golden demo、comparison docs 或 readiness scorecard 中至少一个公开证据。

## 信息架构建议

README 首屏建议改为：

1. One-liner：runtime control plane for existing agent code。
2. Who it is for：teams with agent code that now need deployment, governance, replay, audit。
3. What it is not：not a low-code builder, not a prompt IDE, not a replacement framework。
4. 10-minute path：publish, deploy, run, inspect。
5. Evidence demo：failed run -> replay -> audit。
6. Integrates with：LangGraph, LangChain, DeepAgents, LiteLLM, Langfuse, OpenTelemetry。
7. Product paths：evaluator、developer、operator、security、platform。

Docs 建议新增：

- `docs/start/import-existing-agent.md`
- `docs/start/runtime-control-demo.md`
- `docs/start/evaluator-path.md`
- `docs/start/operator-path.md`
- `docs/start/security-path.md`
- `docs/reference/adapter-certification.md`
- `docs/reference/sdk-parity.md`
- `docs/reference/error-codes.md`
- `docs/reference/api-stability.md`
- `docs/reference/extension-model.md`
- `docs/reference/environment-drift.md`
- `docs/reference/published-surfaces.md`
- `docs/comparisons/langfuse.md`
- `docs/comparisons/litellm.md`
- `docs/comparisons/temporal-hatchet.md`
- `docs/integrations/litellm.md`
- `docs/integrations/langfuse.md`
- `docs/integrations/opentelemetry.md`
- `docs/security/package-trust.md`
- `docs/security/compliance-readiness.md`
- `docs/quality/feedback-loop.md`
- `docs/runtime/scheduled-and-batch.md`
- `docs/operations/incidents-and-alerts.md`
- `docs/operations/cost-budget-governance.md`
- `docs/catalog/runtime-assets.md`
- `docs/operations/backup-restore.md`
- `docs/operations/upgrade.md`
- `docs/product/packaging-boundary.md`

## 风险与反定位

需要避免的风险：

- 功能范围过宽，但没有一条用户路径特别顺。
- 页面很多，但用户不知道第一天该做什么。
- 前端看起来像后台 CRUD，而不是可信的 operator workbench。
- Console 只展示指标，不给下一步行动。
- 与成熟项目正面竞争 observability/gateway/workflow，而没有强调 agent-native runtime。
- 没有 API 稳定策略，导致早期集成用户担心后续 breaking changes。
- 没有开源/企业边界，导致 roadmap 和贡献优先级摇摆。
- 没有合规证据地图，导致安全团队即使认可功能也无法推进评估。
- 集成靠硬编码堆叠，导致每接一个工具都增加核心 runtime 复杂度。
- 把 local proof 误说成 hosted production proof。
- 把 route coverage 误说成 complete operator workflow。

推荐反定位：

```text
If you need to build a simple app visually, use Dify or Flowise.
If you need an agent framework, use LangGraph, CrewAI, or LangChain.
If you need LLM observability, use Langfuse or Phoenix.
If you need an AI gateway, use LiteLLM or Portkey.
If you already have agent code and need to operate it safely, use DimooRun.
```

## 优先级总表

| 优先级 | 项目 | 价值 | 验收 |
|---|---|---|---|
| P0 | 简化 first-run CLI | 降低试用门槛 | 10 分钟看到 Console run detail |
| P0 | 护城河 demo | 证明差异化 | failed run -> replay -> audit 全链路可跑 |
| P0 | README 重写首屏叙事 | 减少误解 | 首屏明确 existing agent runtime control |
| P0 | Trusted package runtime | 建立运行可信边界 | AgentVersion 展示 validation/digest/signature/SBOM/sandbox |
| P0 | Console command center | 提升第一眼吸引力 | Dashboard 给出 next actions |
| P0 | Run triage UX | 提升核心工作流体验 | failed run 能定位、replay、rollback、导出 audit |
| P0 | Quickstart/demo seed | 降低首次试用阻力 | fresh checkout 10 分钟内看到 run evidence |
| P1 | Langfuse 集成 | 避免观测正面竞争 | Run detail 有 trace link |
| P1 | LiteLLM 集成 | 避免 gateway 正面竞争 | Deployment 可绑定 model gateway |
| P1 | Adapter certification matrix | 降低框架接入不确定性 | 每个 adapter 有 capability 状态 |
| P1 | 对比页 | 转化竞品用户 | 4 篇 comparison docs |
| P1 | Console 首页 operator journey | 提升易用性 | 首页直接引导 Publish/Deploy/Run/Triage |
| P1 | SDK/API DX | 提升工程采用 | SDK parity、typed errors、examples |
| P1 | Enterprise readiness | 提升平台信任 | backup/RBAC/audit/retention/upgrade 文档 |
| P1 | API stability and migration | 提升长期接入信心 | stable/experimental/deprecated 边界清晰 |
| P1 | Compliance readiness | 提升安全评估信任 | trust evidence bundle 可生成 |
| P1 | Integration extension model | 降低生态扩展成本 | gateway/exporter/secret/artifact/policy/adapter 接口清晰 |
| P1 | Quality feedback loop | 提升晋级可信度 | dataset/experiment/quality gate 贯通 promotion |
| P1 | Scheduled/batch runtime operations | 支持真实生产负载 | schedule preview、batch retry/dead-letter、cancel summary 可用 |
| P1 | Cost budget and quota governance | 降低企业成本风险 | budget policy 能 reject/approval/notify 并留痕 |
| P1 | Incident alert and webhook workflow | 提升 on-call 可用性 | failed run 可升级 incident 并产生 delivery evidence |
| P1 | Environment drift control | 提升多环境上线信心 | staging/prod diff、scope inheritance、promotion path 可见 |
| P1 | Published agent surface | 提升对外调用能力 | endpoint request 能关联 request log 和 run evidence |
| P2 | Catalog asset lifecycle | 治理运行依赖资产 | prompt/config/MCP asset version、diff、dependency 可见 |
| P2 | Hosted proof | 提升信任 | CI artifact 可公开验证 |
| P2 | Helm/SDK/release hardening | 提升生产可信度 | readiness scorecard 更新 |
| P2 | API test performance | 提升贡献体验 | 核心 API suite 可在稳定时间内完成 |
| P2 | Community ecosystem | 提升传播和贡献 | examples、issue templates、good first issues |

## 最终判断

DimooRun 的护城河不是“我也有 observability / guardrails / workflow / agent UI”，而是：

```text
我把已有 agent 代码变成可运行、可治理、可回放、可审计的生产运行单元。
```

只要接入体验足够短、证据链 demo 足够强、与 Langfuse/LiteLLM/Temporal 等相邻工具的互补关系足够清晰，DimooRun 就有机会从成熟 agent 工程团队中切出一块明确用户群。
