# 04 Runtime、Task、Worker 与 Streaming 执行计划

> **给执行 Agent 的要求：** 运行时计划必须按状态机和任务租约实现，不能把 Agent 执行做成简单 HTTP 调用。

**目标：** 实现 Run / Task / RunAttempt 状态机、Task Scheduler、Worker Pool、lease / heartbeat / retry / dead letter、fencing token、Streaming Runtime、CheckpointIndex、Scheduled / Batch / Replay Runtime。

**架构说明：** API 创建 Run 和 Task；Worker lease Task，创建 RunAttempt，加载 AgentInstance，执行 Adapter，写 Event / Artifact / Trace，最后完成或重试 Task。Streaming Runtime 基于有序事件，而不是普通 HTTP chunk。

**设计覆盖：** `DESIGN_SPEC.md` 第 20、21、29、30、40、41、42 章。

**当前状态：** 已完成 Dev/MVP contract-level 基础实现。当前实现提供内存版 RunStore、RunStore Protocol、InMemoryTaskBackend、WorkerExecutor fake-adapter invoke / stream 执行闭环、ReplayBuffer、SSE event encoding、CheckpointIndexStore 和 ReplayScheduler scaffold。Redis 队列命令映射、Postgres Event Store、真实 SSE API、Native Runtime API 路由接线、长驻 worker process loop、完整 Scheduled / Batch Runtime 和生产级 quota / partition / pubsub cancel 保留到后续生产化阶段。

**本阶段完成内容：**

- Run / Task / RunAttempt 状态机和非法流转校验。
- `IdempotencyStore`，按 `tenant_id + project_id + endpoint + idempotency_key` 去重。
- `TaskBackend` / `RuntimeTaskBackend` Protocol。
- `InMemoryTaskBackend`：enqueue、lease、heartbeat、complete、fail、cancel。
- lease timeout reaper。
- retry / dead letter。
- fencing token stale write 拒绝。
- `ReplayBuffer`：sequence、event_id、Last-Event-ID replay、replay expired、payload ref 降级。
- SSE event encoding。
- `CheckpointIndexStore`，只索引 checkpoint metadata，不解析 payload。
- `ReplayScheduler` scaffold：ReplayJob 语义创建新 Run / Task，不修改历史 Run。
- `WorkerExecutor`：lease task、创建 attempt、构建 RuntimeContext、执行 Adapter invoke / stream、增量写 replay event、应用 task override_config 到 Adapter runtime_config、完成或失败 Task。
- DB 模型和 migration 增加 `tasks.fencing_token`、`events.sequence`、`events.event_id`，`events.sequence` 和 `events.event_id` 为必填，并约束同一 Run 内 `sequence` 唯一。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 20 章：Event Model。
- [x] 第 21 章：Streaming Runtime。
- [x] 第 29 章：Runtime State Machines。
- [x] 第 30 章：Checkpoint Boundary。
- [x] 第 40 章：Task Scheduler。
- [x] 第 41 章：Worker Pool。
- [x] 第 42 章：HA / Scaling Design。
- [x] 第 53.2 章：Runtime MVP 必须包含。

## 1. 文件规划

```text
apps/server/dimoo_run/runtime/state_machine.py
apps/server/dimoo_run/runtime/run_manager.py
apps/server/dimoo_run/runtime/idempotency.py
apps/server/dimoo_run/scheduler/backend.py
apps/server/dimoo_run/scheduler/in_memory.py
apps/server/dimoo_run/scheduler/redis_backend.py
apps/server/dimoo_run/scheduler/reaper.py
apps/server/dimoo_run/worker/executor.py
apps/server/dimoo_run/streaming/sse.py
apps/server/dimoo_run/streaming/replay_buffer.py
apps/server/dimoo_run/checkpoints/index.py
apps/server/dimoo_run/replay/scheduler.py
tests/runtime/
tests/scheduler/
tests/streaming/
```

## 2. 状态机

Run 合法流转：

```text
pending -> running
running -> interrupted
running -> succeeded
running -> failed
running -> cancelled
running -> timeout
interrupted -> running
interrupted -> cancelled
```

Task 合法流转：

```text
queued -> leased
leased -> running
leased -> queued       # lease expired
running -> succeeded
running -> failed
running -> retrying
running -> cancelled
running -> dead_letter
retrying -> queued
```

RunAttempt 合法流转：

```text
running -> succeeded
running -> failed
running -> timeout
running -> cancelled
running -> worker_lost
```

Interrupt / Resume：

```text
running -> interrupted
interrupted + resume payload -> running
resume 必须校验 capability、权限、thread_id、checkpoint_id、resume schema
resume 创建新的 RunAttempt 或恢复原框架线程，由 Adapter 决定
```

## 3. TaskBackend 接口

必须实现：

```python
class TaskBackend(Protocol):
    async def enqueue(self, task: dict) -> str: ...
    async def lease(self, queue: str, worker_id: str, lease_seconds: int) -> dict | None: ...
    async def heartbeat(self, task_id: str, worker_id: str) -> None: ...
    async def complete(self, task_id: str, worker_id: str) -> None: ...
    async def fail(self, task_id: str, worker_id: str, error: dict) -> None: ...
    async def cancel(self, task_id: str) -> None: ...
```

实现：

- [x] `InMemoryTaskBackend` 用于 Dev Mode。
- [x] `RedisTaskBackend` 文件和可选依赖边界已建立；命令映射保留到生产化阶段。
- [x] `RunStore` 已抽象为 Protocol，当前内存实现只作为 Dev/MVP 存储。
- [x] TaskBackend 状态变更统一复用 `assert_task_transition`，避免绕过状态机。

生产级机制：

- [x] lease。
- [x] heartbeat。
- [x] lease timeout。
- [x] retry。
- [x] exponential backoff 保留为生产化策略项，本阶段完成 retry / dead letter 基础语义。
- [x] dead letter。
- [x] idempotency key。
- [x] queue priority。
- [x] scheduled_at。
- [x] tenant/project/agent concurrency quota 预留为后续生产化策略项。

## 4. Run Manager 流程

创建 Run / Task：

```text
HTTP request
  ↓
Validate auth / permission / quota
  ↓
Check idempotency
  ↓
Check Deployment desired_status accepts new Run
  ↓
Create Run
  ↓
Create Task
  ↓
Enqueue
  ↓
Return Run / Task response
```

幂等规则：

```text
tenant_id + project_id + endpoint + idempotency_key
```

冲突规则：

```text
同一 scope + idempotency_key 的 request_hash 必须一致。
request_hash 不一致时返回 idempotency_key_conflict，不 replay 旧结果。
```

测试：

- [x] 同一个 idempotency key 返回同一个业务结果。
- [x] 不同 endpoint 的 idempotency key 不冲突。
- [x] 同一个 idempotency key 携带不同 request_hash 会返回 `idempotency_key_conflict`。
- [x] paused / draining / stopped Deployment 拒绝新 Run 保留到 `05-deployment-runtime-control.md`，因为 Deployment runtime control 尚未实现。

## 5. Worker 执行流程

```text
Worker leases task
  ↓
Create RunAttempt
  ↓
Load Deployment / AgentVersion
  ↓
Check Adapter compatibility
  ↓
Load or reuse AgentInstance
  ↓
Build RuntimeContext
  ↓
Adapter.invoke / Adapter.stream
  ↓
Map AgentEvent -> Event
  ↓
Write Artifact / CheckpointIndex / ModelUsageSnapshot
  ↓
Complete Run / Task
```

Worker 必须处理：

- [x] task cancel 在 TaskBackend 层提供状态接口；API / pubsub cancel 进入 `05` / 生产化阶段。
- [x] run timeout 保留到 Worker 超时策略阶段。
- [x] adapter load failure 通过 Worker failure path 进入 retry / dead letter。
- [x] agent execution failure 通过 Worker failure path 进入 retry / dead letter。
- [x] Worker 支持 `execution_mode=invoke|stream`，stream 模式会消费 Adapter stream event 并增量写入 ReplayBuffer，不等 stream 完成后批量落库。
- [x] Worker 成功路径先校验 task ownership / fencing，再写 Run / Attempt 成功和终态事件，最后完成 Task，避免 Run 持久化失败后 Task 先进入 succeeded。
- [x] stream failure 通过 Worker failure path 进入 retry / dead letter；可重试失败只写 `attempt.failed` 和 `task.retrying`，不提前写 `run.failed` / `stream.failed`。
- [x] heartbeat failure 通过 heartbeat lease owner 校验暴露。
- [x] worker lost 通过 lease timeout + reaper 可见恢复。
- [x] retry exhausted。
- [x] dead letter。

## 6. Fencing Token

规则：

```text
Worker A lease task，token=1
Worker A 卡住，lease 过期
Worker B 重新 lease，token=2
Worker A 恢复后尝试写结果
系统发现 token=1 过期，拒绝写入
```

实现要求：

- [x] 每次 lease 生成递增 `fencing_token`。
- [x] Task 终态写入必须带 `task_id + worker_id + fencing_token`；持久化 attempt_id compare-and-set 进入 DB repository 阶段。
- [x] 使用内存 compare-and-set。
- [x] stale token 写入返回 `stale_fencing_token`。

## 7. Streaming Runtime

传输协议：

```text
SSE：默认，用于浏览器、Console、普通 API stream。
WebSocket：可选，用于双向控制、交互式会话、实时取消。
```

事件规则：

```text
sequence 每个 run 从 1 递增
event_id = run_id + ":" + sequence
sequence / event_id 是 runtime event 必填字段
同一 run 内 sequence 必须唯一
事件先持久化，再发送
客户端断线后携带 Last-Event-ID
服务端从 event store / replay buffer 恢复
```

Replay Buffer：

```text
Redis Stream
Postgres Event log
最近 N 条
最近 T 分钟
```

`stream.replay_expired` 是传输层事件，不写入 Run 业务 timeline，使用 `visibility_level=transport`，并使用确定性 `event_id = run_id + ":replay-expired:" + last_sequence`，便于客户端去重。

Backpressure：

- [x] 限制单 Run stream buffer 大小。
- [x] 慢消费者断开或降级保留到真实 SSE API 阶段。
- [x] 大 payload 进入 Artifact Store，只 stream ref；当前以 `artifact://run_id/sequence` 引用形式表达。

终止语义：

```text
stream.completed
stream.cancelled
stream.failed
stream.timeout
```

终态写入规则：

```text
retryable failure:
  attempt.failed
  task.retrying
  Run 保持 running，等待下一次 attempt

retry exhausted / non-retryable failure:
  attempt.failed
  run.failed
  stream.failed
  Task 进入 dead_letter 或失败终态
```

## 8. Checkpoint Boundary

DimooRun 只索引 checkpoint，不解释业务 state。

CheckpointIndex 字段：

```text
run_id
thread_id
checkpoint_ns
checkpoint_id
payload_uri
created_at
```

规则：

- [x] Run 状态以 DimooRun 为准。
- [x] 框架 checkpoint 是恢复输入。
- [x] checkpoint payload 由 Framework Runtime Store 负责。
- [x] checkpoint 恢复受 Adapter capability 限制。

## 9. Scheduled / Batch / Replay Runtime

对象：

```text
ScheduledRun
BatchRun
ReplayJob
```

规则：

- [x] ScheduledRun 最终展开为 Run / Task 的对象边界保留，完整调度进入后续阶段。
- [x] BatchRun 每个 item 展开为 Run / Task 的对象边界保留，完整批处理进入后续阶段。
- [x] ReplayJob 创建新 Run，不修改历史 Run。
- [x] replay 可以选择 baseline / candidate AgentVersion；当前实现 candidate AgentVersion。
- [x] batch 和 replay 受 tenant/project/agent concurrency quota 限制保留到生产化策略项。
- [x] cron 调度失败、跳过、补跑写 AuditLog 保留到完整 Scheduled Runtime。

## 10. 验收清单

- [x] 状态机非法流转会失败。
- [x] Task lease / heartbeat / retry / dead letter 测试通过。
- [x] stale fencing token 无法写终态。
- [x] SSE event 有 sequence 和 event_id。
- [x] runtime event 的 sequence / event_id 在 DB schema 中为非空字段。
- [x] Last-Event-ID 可恢复 stream。
- [x] Worker 可以执行 fake Adapter。
- [x] Worker 可以执行 fake Adapter stream 模式并增量持久化 stream chunk。
- [x] Worker 崩溃后 Task 可见恢复或失败。
- [x] ReplayJob 创建新 Run，并将 override_config 传递到 task payload / Adapter runtime_config。

本阶段未完成且不得误读为已完成：

- Native Runtime API 路由接线仍在后续阶段；当前部分 API contract stub 仍可能返回 `501`。
- `apps/worker/dimoo_run_worker/main.py` 仍是 worker process entrypoint scaffold，尚未启动长驻 lease / heartbeat / execute loop。
- Redis / Postgres / Kafka / Temporal 等生产后端仍只完成边界或映射设计，生产实现进入后续生产化阶段。

验收命令：

```powershell
uv run pytest tests/runtime tests/scheduler tests/streaming -q
```

## 11. 提交建议

```text
feat: add runtime task worker and streaming
```

## 12. 设计回查清单

- [x] Event 类型覆盖第 20 章通用事件与框架特定事件边界。
- [x] SSE、sequence、event_id、Last-Event-ID、Replay Buffer、Backpressure 覆盖第 21 章。
- [x] Run / Task / RunAttempt 状态机与第 29 章一致。
- [x] Runtime store 和 TaskBackend 状态写入会复用状态机校验。
- [x] 幂等规则与第 29.5 章一致，并覆盖 request_hash 冲突。
- [x] TaskBackend / RuntimeTaskBackend 接口与第 40.2 章一致。
- [x] Worker 职责覆盖第 41 章。
- [x] lease、heartbeat、retry、dead letter、fencing token 覆盖第 42 章。
