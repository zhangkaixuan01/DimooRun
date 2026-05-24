# 10 企业运维与云原生执行计划

> **给执行 Agent 的要求：** 企业能力必须建立在已有 Runtime、治理和观测基础上。不要在核心闭环完成前实现复杂云原生功能。

**目标：** 实现 Dev / Production / Enterprise 部署模式、Docker Compose、Backup / Restore / DR、Extension API、HA / Scaling、K8s / Helm、企业级运维边界。

**架构说明：** Dev Mode 让开发者快速启动；Production Mode 验证 server + worker + Postgres + Redis；Enterprise Mode 增加高隔离、高可用、对象存储、队列分区、扩容、备份恢复和扩展治理。

**设计覆盖：** `DESIGN_SPEC.md` 第 17、18、33.1、42、47.5、51、54 Phase 3/4 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [ ] 第 17 章：Deployment Modes。
- [ ] 第 18 章：Execution Isolation & Sandbox。
- [ ] 第 33.1 章：Backup / Restore / Disaster Recovery。
- [ ] 第 42 章：HA / Scaling Design。
- [ ] 第 47.5 章：Notification / Alerting。
- [ ] 第 51 章：Extension API。
- [ ] 第 54 章：Roadmap Phase 3 / Phase 4。

## 1. 部署模式

Dev Mode：

```text
目标：本地开发、快速调试。
运行方式：in-process。
存储：SQLite / in-memory。
队列：in-process queue。
Agent 执行：本进程。
入口：dimoorun dev。
```

Production Mode：

```text
目标：单机或小集群生产。
运行方式：server + worker。
存储：Postgres。
队列：Redis。
事件：Redis Stream / Postgres Event。
执行：Worker Pool。
入口：Docker Compose。
```

Enterprise Mode：

```text
目标：企业级大规模运行。
运行方式：API Server + Worker Pool + Sandbox / Container Pool。
存储：Postgres HA / Object Storage。
队列：Redis Cluster / Kafka / Temporal。
事件：Kafka / Redis Stream。
执行：K8s worker / remote worker / container sandbox。
适用：多租户、高隔离、高可用。
```

## 2. 文件规划

```text
docker-compose.yml
deploy/docker/server.Dockerfile
deploy/docker/worker.Dockerfile
deploy/docker/console.Dockerfile
deploy/helm/dimoorun/Chart.yaml
deploy/helm/dimoorun/values.yaml
deploy/helm/dimoorun/templates/server.yaml
deploy/helm/dimoorun/templates/worker.yaml
deploy/helm/dimoorun/templates/console.yaml
deploy/helm/dimoorun/templates/ingress.yaml
apps/server/dimoo_run/extensions/webhooks.py
apps/server/dimoo_run/backup/service.py
apps/server/dimoo_run/ha/reaper.py
apps/server/dimoo_run/ha/quotas.py
apps/server/dimoo_run/ha/partitioning.py
tests/enterprise/
```

## 3. Docker Compose

服务：

```text
server
worker
console
postgres
redis
minio
```

健康检查：

```text
server /healthz
worker heartbeat
postgres readiness
redis ping
console static readiness
minio readiness
```

配置：

- [ ] server 使用 Postgres 和 Redis。
- [ ] worker 使用同一 Postgres 和 Redis。
- [ ] console 指向 server API。
- [ ] object store 默认 MinIO。
- [ ] `.env.example` 提供必要变量。

验收：

```powershell
docker compose up
```

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
created_at
updated_at
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
created_at
updated_at
```

规则：

- [ ] extension auth。
- [ ] extension permissions。
- [ ] request audit。
- [ ] rate limit。
- [ ] Policy Engine enforcement。
- [ ] webhook 失败不影响核心 Runtime。

Custom Routes：

- [ ] 不进入 MVP。
- [ ] 进入 Phase 3 后必须 route namespace isolation。
- [ ] 必须 extension sandbox。
- [ ] 默认不能访问平台内部对象。
- [ ] 调用必须写 AuditLog。

## 6. HA / Scaling

Production 必须实现：

```text
lease reaper
fencing token
Redis pub/sub cancel
tenant concurrency quota
project concurrency quota
queue partition
```

Enterprise 演进：

```text
run sharding
leaderless reaper
multi-region
Kafka partition
Temporal backend
worker autoscaling
```

Quota：

```text
tenant_max_running_runs
project_max_running_runs
agent_max_concurrency
worker_max_concurrency
model_gateway_rate_limit
tool_gateway_rate_limit
```

Queue partition：

```text
by tenant
by project
by priority
by agent
by resource class
```

## 7. Notification / Alerting 企业出口

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

## 8. Cloud Native / Helm

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

## 9. 企业验收流程

完整流程：

```text
docker compose up
  ↓
server /healthz healthy
  ↓
worker heartbeat healthy
  ↓
register Agent
  ↓
create AgentVersion
  ↓
activate Deployment
  ↓
invoke Run
  ↓
trigger alert
  ↓
create backup
  ↓
restore dry-run
  ↓
subscribe webhook
  ↓
drain Deployment
  ↓
scale worker
  ↓
queue drains
```

## 10. 验收清单

- [ ] Docker Compose 服务全部 healthy。
- [ ] BackupPlan 可创建。
- [ ] RestoreJob dry-run 可生成 validation report。
- [ ] WebhookSubscription 可接收事件。
- [ ] lease reaper 可回收过期任务。
- [ ] tenant / project quota 生效。
- [ ] Helm chart 可 render。
- [ ] Worker 扩容后队列积压下降。

命令：

```powershell
uv run pytest tests/enterprise -q
docker compose up
helm template dimoorun deploy/helm/dimoorun
```

## 11. 提交建议

```text
feat: add enterprise ops and cloud native deployment
```

## 12. 设计回查清单

- [ ] Dev / Production / Enterprise 模式符合第 17 章。
- [ ] Sandbox 和 container pool 边界符合第 18 章。
- [ ] BackupPlan / RestoreJob / dry-run validation 覆盖第 33.1 章。
- [ ] lease reaper、fencing token、quota、partition 覆盖第 42 章。
- [ ] NotificationChannel / AlertRule / IncidentEvent 覆盖第 47.5 章。
- [ ] Extension API 第一阶段只实现 Webhook Subscription，符合第 51 章。
- [ ] Cloud Native 范围与第 54 Phase 4 一致，没有提前实现多区域复杂能力。
