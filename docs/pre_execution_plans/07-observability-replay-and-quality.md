# 07 可观测性、回放与质量闭环执行计划

> **给执行 Agent 的要求：** Event、Trace、AuditLog 是三本账，不能混用。Replay 不允许修改历史 Run。

**目标：** 实现 Event / Trace / Audit 三账本、Artifact Store、Run Graph、Debug / Replay、Dataset、Experiment、Evaluation、Feedback、Memory/Semantic Store 元数据、Notification / Alerting。

**架构说明：** Event 是运行事实，Trace 是调试链路，AuditLog 是合规审计。评估和回放建立在这些事实之上，为发布门禁和线上质量闭环提供数据。

**设计覆盖：** `DESIGN_SPEC.md` 第 33、34、35、36、37、47、49 章。

**当前状态：** Dev/MVP 契约层已完成。已落地 in-memory 观测、Artifact、Run Graph、Replay、Dataset、Evaluation、Semantic Store Provider、Notification / Incident 服务，以及对应领域模型和 Alembic 表字段硬化。当前实现已收紧递归脱敏、Artifact 读时 checksum 校验、Dataset scope 校验、Event sequence 要求、Run Graph edge 可持久化映射、Replay override_config 传递、Notification channel scope / status 校验和 Incident trigger value。生产级外部观测导出、持久对象存储、完整 Console 可视化、真实 Runtime 全链路接线进入后续阶段。

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 33 章：Artifact Store。
- [x] 第 34 章：Event / Trace / Audit 三账本模型。
- [x] 第 35 章：Run Graph and Execution Provenance。
- [x] 第 36 章：Dataset, Experiment, and Quality Loop。
- [x] 第 37 章：存储边界。
- [x] 第 47 章：可观测性。
- [x] 第 49 章：评估设计。

## 1. 文件规划

```text
apps/server/dimoo_run/observability/events.py
apps/server/dimoo_run/observability/traces.py
apps/server/dimoo_run/observability/metrics.py
apps/server/dimoo_run/observability/audit.py
apps/server/dimoo_run/artifacts/store.py
apps/server/dimoo_run/run_graph/projector.py
apps/server/dimoo_run/replay/service.py
apps/server/dimoo_run/datasets/service.py
apps/server/dimoo_run/evals/service.py
apps/server/dimoo_run/memory/providers.py
apps/server/dimoo_run/notifications/alerts.py
tests/observability/
tests/replay/
tests/evals/
```

## 2. Event / Trace / Audit 三账本

Event：

```text
描述 Agent 执行过程中发生了什么。
用于 Console Timeline。
关键状态变更不能采样。
payload 可存 Artifact ref。
```

Trace / Span：

```text
描述调用链、耗时、模型和工具链路。
用于调试和外部观测平台。
可采样。
可导出 OpenTelemetry、Langfuse、Phoenix。
```

AuditLog：

```text
描述谁做了什么治理动作。
用于合规和安全审计。
不能因为 Trace 采样丢失。
保留周期通常长于 Trace。
```

映射：

```text
framework event -> AgentEvent -> EventSink
callback span -> TraceSink
policy decision -> AuditLog
security violation -> Event + AuditLog
tool call -> Event + TraceSpan + optional AuditLog
model call -> Event + TraceSpan + ModelUsageSnapshot
```

## 3. EventSink / TraceSink

EventSink：

```text
PostgresEventSink
RedisStreamEventSink
KafkaEventSink interface
OpenTelemetryEventSink
LangfuseEventSink interface
PhoenixEventSink interface
```

事件必须记录：

```text
request_id
run_id
attempt_id
task_id
trace_id
tenant_id
project_id
user_id
agent_id
agent_version
framework
adapter
input_ref
output_ref
event
tool call
model usage
latency
cost
error
checkpoint
```

## 4. Metrics

必须提供：

```text
run_total
run_success_total
run_failed_total
run_timeout_total
run_cancelled_total
run_interrupted_total
task_queue_size
task_latency_seconds
run_latency_seconds
attempt_total
tool_call_total
tool_error_total
llm_token_total
llm_cost_total
checkpoint_total
worker_heartbeat_lag
```

## 5. 脱敏、采样、保留

策略：

```text
Redaction Policy
Visibility Policy
Retention Policy
Sampling Policy
PII Handling
```

要求：

- [ ] Console 展示前应用 visibility/redaction。
- [ ] 外部 Trace 导出前应用 redaction。
- [x] AuditLog 不采样。
- [x] Artifact 读取经过权限、tenant/project scope、checksum 和可见性策略。

## 6. Artifact Store

存储内容：

```text
input payload
output payload
stream transcript
tool result
model raw response
retrieved context
generated file
uploaded file
trace attachment
evaluation dataset
error dump
```

后端：

```text
local filesystem for dev
S3-compatible object storage
MinIO
cloud object storage
database blob only for small payloads
```

规则：

- [ ] Run.input_ref / Run.output_ref 指向 Artifact。
- [ ] Event.payload_ref 指向 Artifact。
- [x] 敏感 Artifact 读取有权限、范围校验、checksum 校验和访问审计；加密留给生产后端。
- [ ] retention 不早于仍被 AgentVersion / Deployment 引用的资产。

## 7. Run Graph

RunGraph 是观测投影，不是编排 DSL。

节点类型：

```text
model
tool
retriever
ranker
generator
router
human
custom
```

用途：

- [ ] Console 可视化执行结构。
- [x] Trace 调试。
- [x] Eval 分析。
- [x] 排障定位。

## 8. Debug / Replay

流程：

```text
选择失败 Run
  ↓
查看失败 event / trace / error
  ↓
创建 ReplayJob
  ↓
选择相同 AgentVersion 或 candidate AgentVersion
  ↓
可选 override config / model / prompt asset
  ↓
创建新的 Run
  ↓
对比 output / latency / cost / events / errors
  ↓
沉淀 DatasetItem 或创建 Experiment
```

规则：

- [x] replay 不修改历史 Run。
- [x] replay 不修改历史 Event。
- [x] replay 不覆盖历史 Artifact。
- [x] replay 产生新的 Run / Task，并将 override_config 传递给 Runtime task；Event 由后续 Runtime 接线生成。
- [ ] replay 受权限和配额限制。

## 9. Dataset / Experiment / Evaluation

对象：

```text
Dataset
DatasetItem
Experiment
ExperimentRun
EvaluationResult
Feedback
```

评估类型：

```text
success_rate
timeout_rate
retry_count
tool_error_rate
avg_latency
p95_latency
avg_token_cost
interruption_rate
schema validation
cost threshold
tool call count threshold
answer correctness
instruction following
tool selection accuracy
citation correctness
faithfulness
relevance
safety
```

Evaluator 接口：

```python
class Evaluator(Protocol):
    name: str

    async def evaluate(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        trace: dict[str, Any],
        expected: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
```

规则：

- [x] Dataset 可来自生产 Run 并执行递归脱敏和 Dataset scope 校验；权限检查留给 API / Policy 接线。
- [x] EvaluationResult 可作为 Deployment promotion 的输入。
- [x] Quality Gate 不修改 AgentVersion，只阻止或允许 promotion。

## 10. Memory / Semantic Store 边界

Store 类型：

```text
Platform Store
Framework Runtime Store
Agent Memory Store
Semantic Store Provider
Agent Business Store
```

Semantic Store Provider 字段：

```text
embedding_model
embedding_gateway_id nullable
connection_ref
retention_policy_id nullable
status
metadata
```

规则：

- [x] DimooRun 不理解 memory 的业务语义。
- [x] 平台保存 Semantic Store Provider 的权限、隔离、审计、retention、redaction 元数据边界。
- [ ] embedding 调用优先经过 Model Gateway。

## 11. Notification / Alerting

对象：

```text
NotificationChannel
AlertRule
IncidentEvent
```

告警：

```text
run_failed_rate_high
task_queue_backlog_high
worker_heartbeat_lag_high
model_cost_threshold_exceeded
budget_near_exhausted
human_task_timeout
policy_violation_detected
webhook_delivery_failed
backup_failed
```

规则：

- [x] 告警来源可追溯 Event、Metric、AuditLog 或 Backup/Restore 状态，并保留触发值。
- [x] 通知失败不影响 Runtime。
- [ ] 高风险安全事件进入 AuditLog。
- [ ] Console 展示 incident，但不替代 ITSM / Pager 系统。

## 12. 验收清单

- [ ] Run 执行后 Event Timeline 完整。
- [ ] Trace span tree 可查询。
- [x] AuditLog 不受采样影响。
- [x] Artifact 读写有 checksum。
- [x] ReplayJob 创建新 Run，并传递 override_config。
- [x] DatasetItem 可从失败 Run 沉淀。
- [x] ExperimentRun 生成 EvaluationResult。
- [x] AlertRule 可触发 IncidentEvent。

命令：

```bash
uv run pytest tests/observability tests/replay tests/evals -q
```

## 13. 提交建议

```text
feat: add observability replay and quality loop
```

## 14. 设计回查清单

- [x] Artifact 类型和访问规则覆盖第 33 章。
- [x] Event / Trace / AuditLog 三账本没有混用，符合第 34 章。
- [x] Run Graph 是观测投影，不是编排 DSL，符合第 35 章。
- [x] Dataset / Experiment / Quality Gate 覆盖第 36 章。
- [x] Store 边界符合第 37 章，不接管业务 memory。
- [ ] 指标、EventSink、脱敏、采样、保留覆盖第 47 章。
- [x] Evaluator 接口和评估类型覆盖第 49 章。
