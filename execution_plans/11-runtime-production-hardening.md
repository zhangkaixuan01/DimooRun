# 11 Runtime 生产级加固执行计划

> **给执行 Agent 的要求：** 本阶段只加固 Runtime Plane 的生产可靠性。不要把 Backup、Helm、Webhook、Notification 等企业运维能力混入本阶段。

**目标：** 在 10 阶段生产化基础闭环之上，把任务队列、worker、streaming、取消、重试、限流、崩溃恢复和水平扩容做成生产级 Runtime。

**架构说明：** 11 阶段解决的是 Agent Runtime 最核心的生产问题：任务不能丢、旧 worker 不能覆盖新结果、取消要跨实例生效、慢消费者不能拖垮系统、租户和项目不能互相挤占资源。

**设计覆盖：** `DESIGN_SPEC.md` 第 20、21、29、40、41、42、47、53、54 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [ ] 第 20 章：Event Model。
- [ ] 第 21 章：Streaming Runtime。
- [ ] 第 29 章：Runtime State Machines。
- [ ] 第 40 章：Task Scheduler。
- [ ] 第 41 章：Worker Pool。
- [ ] 第 42 章：HA / Scaling Design。
- [ ] 第 47 章：可观测性。

## 1. 本阶段边界

必须完成：

- [ ] Redis Queue 支持 lease、heartbeat、retry、dead letter。
- [ ] lease reaper 生产实现。
- [ ] fencing token 跨 worker 写入保护。
- [ ] Redis pub/sub cancel。
- [ ] Task timeout / Run timeout。
- [ ] worker crash recovery。
- [ ] worker horizontal scaling 验证。
- [ ] tenant / project / agent concurrency quota。
- [ ] queue partition。
- [ ] streaming replay buffer 生产实现。
- [ ] cross-instance event fan-out。
- [ ] stream backpressure。

不在本阶段：

- [ ] Backup / Restore / DR。
- [ ] Helm / K8s。
- [ ] Extension Webhook。
- [ ] Notification / Alerting 企业出口。
- [ ] multi-region。
- [ ] Kafka / Temporal 生产替换。

## 2. Redis Queue 生产语义

队列能力：

```text
enqueue
lease
heartbeat
extend lease
complete
fail retryable
fail terminal
dead letter
cancel
requeue expired
```

规则：

- [ ] 每次 lease 生成递增 fencing token。
- [ ] complete / fail / event append 必须校验 task ownership 和 fencing token。
- [ ] lease timeout 后旧 worker 写入结果必须被拒绝。
- [ ] retry 必须记录 attempt number 和 retry reason。
- [ ] 超过 max_attempts 进入 dead letter。
- [ ] dead letter 对 Console 和 API 可见。

## 3. Lease Reaper

要求：

- [ ] 扫描 expired leased / running task。
- [ ] 根据 task 状态 requeue 或 terminal fail。
- [ ] 写 AuditLog 或 runtime event。
- [ ] 支持单实例运行。
- [ ] 多实例下不重复 requeue。
- [ ] reaper 自身有 heartbeat。

后续演进：

- [ ] leaderless reaper 放到 12+ 或更后。

## 4. Fencing Token

典型场景：

```text
Worker A lease task, token=1
Worker A 卡住，lease 过期
Worker B re-lease task, token=2
Worker A 恢复并尝试写结果
系统拒绝 token=1 的写入
```

实现要求：

- [ ] Task lease token 存 durable state。
- [ ] WorkerExecutor 写 Run / Task / Event 前校验 token。
- [ ] stale token 返回 `stale_fencing_token`。
- [ ] stale 写入要有测试覆盖。

## 5. Cancel 跨实例

要求：

- [ ] API cancel 写 durable cancel requested state。
- [ ] Redis pub/sub 广播 cancel。
- [ ] worker loop 订阅 cancel channel。
- [ ] Adapter 支持 cancel 时调用 Adapter cancel。
- [ ] Adapter 不支持 cancel 时标记 best-effort cancel。
- [ ] cancel event 对 stream 和 Console 可见。

## 6. Concurrency Quota

Quota：

```text
tenant_max_running_runs
project_max_running_runs
agent_max_concurrency
deployment_max_concurrency
worker_max_concurrency
model_gateway_rate_limit
tool_gateway_rate_limit
```

规则：

- [ ] quota 检查在 enqueue / lease 前生效。
- [ ] 超限返回稳定错误码。
- [ ] quota 释放必须和 terminal state 一致。
- [ ] Console 能展示 quota blocking reason。
- [ ] API Key / ServiceAccount 不能绕过 quota。

## 7. Queue Partition

分区维度：

```text
tenant
project
priority
agent
deployment
resource class
```

要求：

- [ ] 默认按 tenant/project 做公平调度。
- [ ] priority 不允许永久饿死低优先级任务。
- [ ] partition key 进入 Task metadata。
- [ ] worker 可声明 resource class。
- [ ] 测试覆盖多租户任务隔离。

## 8. Streaming 生产加固

要求：

- [ ] 每个 stream event 有 `sequence` 和 `event_id`。
- [ ] `event_id = run_id + sequence` 或等价稳定格式。
- [ ] 支持 `Last-Event-ID` 断线续传。
- [ ] Replay Buffer 使用 Redis Stream 或 Postgres event log。
- [ ] 最近 N 条或最近 T 分钟可 replay。
- [ ] 多 API Server 通过 Redis Stream / PubSub fan-out。
- [ ] 慢消费者断开或降级。
- [ ] 大 payload 存 Artifact Store，只 stream ref。

## 9. Worker 水平扩容

验收场景：

```text
启动 1 个 worker
积压 100 个 task
扩容到 3 个 worker
队列积压下降
没有重复 terminal result
没有 stale worker 覆盖结果
```

指标：

- [ ] queue depth。
- [ ] running task count。
- [ ] lease expired count。
- [ ] retry count。
- [ ] dead letter count。
- [ ] worker heartbeat age。

## 10. 测试要求

- [ ] Redis queue unit tests。
- [ ] worker integration tests。
- [ ] lease timeout / stale fencing tests。
- [ ] cancel pub/sub tests。
- [ ] quota tests。
- [ ] queue partition fairness tests。
- [ ] SSE reconnect / replay tests。
- [ ] backpressure tests。
- [ ] crash recovery tests。

命令：

```powershell
uv run pytest tests/runtime tests/streaming tests/worker -q
uv run ruff check .
uv run mypy apps/server tests scripts
docker compose up
```

## 11. 提交建议

```text
feat(runtime): harden production worker and streaming runtime
```

## 12. 设计回查清单

- [ ] Runtime 状态机没有被 API happy path 绕过。
- [ ] Worker 崩溃不会留下永久 stuck task。
- [ ] stale fencing token 无法写入 terminal result。
- [ ] cancel、retry、dead letter 对 API、Console、Event 都可见。
- [ ] Quota 不依赖前端判断。
- [ ] Streaming 支持断线重连和多实例 fan-out。
