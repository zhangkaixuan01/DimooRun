# 04 Runtime、Task、Worker 与 Streaming 执行计划

> **给执行 Agent 的要求：** 运行时计划必须按状态机和任务租约实现，不能把 Agent 执行做成简单 HTTP 调用。

**目标：** 实现 Run / Task / RunAttempt 状态机、Task Scheduler、Worker Pool、lease / heartbeat / retry / dead letter、fencing token、Streaming Runtime、CheckpointIndex、Scheduled / Batch / Replay Runtime。

**架构说明：** API 创建 Run 和 Task；Worker lease Task，创建 RunAttempt，加载 AgentInstance，执行 Adapter，写 Event / Artifact / Trace，最后完成或重试 Task。Streaming Runtime 基于有序事件，而不是普通 HTTP chunk。

**设计覆盖：** `DESIGN_SPEC.md` 第 20、21、29、30、40、41、42 章。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [ ] 第 20 章：Event Model。
- [ ] 第 21 章：Streaming Runtime。
- [ ] 第 29 章：Runtime State Machines。
- [ ] 第 30 章：Checkpoint Boundary。
- [ ] 第 40 章：Task Scheduler。
- [ ] 第 41 章：Worker Pool。
- [ ] 第 42 章：HA / Scaling Design。
- [ ] 第 53.2 章：Runtime MVP 必须包含。

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
apps/server/dimoo_run/worker/heartbeat.py
apps/server/dimoo_run/streaming/events.py
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

- [ ] `InMemoryTaskBackend` 用于 Dev Mode。
- [ ] `RedisTaskBackend` 用于 Runtime MVP。

生产级机制：

- [ ] lease。
- [ ] heartbeat。
- [ ] lease timeout。
- [ ] retry。
- [ ] exponential backoff。
- [ ] dead letter。
- [ ] idempotency key。
- [ ] queue priority。
- [ ] scheduled_at。
- [ ] tenant/project/agent concurrency quota 预留。

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

测试：

- [ ] 同一个 idempotency key 返回同一个业务结果。
- [ ] 不同 endpoint 的 idempotency key 不冲突。
- [ ] paused / draining / stopped Deployment 拒绝新 Run。

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

- [ ] task cancel。
- [ ] run timeout。
- [ ] adapter load failure。
- [ ] agent execution failure。
- [ ] stream failure。
- [ ] heartbeat failure。
- [ ] worker lost。
- [ ] retry exhausted。
- [ ] dead letter。

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

- [ ] 每次 lease 生成递增 `fencing_token`。
- [ ] Task 终态写入必须带 `task_id + attempt_id + fencing_token`。
- [ ] 使用 compare-and-set。
- [ ] stale token 写入返回 `stale_fencing_token`。

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

Backpressure：

- [ ] 限制单 Run stream buffer 大小。
- [ ] 慢消费者断开或降级。
- [ ] 大 payload 进入 Artifact Store，只 stream ref。

终止语义：

```text
stream.completed
stream.cancelled
stream.failed
stream.timeout
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

- [ ] Run 状态以 DimooRun 为准。
- [ ] 框架 checkpoint 是恢复输入。
- [ ] checkpoint payload 由 Framework Runtime Store 负责。
- [ ] checkpoint 恢复受 Adapter capability 限制。

## 9. Scheduled / Batch / Replay Runtime

对象：

```text
ScheduledRun
BatchRun
ReplayJob
```

规则：

- [ ] ScheduledRun 最终展开为 Run / Task。
- [ ] BatchRun 每个 item 展开为 Run / Task。
- [ ] ReplayJob 创建新 Run，不修改历史 Run。
- [ ] replay 可以选择 baseline / candidate AgentVersion。
- [ ] batch 和 replay 受 tenant/project/agent concurrency quota 限制。
- [ ] cron 调度失败、跳过、补跑都写 AuditLog。

## 10. 验收清单

- [ ] 状态机非法流转会失败。
- [ ] Task lease / heartbeat / retry / dead letter 测试通过。
- [ ] stale fencing token 无法写终态。
- [ ] SSE event 有 sequence 和 event_id。
- [ ] Last-Event-ID 可恢复 stream。
- [ ] Worker 可以执行 fake Adapter。
- [ ] Worker 崩溃后 Task 可见恢复或失败。
- [ ] ReplayJob 创建新 Run。

验收命令：

```powershell
uv run pytest tests/runtime tests/scheduler tests/streaming -q
```

## 11. 提交建议

```text
feat: add runtime task worker and streaming
```

## 12. 设计回查清单

- [ ] Event 类型覆盖第 20 章通用事件与框架特定事件边界。
- [ ] SSE、sequence、event_id、Last-Event-ID、Replay Buffer、Backpressure 覆盖第 21 章。
- [ ] Run / Task / RunAttempt 状态机与第 29 章一致。
- [ ] 幂等规则与第 29.5 章一致。
- [ ] TaskBackend 接口与第 40.2 章一致。
- [ ] Worker 职责覆盖第 41 章。
- [ ] lease、heartbeat、retry、dead letter、fencing token 覆盖第 42 章。
