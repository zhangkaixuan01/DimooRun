# 12 企业运维与云原生执行计划

> **给执行 Agent 的要求：** 本阶段建立企业运维、灾备、云原生和安全扩展能力。必须建立在 10 的生产化基础闭环和 11 的 Runtime 生产级加固之上。

**目标：** 实现 Backup / Restore / DR、Extension Webhook Subscription、Notification / Alerting、生产对象存储、外部观测导出、Helm / K8s、Sandbox / Container Pool 边界和企业级运维验收。

**架构说明：** 12 阶段不是改变 DimooRun 的产品本质，而是把 Runtime Control Plane 放进企业环境：可备份、可恢复、可观测、可告警、可扩展、可部署、可审计。

**设计覆盖：** `DESIGN_SPEC.md` 第 18、33、33.1、42、47、47.5、51、54 Phase 3/4 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [ ] 第 18 章：Execution Isolation & Sandbox。
- [ ] 第 33 章：Artifact Store。
- [ ] 第 33.1 章：Backup / Restore / Disaster Recovery。
- [ ] 第 42 章：HA / Scaling Design。
- [ ] 第 47 章：可观测性。
- [ ] 第 47.5 章：Notification / Alerting。
- [ ] 第 51 章：Extension API。
- [ ] 第 54 章：Roadmap Phase 3 / Phase 4。

## 1. 本阶段边界

必须完成：

- [ ] production Artifact Store backend。
- [ ] external observability exporters。
- [ ] BackupPlan。
- [ ] RestoreJob dry-run validation。
- [ ] NotificationChannel / AlertRule / IncidentEvent。
- [ ] Event Webhook Subscription。
- [ ] Helm chart render。
- [ ] K8s deployment manifests。
- [ ] sandbox / container pool 企业边界。

后续可选，不作为本阶段必须完成：

- [ ] multi-region。
- [ ] Kafka partition。
- [ ] Temporal backend。
- [ ] leaderless reaper。
- [ ] Custom Routes 开放式后端扩展。

## 2. Production Artifact Store

后端：

```text
local
S3-compatible
MinIO
```

要求：

- [ ] Artifact metadata 与 object data 分离。
- [ ] checksum 写入与读取校验。
- [ ] tenant/project scope 校验。
- [ ] signed URL 或受控下载。
- [ ] 大 payload 只在 Event 中保存 ref。
- [ ] object store backend 可通过配置切换。

## 3. 外部观测导出

导出目标：

```text
OpenTelemetry
Langfuse
Phoenix
custom webhook sink
```

要求：

- [ ] redaction 在导出前执行。
- [ ] sampling 在导出前执行。
- [ ] exporter 失败不影响核心 Runtime。
- [ ] exporter 有 retry / dead letter 或可见失败状态。
- [ ] trace / event / audit 三账本边界不混淆。
- [ ] Secret 不进入外部导出。

## 4. Backup / Restore / DR

BackupPlan：

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
created_by
created_at
updated_by
updated_at
is_deleted
```

RestoreJob：

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
updated_by
updated_at
is_deleted
```

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

规则：

- [ ] restore 先 dry-run validation。
- [ ] Artifact metadata 与 object data 校验 checksum。
- [ ] 恢复的历史 Run / Event / AuditLog 不重新解释为新执行。
- [ ] checkpoint 恢复只恢复索引和可访问性。
- [ ] Enterprise Mode 定义 RPO / RTO。
- [ ] restore action 必须写 AuditLog。

## 5. Extension API

第一阶段只做：

```text
Event Webhook Subscription
```

WebhookSubscription：

```text
tenant_id
project_id nullable
name
event_types
target_url
secret_ref
status
retry_policy
created_by
created_at
updated_by
updated_at
is_deleted
```

规则：

- [ ] extension auth。
- [ ] extension permissions。
- [ ] request audit。
- [ ] rate limit。
- [ ] Policy Engine enforcement。
- [ ] webhook 失败不影响核心 Runtime。
- [ ] webhook payload 经过 redaction。
- [ ] webhook secret 不明文展示。

Custom Routes：

- [ ] 不进入本阶段必须范围。
- [ ] 进入后续 Phase 3+ 后必须 route namespace isolation。
- [ ] 必须 extension sandbox。
- [ ] 默认不能访问平台内部对象。
- [ ] 调用必须写 AuditLog。

## 6. Notification / Alerting

通道：

```text
email
webhook
Slack
Teams
Feishu
DingTalk
PagerDuty
custom
```

企业要求：

- [ ] incident 可 acknowledge / resolve。
- [ ] 告警有 dedupe window。
- [ ] 告警有 cooldown。
- [ ] 安全事件进入 AuditLog。
- [ ] 通知失败不影响 Runtime。
- [ ] 通知 payload 经过 redaction。
- [ ] AlertRule 支持 tenant/project scope。

## 7. Cloud Native / Helm

values：

```text
server.replicas
worker.replicas
console.ingress
postgres.external
redis.external
objectStore.external
secretProvider.mode
sandbox.mode
resources
autoscaling
```

K8s 对象：

```text
Deployment server
Deployment worker
Deployment console
Service server
Service console
Ingress api/console
ConfigMap
Secret references
ServiceAccount
HorizontalPodAutoscaler
```

验收：

```powershell
helm template dimoorun deploy/helm/dimoorun
```

## 8. Sandbox / Container Pool

要求：

- [ ] sandbox policy 与 06 阶段 SandboxPolicy 对齐。
- [ ] container pool 不绕过 Deployment desired status。
- [ ] 资源限制可配置。
- [ ] secret 注入最小权限。
- [ ] sandbox 执行事件进入 AuditLog / Event。
- [ ] sandbox 失败不会破坏核心 Runtime state。

## 9. 企业验收流程

```text
docker compose up
  ↓
server / worker / console healthy
  ↓
run production runtime smoke
  ↓
export trace to external sink
  ↓
create backup
  ↓
restore dry-run
  ↓
subscribe webhook
  ↓
trigger alert
  ↓
acknowledge incident
  ↓
helm template
```

## 10. 验收清单

- [ ] BackupPlan 可创建。
- [ ] RestoreJob dry-run 可生成 validation report。
- [ ] Artifact Store 使用生产 backend。
- [ ] external observability exporter 可配置。
- [ ] WebhookSubscription 可接收事件。
- [ ] Notification / Alerting 可触发 incident。
- [ ] Helm chart 可 render。
- [ ] Sandbox / Container Pool 边界符合设计。

命令：

```powershell
uv run pytest tests/enterprise -q
uv run ruff check .
uv run mypy apps/server tests scripts
docker compose up
helm template dimoorun deploy/helm/dimoorun
```

## 11. 提交建议

```text
feat: add enterprise ops and cloud native deployment
```

## 12. 设计回查清单

- [ ] BackupPlan / RestoreJob / dry-run validation 覆盖第 33.1 章。
- [ ] NotificationChannel / AlertRule / IncidentEvent 覆盖第 47.5 章。
- [ ] Extension API 第一阶段只实现 Webhook Subscription，符合第 51 章。
- [ ] Cloud Native 范围与第 54 Phase 4 一致，没有提前实现多区域复杂能力。
- [ ] Custom Routes 没有绕过 Policy Engine。
- [ ] 企业能力没有改变 DimooRun “Adapter-first Runtime / Ops / Control Plane”的项目精髓。
