# 08 前端 Console 产品执行计划

> **给执行 Agent 的要求：** Console 是 DimooRun 的核心竞争力之一。实现时必须做 Runtime Control Plane，不允许做低代码 Builder、拖拽画布或营销首页。

**目标：** 构建一个模块规划合理、视觉精致、信息密度高、适合企业运维的 DimooRun Console，用于展示运行状态、控制 Deployment、查看 Run Timeline、调试 Replay、治理权限、审计风险和观察成本。

**架构说明：** Console 通过 OpenAPI 生成 SDK 调用后端。前端只展示权限结果和发起动作，真实权限由后端 Policy Engine 决定。高风险动作必须二次确认，并提示 AuditLog。

**设计覆盖：** `DESIGN_SPEC.md` 第 7.4、26、31、38、47、48、53、54 章。

---

## 实施结果

- [x] Console 保持 Runtime Control Plane 定位，没有加入低代码画布、Prompt 设计器或营销首页。
- [x] 已实现 Vue 3 / TypeScript / Vite / Vue Router / Pinia 前端骨架。
- [x] 已实现 Dashboard、Agents、Deployments、Compatibility、Published Surfaces、Runs、Run Detail、Tasks、Events、Debug / Replay、Human Tasks、Policies、API Keys、Settings。
- [x] 已实现中英文切换、明暗主题切换、tenant / project / environment selector、全局搜索入口、live refresh 开关。
- [x] 已实现 Deployment pause / resume / restart 的高风险操作确认弹窗，并展示影响对象、环境、新 Run、已有 Run、AuditLog 和可回滚信息。
- [x] 已实现 Event Timeline、Run cost breakdown、ECharts runtime trend、状态 badge、metric cards 等基础组件。
- [x] 已新增 `consoleClient` 边界，先用 mock 数据模拟后端聚合 API，后续 09 阶段接入生成 SDK。
- [x] 已新增前端契约测试 `npm run test`，并通过 `npm run build` 验证。

暂缓到后续阶段：

- [ ] 真实 OpenAPI SDK 生成和 API 接线。
- [ ] 真实 SSE Last-Event-ID reconnect client。
- [ ] 完整 Console 后端聚合 API。
- [ ] 完整权限 summary 驱动的按钮级可见性。
- [ ] 复杂 Console 页面：Workers、Agent Instances、Trace waterfall、Costs、Alerts、Datasets、Experiments、Users、Roles、Backups。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 7.4 章：Frontend Console。
- [x] 第 24.1 章：Deployment Runtime Control。
- [x] 第 26 章：Published Runtime Surfaces。
- [x] 第 31 章：Human-in-the-loop Governance。
- [x] 第 38 章：API 设计。
- [x] 第 47 章：可观测性。
- [x] 第 48 章：前端 Console 设计。
- [x] 第 53 章：MVP 范围。
- [x] 第 54 章：Roadmap。

## 1. 产品定位

Console 的定位：

```text
DimooRun Console = Runtime Control Plane 的主要交互入口。
```

Console 必须回答：

```text
Agent 当前能不能运行？
Deployment 是否接收新请求？
Worker 是否健康？
AgentInstance 加载在哪些 Worker 上？
Run 为什么失败？
Task 为什么积压？
成本和 Token 消耗在哪里？
高风险 Tool / Secret / Model 调用是否合规？
失败 Run 能否 replay、对比和沉淀为 Dataset？
```

Console 不做：

```text
拖拽 Agent 编排画布
Prompt 设计器
知识库构建器
业务 Workflow Builder
业务 Tool 开发 IDE
营销落地页
```

## 2. 技术栈

```text
Vue 3
TypeScript
Vite
Vue Router
Pinia
Naive UI
ECharts
Monaco Editor
Axios 或 TanStack Query
openapi-typescript / orval
```

## 3. 文件规划

```text
apps/console/src/main.ts
apps/console/src/App.vue
apps/console/src/router/index.ts
apps/console/src/api/client.ts
apps/console/src/layouts/AppShell.vue
apps/console/src/components/StatusBadge.vue
apps/console/src/components/MetricCard.vue
apps/console/src/components/ConfirmImpactDialog.vue
apps/console/src/components/ResourceLink.vue
apps/console/src/components/TimeRangePicker.vue
apps/console/src/components/EventTimeline.vue
apps/console/src/components/RunCostBreakdown.vue
apps/console/src/pages/dashboard/DashboardPage.vue
apps/console/src/pages/agents/AgentsPage.vue
apps/console/src/pages/deployments/DeploymentsPage.vue
apps/console/src/pages/runs/RunsPage.vue
apps/console/src/pages/runs/RunDetailPage.vue
apps/console/src/pages/tasks/TasksPage.vue
apps/console/src/pages/replay/ReplayPage.vue
apps/console/src/pages/governance/PoliciesPage.vue
apps/console/src/pages/governance/HumanTasksPage.vue
apps/console/src/pages/governance/ToolsPage.vue
apps/console/src/pages/governance/ModelGatewaysPage.vue
apps/console/src/pages/governance/SecretsPage.vue
apps/console/src/pages/governance/ServiceAccountsPage.vue
apps/console/src/pages/governance/ApiKeysPage.vue
apps/console/src/pages/governance/AuditLogsPage.vue
apps/console/src/pages/settings/SettingsPage.vue
```

## 4. 视觉与交互原则

视觉方向：

```text
专业
克制
精致
工程化
信息密度高
层次清晰
```

参考气质：

```text
Linear
Datadog
Grafana
Vercel
Supabase
Langfuse
```

不采用：

```text
低代码画布风
营销落地页风
过度渐变装饰
玩具感后台
大面积空泛卡片
```

状态颜色：

```text
success: succeeded / ready / active
warning: degraded / retrying / pending approval
danger: failed / timeout / policy denied / dead letter
neutral: draft / paused / stopped / archived
running: running / warming_up / draining / loading
```

全局交互：

- [ ] tenant / project / environment switcher。
- [ ] global search。
- [ ] command menu。
- [ ] saved filters。
- [ ] time range selector。
- [ ] live refresh / pause refresh。
- [ ] copy id。
- [ ] copy curl。
- [ ] deep link to resource。
- [ ] drawer detail view。
- [ ] bulk action with confirmation。

## 5. 信息架构

一级分组：

```text
Overview
Runtime
Observability
Governance
Quality
Platform
```

导航：

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

MVP 菜单：

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

## 6. Dashboard 页面

展示：

```text
今日 Run 数
成功率
失败率
平均耗时
P95 耗时
P99 耗时
队列积压
Worker 状态
Deployment 健康状态
AgentInstance 数量
Token 消耗
成本
错误趋势
Top failed agents
Top cost agents
最近 critical alerts
pending human tasks
```

布局：

```text
顶部：tenant / project / environment selector
第一行：核心 KPI compact cards
第二行：Run volume / success rate / cost trend
第三行：queue backlog / worker health / deployment health
第四行：recent failures / active alerts / pending human tasks
```

## 7. Agents 页面

展示：

- [ ] Agent 列表。
- [ ] AgentVersion 列表。
- [ ] framework / adapter。
- [ ] capabilities。
- [ ] manifest 查看。
- [ ] 调用入口。
- [ ] 关联 Deployments。
- [ ] 最近 Run 状态。
- [ ] 最近发布版本。

页面必须解释对象边界：

```text
Agent 是逻辑对象。
AgentVersion 是不可变包。
Deployment 是运行入口。
AgentInstance 是 Worker 上实际加载实例。
```

## 8. Deployments 页面

展示：

```text
deployment_id
agent / version / environment
desired_status / runtime_status
activate / pause / resume / drain / stop / restart
当前 AgentInstance 数量
running runs
queue backlog
最近错误
所在 Worker
实例启动时间
最近 heartbeat
ExecutionProfile
绑定 Policy / ModelGateway / Secret / PublishedSurface
```

详情布局：

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

高风险操作：

- [ ] pause。
- [ ] drain。
- [ ] stop。
- [ ] restart。
- [ ] rollback。

确认弹窗必须展示：

```text
影响对象
影响环境
是否影响新 Run
是否影响已有 Run
是否写 AuditLog
是否可回滚
```

## 9. Runs 与 Run Detail

Runs 列表字段：

```text
run_id
agent
framework
adapter
version
user / service_account
status
latency
cost
started_at
finished_at
trigger: api | schedule | replay | batch | compatibility
deployment
trace_id
```

Run 详情布局：

```text
左侧：event timeline
中间：当前选中 event / span / tool call / model call 详情
右侧：run metadata、cost、attempts、checkpoint、policy decisions
底部：input / output / artifacts / logs tabs
```

Timeline 事件：

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

## 10. Tasks 页面

字段：

```text
task_id
run_id
status
attempt
queue
worker_id
heartbeat_at
lease_until
fencing_token
retry_count
dead_letter_reason
error
```

必须支持：

- [ ] 按 queue 过滤。
- [ ] 按 status 过滤。
- [ ] 查看 retry history。
- [ ] 查看 dead letter reason。
- [ ] 跳转 Run。

## 11. Debug / Replay 页面

工作流：

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

规则：

- [ ] 原始 Run 只读。
- [ ] Replay 产生新 Run。
- [ ] 对比视图必须展示差异。
- [ ] 可跳转 Dataset / Experiment。

## 12. Governance 页面

Policies：

- [ ] 策略列表。
- [ ] 匹配范围。
- [ ] 最近命中。
- [ ] deny / approval 统计。

Human Tasks：

- [ ] 待审批任务。
- [ ] 来源 Run / Tool / Secret / Model / Deployment。
- [ ] 风险等级。
- [ ] payload 摘要。
- [ ] approve / reject / escalate。
- [ ] 审批历史。

Tools：

- [ ] schema。
- [ ] risk_level。
- [ ] approval policy。
- [ ] 最近调用。

Model Gateways：

- [ ] gateway 状态。
- [ ] 模型组。
- [ ] 成本。
- [ ] 限流。
- [ ] 错误。

Secrets：

- [ ] secret 引用。
- [ ] last_used_at。
- [ ] 使用审计。
- [ ] 不展示明文。

Service Accounts：

- [ ] 机器身份。
- [ ] scopes。
- [ ] API keys。
- [ ] last_used_at。

Audit Logs：

- [ ] actor。
- [ ] action。
- [ ] resource。
- [ ] result。
- [ ] request_id。

## 13. 前后端契约

规则：

- [ ] 所有 API 类型从 OpenAPI 生成。
- [ ] 列表页使用 cursor pagination。
- [ ] 时间统一 ISO 8601，前端按用户时区展示。
- [ ] 金额和 token 使用后端返回标准单位。
- [ ] 错误展示基于稳定 error code。
- [ ] SSE stream client 支持 Last-Event-ID 和 reconnect。
- [ ] 前端不可缓存 Secret 明文。
- [ ] 前端展示权限由后端 permission summary 决定。

## 13.1 Console 后端聚合 API

Console 不应在前端拼接大量底层 API 来生成 Dashboard 和健康视图。聚合数据应由后端按 tenant/project/environment 权限过滤后返回。

建议新增 Console API：

```http
GET /v1/console/dashboard-summary
GET /v1/console/runtime-overview
GET /v1/console/deployment-health
GET /v1/console/worker-health
GET /v1/console/cost-summary
GET /v1/console/recent-failures
GET /v1/console/pending-actions
```

API 语义：

```text
dashboard-summary:
  今日 Run 数、成功率、失败率、P95/P99、成本、Token、critical alerts。

runtime-overview:
  running runs、queue backlog、worker count、agent instance count。

deployment-health:
  deployment_id、desired_status、runtime_status、last_error、running_runs、instance_count。

worker-health:
  worker_id、status、heartbeat_lag、loaded_instances、running_runs。

cost-summary:
  按 agent / deployment / model / tenant 归因的 cost 和 token。

recent-failures:
  最近 failed / timeout / dead_letter Run 和 Task。

pending-actions:
  pending approvals、draining deployments、backup failures、policy violations。
```

规则：

- [ ] 聚合 API 必须经过 Policy Engine。
- [ ] 聚合 API 不能泄露用户无权查看的 Run input/output。
- [ ] 聚合 API 默认按当前 tenant/project/environment 过滤。
- [ ] 聚合 API 返回稳定 schema，Console 不直接依赖数据库字段。
- [ ] Dashboard、Deployments、Workers、Costs 页面优先使用聚合 API。

## 14. MVP 验收

- [x] Dashboard 能展示 Run、Task、Worker、成本、错误趋势。
- [x] Agents 页面能查看 AgentVersion、manifest、capabilities。
- [x] Deployments 页面能展示 desired_status / runtime_status。
- [x] Deployments 页面能发起 pause / resume / restart。
- [x] Runs 页面能过滤、搜索、进入 Run 详情。
- [x] Run 详情能展示 Timeline、input/output、attempts、error、cost。
- [x] Tasks 页面能展示 lease、heartbeat、retry、dead letter。
- [x] API Keys 页面能创建、禁用、查看 scopes。
- [x] Compatibility 页面能展示 LangGraph assistants / threads / runs 映射。
- [x] 高风险操作有确认弹窗和 AuditLog 提示。

命令：

```bash
cd apps/console
npm run typecheck
npm run build
```

## 15. 提交建议

```text
feat: build runtime control console
```

## 16. 设计回查清单

- [x] Console 没有低代码画布、Prompt 设计器、Workflow Builder，符合第 48.1 章。
- [x] 信息架构覆盖第 48.4 章。
- [x] MVP 菜单覆盖第 48.5 章。
- [ ] Phase 2 菜单覆盖第 48.6 章。
- [x] Dashboard / Agents / Deployments / Runs / Run Detail / Tasks / Replay / Governance 页面覆盖第 48.7 章。
- [x] 高风险操作确认覆盖第 48.8 章。
- [x] 状态颜色和空态覆盖第 48.9 章。
- [ ] API 类型生成和 SSE reconnect 覆盖第 48.10 章。
- [x] MVP 前端验收覆盖第 48.11 章。
- [x] Dashboard 和健康视图保留后端聚合 API client 边界，不直接绑定数据库字段。
