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

当前 11 阶段进度：

- [x] 已新增 `SQLAlchemyTaskBackend`，对齐 in-memory backend 的 enqueue、lease、heartbeat、complete、fail、cancel、requeue expired、fencing token 语义。
- [x] durable task lease 会按 priority / created_at 选择 queued task，并递增 fencing token。
- [x] durable heartbeat、complete、fail 均校验 worker ownership 和 fencing token。
- [x] durable fail 支持 retry / dead letter，并记录 dead letter reason。
- [x] `WorkerLoop` 可选接入 task backend，`run_once` 能 lease durable task 并推进到 running。
- [x] 新增 SQLAlchemy scheduler 和 worker loop durable backend 测试。
- [x] 已新增 `SQLAlchemyRunStore`，WorkerExecutor 可将 Run / RunAttempt / Task 推进到 durable succeeded 状态。
- [x] WorkerExecutor 在事件 append 和 terminal result 写入前校验 active fencing token。
- [x] RedisTaskBackend 已从占位改为可测 command mapping，覆盖 enqueue、lease、heartbeat、complete、fail、cancel、reap expired、retry、dead letter 和 fencing token。
- [x] RedisTaskBackend cancel 会向 `dimoorun:cancel` channel 发布跨实例 cancel message。
- [x] 已新增 SQLAlchemy quota policy，durable queue 可在 lease 前按 tenant/project running task 限制阻塞任务。
- [x] quota durable lease 已覆盖 tenant/project/agent/deployment，并验证 terminal state 后释放。
- [x] SQLAlchemy durable queue 会跳过 quota-blocked partition，并按 tenant/project active count 做基础公平 lease。
- [x] 已新增 StreamFanOutHub，支持按 run fan-out，并在 subscriber buffer 超限时断开慢消费者。
- [x] 已新增 RedisStreamFanOutBridge，event 同时写 Redis Stream replay 边界并 publish 到跨实例 fan-out channel。
- [x] lease reaper 可将 expired running task 按 max_attempts requeue 或 dead_letter，避免永久 stuck。
- [x] lease reaper 会写 `task.lease_expired` / `task.dead_letter` runtime event。
- [x] WorkerExecutor 支持 `timeout_seconds` / `timeout`，并将 attempt/run/task 推进到 timeout/dead_letter 边界。
- [x] Task API 会返回 `error` 与 `dead_letter_reason`，dead-letter 对 API/Console 数据面可见。
- [x] 已新增 SQLAlchemy scheduler metrics snapshot，覆盖 queue depth、running、expired lease、retry、dead-letter。

必须完成：

- [x] Redis Queue 支持 lease、heartbeat、retry、dead letter 的命令映射。
- [x] SQLAlchemy durable queue 支持 lease、heartbeat、retry、dead letter。
- [x] SQLAlchemy lease reaper 基础实现。
- [x] fencing token 跨 worker 写入保护的 durable task 边界。
- [x] Redis pub/sub cancel 广播边界。
- [x] Task timeout / Run timeout。
- [x] worker crash recovery 的 expired lease requeue / dead_letter 基础边界。
- [x] worker horizontal scaling 验证。
- [x] tenant / project concurrency quota 的 durable lease 边界。
- [x] agent concurrency quota。
- [x] queue partition。
- [x] streaming replay buffer 基础实现。
- [x] 进程内 event fan-out 基础边界。
- [x] cross-instance event fan-out 完整读写闭环。
- [x] stream backpressure 基础边界。

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

- [x] 每次 lease 生成递增 fencing token。
- [x] complete / fail 必须校验 task ownership 和 fencing token。
- [x] event append 写入前校验 task ownership 和 fencing token。
- [x] lease timeout 后旧 worker 写入结果必须被拒绝。
- [x] retry 必须记录 attempt number 和 retry reason。
- [x] 超过 max_attempts 进入 dead letter。
- [x] dead letter 对 Console 和 API 可见。

## 3. Lease Reaper

要求：

- [x] 扫描 expired leased / running task。
- [x] 根据 task 状态 requeue。
- [x] 根据 task 状态 terminal fail / dead_letter。
- [x] 写 AuditLog 或 runtime event。
- [x] 支持单实例运行。
- [x] 多实例下不重复 requeue。
- [x] reaper 自身有 heartbeat。

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

- [x] Task lease token 存 durable state。
- [x] WorkerExecutor 写 Run / Task / Event 前校验 token。
- [x] stale token 返回 `stale_fencing_token`。
- [x] stale 写入要有测试覆盖。

## 5. Cancel 跨实例

要求：

- [x] API cancel 写 durable cancelled state 和 cancel event。
- [x] Redis pub/sub 广播 cancel。
- [x] worker loop 订阅 cancel channel。
- [x] Adapter 支持 cancel 时调用 Adapter cancel。
- [x] Adapter 不支持 cancel 时标记 best-effort cancel。
- [x] cancel event 对 stream 和 Console 可见。

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

- [x] quota 检查在 lease 前生效。
- [x] quota 检查在 enqueue 前生效。
- [x] 超限返回稳定错误码。
- [x] quota 释放必须和 terminal state 一致。
- [x] Console 能展示 quota blocking reason。
- [x] API Key / ServiceAccount 不能绕过 quota。

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

- [x] 默认按 tenant/project 做公平调度。
- [x] priority 不允许永久饿死低优先级任务。
- [x] partition key 进入 Task metadata。
- [x] worker 可声明 resource class。
- [x] 测试覆盖多租户任务隔离。

## 8. Streaming 生产加固

要求：

- [x] 每个 stream event 有 `sequence` 和 `event_id`。
- [x] `event_id = run_id + sequence` 或等价稳定格式。
- [x] 支持 `Last-Event-ID` 断线续传。
- [x] Replay Buffer 支持内存 N 条 replay，并新增 Redis Stream 写入边界。
- [x] 最近 N 条可 replay。
- [x] 多 API Server 通过 Redis Stream / PubSub fan-out 完整闭环。
- [x] 慢消费者断开或降级。
- [x] 大 payload stream ref 边界。

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

- [x] queue depth。
- [x] running task count。
- [x] lease expired count。
- [x] retry count。
- [x] dead letter count。
- [x] worker heartbeat age。

## 10. 测试要求

- [x] Redis queue unit tests。
- [x] SQLAlchemy durable queue unit tests。
- [x] worker loop durable backend integration test。
- [x] lease timeout / stale fencing tests。
- [x] cancel pub/sub tests。
- [x] quota tests。
- [x] queue partition fairness tests。
- [x] SSE reconnect / replay tests。
- [x] backpressure tests。
- [x] crash recovery tests。

命令：

```bash
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

- [x] Runtime 状态机没有被 API happy path 绕过。
- [x] Worker 崩溃不会留下永久 stuck task。
- [x] stale fencing token 无法写入 terminal result。
- [x] cancel、retry、dead letter 对 API、Console、Event 都可见。
- [x] Quota 不依赖前端判断。
- [x] Streaming 支持断线重连和多实例 fan-out。
