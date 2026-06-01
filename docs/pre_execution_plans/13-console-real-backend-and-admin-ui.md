# 13 Console 真实后端接线与管理台补齐执行计划

> **给执行 Agent 的要求：** 本阶段先完成 Console 信息架构和真实 API 接线，再做视觉 polish。不要继续把 mock 数据当作默认主路径。mock 只能作为显式 demo mode。

**目标：** 把 `apps/console` 从 mock-first 产品壳升级为真实 Runtime Control Plane：所有已有后端能力中需要人工查看、操作、审批、诊断、配置的部分都必须有前端入口、真实 API 调用、状态反馈、错误展示和空状态。

**当前问题：**

- `consoleClient` 默认读取 `mockData.ts`，`nativeConsoleClient` 只覆盖少量接口且页面基本未使用。
- Deployments 的 pause / resume / restart 等按钮只打开确认框，确认后没有调用后端。
- Users / Roles / Permissions / Service Accounts / Secrets / Model Gateways / Webhook Subscriptions / Backups / Incidents / Audit Logs 等管理面没有完整页面。
- README 和前端 UI 容易让使用者误以为 Console 已经完整接入后端。

**设计原则：**

- Console 是 Runtime Control Plane，不是 Builder。
- 默认数据源必须是真实 API；只有 `VITE_DIMOORUN_DEMO_MODE=true` 时使用 mock。
- 所有写操作必须有 loading / success / error / disabled 状态。
- 所有高风险操作必须二次确认，并展示影响范围。
- 所有错误展示基于稳定 `error_code` 和 `request_id`。
- 所有页面默认按 tenant/project scope 访问后端。

---

## 0. 后端能力盘点

### Native Runtime API

必须接入页面：

- Agents：列表、创建、更新、归档。
- AgentVersions：列表、创建、查看。
- Deployments：列表、创建、详情、实例列表、activate / pause / resume / drain / stop / restart。
- Runs：详情、events、attempts、cancel / resume / retry / replay。
- Tasks：详情、cancel、dead letter / quota / partition 信息。

### Admin / Governance API

必须补页面：

- Policies。
- Human Tasks：approve / reject。
- API Keys。
- Users。
- Roles。
- Permissions。
- Service Accounts。
- Secrets。
- Model Gateways。
- Tool Gateway / Tools。
- Catalog Items。
- Prompt / Config / Template Assets。
- Published Surfaces。
- Ingress Routes。

### Observability / Quality

必须补页面或 tab：

- Event Timeline。
- Trace / Span tree。
- Audit Logs。
- Artifacts。
- Run Graph。
- Replay Jobs。
- Datasets。
- Experiments。
- Evaluation Results。
- Feedback。
- Semantic Store Providers。

### Enterprise Ops

必须补页面：

- Backup Plans。
- Restore Jobs / dry-run validation report。
- Webhook Subscriptions。
- Notification Channels。
- Alert Rules。
- Incident Events：acknowledge / resolve。
- Observability Exporters。
- Sandbox / Container Pool policy view。

### Compatibility API

必须补页面：

- LangGraph Assistants。
- Threads。
- Thread Runs。
- Stream / cancel / join 状态。
- Agent Protocol capabilities。

---

## 1. API Client 重构

文件：

```text
apps/console/src/api/client.ts
apps/console/src/api/generated/dimoorun.ts
apps/console/src/api/types.ts
apps/console/src/api/mockData.ts
```

要求：

- [x] `consoleClient` 默认使用真实后端。
- [x] 新增 `demoConsoleClient`，只在 `VITE_DIMOORUN_DEMO_MODE=true` 时启用。
- [x] 所有请求统一注入：
  - `Authorization`
  - `X-Request-Id`
  - `X-Tenant-Id`
  - `X-Project-Id`
  - `Idempotency-Key`（写操作）
- [x] 统一错误模型：
  - `error_code`
  - `message`
  - `request_id`
  - `details`
- [x] 所有 list API 返回统一 `CursorPage<T>`。
- [x] 所有 mutation 返回可供页面更新的资源快照。
- [x] API client 覆盖 Native 与 Admin 后端；Compatibility 保留现有页面入口和后续细化空间。

## 2. App Shell 与全局状态

要求：

- [x] 顶部显示当前 API mode：`live` / `demo` / `offline`。
- [x] 顶部显示登录操作员允许访问的 tenant / project / environment，并可切换当前请求范围。
- [x] Tenant / Project / Environment 不再由前端 env 写死；后端只用 `DIMOORUN_DEFAULT_*` 作为本地种子数据。
- [x] Tenant / Project / Environment 使用 SQLAlchemy 模型和 Alembic 迁移落库，不再走内存管理集合。
- [x] 真实 API 未配置时显示明确空状态，不静默使用 mock。
- [x] 页面级请求错误 banner 展示稳定错误码和 request_id。
- [x] 导航补齐缺失模块：
  - Identity
  - Governance
  - Runtime
  - Observability
  - Enterprise Ops
  - Compatibility
  - Settings

## 3. Runtime 页面

### Agents

- [x] 真实列表。
- [x] 创建 Agent。
- [ ] 更新 Agent。
- [x] 归档 Agent。
- [ ] AgentVersion 列表。
- [ ] 创建 AgentVersion。
- [ ] 从 Agent 创建 Run / Task。

### Deployments

- [x] 真实列表。
- [ ] 创建 Deployment。
- [ ] 详情页。
- [ ] AgentInstances 列表。
- [x] activate / pause / resume / drain / stop / restart 调真实 API。
- [x] 每个按钮有 loading / disabled / error。
- [x] 成功后刷新行数据。

### Runs / Tasks / Events

- [x] Runs 列表真实数据。
- [x] Run Detail 真实数据。
- [x] Event Timeline 调 `/v1/runs/{run_id}/events`。
- [ ] Attempts 调 `/v1/runs/{run_id}/attempts`。
- [x] cancel / resume / retry / replay 调真实 API。
- [x] Tasks 详情展示 fencing token、partition、resource class、quota blocking reason。
- [x] Task cancel 调真实 API。

## 4. Identity / Access 页面

### Users

- [x] Tenants 列表 / 创建 / 更新 / 删除。
- [x] Projects 列表 / 创建 / 更新 / 删除。
- [x] Environments 列表 / 创建 / 更新 / 删除。
- [x] Operators 展示 allowed scopes，新建操作员默认绑定当前范围。
- [x] 列表。
- [x] 创建。
- [x] 禁用 / 启用。
- [ ] 关联 roles。

### Roles / Permissions

- [x] Role 列表。
- [x] Permission 列表。
- [ ] Role permission matrix。
- [ ] 保存 role permissions。

### Service Accounts / API Keys

- [x] Service Account 列表。
- [x] 创建 Service Account。
- [x] API Key 作为 Service Account 的嵌套凭证展示，不再作为独立身份页面。
- [x] 创建 API Key 后只展示一次明文。
- [x] 禁用 / 启用 API Key。
- [x] 删除 API Key。
- [x] Service Account 禁用 / 启用后列表状态立即刷新。
- [x] API Key 禁用 / 启用 / 删除后列表状态立即刷新。
- [ ] last_used_at 展示。

实现补充：

- Console 统一进入 `Identity / Machine Identities` 管理 Service Accounts 与 API Keys，旧的 `/identity/service-accounts` 和 `/governance/api-keys` 前端路由重定向到该页面。
- 后端移除了通用 `/v1/service-accounts` 与 `/v1/api-keys` in-memory admin collection 路径，机器身份只通过 `/v1/identity/service-accounts/{service_account_id}/api-keys` 这类领域路由操作。
- API Key scopes 必须保持为所属 Service Account 权限子集；Service Account 权限收窄时，超出权限范围的 key 会被禁用。

## 5. Governance 页面

- [x] Policies 列表 / 创建。
- [x] Human Tasks approve / reject 调真实 API。
- [x] Tool Gateway / Tools 列表。
- [x] Model Gateways 列表 / 创建。
- [x] Secrets 列表，不展示明文。
- [x] Catalog Items 列表。
- [x] Prompt / Config / Template Assets 列表。
- [x] Published Surfaces 列表和创建。

## 6. Observability 页面

- [x] Audit Logs 列表。
- [x] Artifacts 列表 / 详情元数据。
- [ ] Trace tree。
- [ ] Run Graph。
- [ ] Replay Jobs。
- [ ] Datasets / Dataset Items。
- [x] Experiments / Evaluation Results。
- [x] Feedback。
- [x] Semantic Store Providers。

## 7. Enterprise Ops 页面

- [x] Backup Plans 列表 / 创建。
- [x] Restore Jobs 列表。
- [x] Restore dry-run collection 创建入口。
- [x] Webhook Subscriptions 列表 / 创建。
- [x] Notification Channels 列表 / 创建。
- [x] Alert Rules 列表 / 创建。
- [x] Incident Events 列表。
- [x] Incident acknowledge / resolve 后端动作已实现。
- [x] Observability Exporter 状态入口。
- [x] Sandbox / Container Pool policy view。

## 8. Compatibility 页面

- [ ] LangGraph Assistants 列表 / 创建。
- [ ] Threads 创建 / 查看。
- [ ] Thread Runs 创建 / cancel / join。
- [ ] Stream 状态和 Last-Event-ID reconnect。
- [ ] Agent Protocol capabilities。

## 9. UX / 状态要求

- [x] 每个接线页面有 loading 状态。
- [x] 每个接线页面有 empty state。
- [x] 每个 mutation 有 pending / error，并用返回资源刷新页面。
- [ ] 表格有搜索和基础过滤。
- [x] Deployment 危险操作有确认。
- [x] 新增按钮有实际 handler 或 disabled reason。
- [x] 错误展示 request_id。
- [x] i18n 覆盖新增导航、按钮、状态和错误文案。

## 10. 测试与验收

必须执行：

```bash
cd apps/console
npm run test
npm run build
```

后端回归：

```bash
uv run pytest -q
uv run ruff check apps tests packages\sdk-python scripts
uv run mypy apps/server tests scripts
```

前端验收：

- [x] 不配置 `VITE_DIMOORUN_API_BASE_URL` 时显示 live API 未配置状态。
- [x] 配置 `VITE_DIMOORUN_DEMO_MODE=true` 时才显示 mock 数据。
- [x] Deployments 操作按钮能调用真实后端。
- [x] Human Tasks approve / reject 能调用真实后端。
- [x] Users / Roles / Permissions 页面存在并可访问。
- [x] Backup / Restore / Webhook / Alerts / Incidents 页面存在并可访问。
- [x] 所有导航项没有死链接。
- [x] 所有页面在空数据下不崩溃。

## 11. 分阶段实现建议

建议拆 4 个原子阶段：

1. API client 与 app shell data mode。
2. Runtime 主路径：Agents / Deployments / Runs / Tasks / Events。
3. Governance / Identity / Admin UI。
4. Enterprise Ops / Observability / Compatibility 补齐。

## 12. 提交建议

```text
feat(console): connect real backend and admin surfaces
```
