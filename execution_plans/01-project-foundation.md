# 01 项目基础设施执行计划

> **给执行 Agent 的要求：** 使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 逐任务执行。每个任务必须有测试或可验证命令。

**目标：** 建立 DimooRun 的基础仓库结构、后端服务骨架、Worker 骨架、Console 骨架、配置模型、开发命令和基础验证链路。

**架构说明：** 本计划不实现复杂业务，只确定代码边界和工程规范。后续领域模型、Adapter、Runtime、治理、Console 都要落在这里建立的结构之上，避免后续重构项目骨架。

**设计覆盖：** `DESIGN_SPEC.md` 第 1-9、15-17、52、53、54 章。

**当前状态：** 已完成并推送到 `main`。落地提交：

```text
0c5bac0 chore: establish project foundation
```

**最终验证：**

```powershell
uv run pytest -q      # passed
npm run build         # passed
```

---

## 0. 实施前必读 DESIGN_SPEC 章节

- [x] 第 1 章：项目概述。
- [x] 第 2 章：项目定位。
- [x] 第 3 章：设计目标。
- [x] 第 4 章：非目标。
- [x] 第 5 章：核心边界。
- [x] 第 6 章：Design Guardrails。
- [x] 第 7 章：三层架构。
- [x] 第 8 章：总体架构。
- [x] 第 9 章：技术选型。
- [x] 第 15 章：Project Configuration。
- [x] 第 16 章：CLI / Developer Experience。
- [x] 第 17 章：Deployment Modes。
- [x] 第 52 章：代码结构建议。
- [x] 第 53 章：MVP 范围。
- [x] 第 54 章：Roadmap。

## 1. 实现边界

本计划负责：

- [x] Python 项目依赖和开发工具。
- [x] `apps/server` FastAPI 骨架。
- [x] `apps/worker` Worker 入口骨架。
- [x] `apps/console` Vue 入口骨架。
- [x] `dimoorun.yaml` / `manifest.yaml` 的文件位置预留。
- [x] `examples/` 示例目录。
- [x] `openapi/` 输出目录。
- [x] `deploy/` 部署目录。
- [x] README 与当前设计方向一致。

本计划不负责：

- [x] 真实数据库模型：不在本阶段，已进入 `02-domain-persistence-and-api.md`。
- [x] 真实 Adapter：不在本阶段，进入 `03-agent-package-and-adapters.md`。
- [x] 真实 Task Queue：不在本阶段，进入 `04-runtime-task-worker-streaming.md`。
- [x] 真实 Console 页面：不在本阶段，进入 `08-console-product-plan.md`。
- [x] Docker Compose 完整生产启动：不在本阶段，进入 `10-enterprise-ops-and-cloud-native.md`。

## 2. 目标目录结构

```text
apps/
  server/
    dimoo_run/
      __init__.py
      server.py
      api/
      core/
      persistence/
      runtime/
      scheduler/
      worker/
  worker/
    dimoo_run_worker/
      __init__.py
      main.py
  console/
    package.json
    index.html
    src/
      main.ts
      App.vue
examples/
  langgraph/
  compatibility/
execution_plans/
openapi/
deploy/
tests/
  server/
```

## 2.1 Worker 目录边界

本项目存在两个 Worker 相关位置，职责必须区分清楚：

```text
apps/server/dimoo_run/worker/
  Worker runtime library。
  放任务执行器、AgentInstance 缓存、heartbeat、执行上下文、worker 服务逻辑。

apps/worker/dimoo_run_worker/
  Worker process entrypoint。
  只负责读取配置、创建依赖、启动 worker loop。
  不放领域模型、不放核心调度逻辑、不放 Adapter 逻辑。
```

规则：

- [x] 所有可测试的 Worker 逻辑放 `apps/server/dimoo_run/worker/`。
- [x] `apps/worker/dimoo_run_worker/main.py` 保持薄入口。
- [x] 后续 Docker worker image 运行 `apps/worker/dimoo_run_worker/main.py`。
- [x] API server 和 Worker 共享同一套 domain/runtime/scheduler library。

## 3. 依赖规划

Python 基础依赖：

```text
fastapi
pydantic
uvicorn[standard]
```

开发依赖：

```text
pytest
pytest-asyncio
httpx
ruff
mypy
```

后续计划会继续加入：

```text
sqlalchemy
alembic
asyncpg
aiosqlite
redis
typer
pyyaml
langgraph
langchain
langchain-core
langsmith
deepagents
opentelemetry
```

LangChain 生态依赖策略：

- [x] 不在基础骨架阶段固定安装 LangGraph / LangChain / DeepAgents。
- [x] 到 `03-agent-package-and-adapters.md` 实施时按 `DESIGN_SPEC.md` 第 9.4 章使用固定测试基线。
- [x] 示例 README 可以说明版本策略，但不写过期版本号作为唯一真相。

前端基础依赖：

```text
vue
vite
typescript
vue-router
pinia
naive-ui
echarts
```

## 4. 任务拆分

### Task 1：更新 Python 工程配置

修改 `pyproject.toml`：

- [x] 保留项目名 `dimoorun`。
- [x] Python 版本保持 `>=3.11`。
- [x] 增加 FastAPI / Pydantic / Uvicorn。
- [x] 增加 dev dependency group。
- [x] 设置 pytest 的 `pythonpath = ["apps/server"]`。
- [x] 设置 ruff、mypy 基础配置。

验收命令：

```powershell
uv lock
uv run python --version
uv run pytest -q
```

验收标准：

```text
uv lock 成功。
pytest 至少能发现并运行基础测试。
```

### Task 2：创建 FastAPI Server 骨架

创建文件：

```text
apps/server/dimoo_run/__init__.py
apps/server/dimoo_run/server.py
apps/server/dimoo_run/api/router.py
apps/server/dimoo_run/core/health.py
tests/server/test_health.py
```

`server.py` 必须提供：

```text
create_app()
app
/healthz
/openapi.json
```

`/healthz` 返回：

```json
{
  "status": "ok",
  "service": "dimoorun-server",
  "version": "0.1.0"
}
```

测试要求：

- [x] `TestClient(create_app()).get("/healthz")` 返回 200。
- [x] 返回体字段完整。
- [x] OpenAPI title 是 `DimooRun API`。

验收命令：

```powershell
uv run pytest tests/server/test_health.py -q
```

### Task 3：创建配置模型

创建文件：

```text
apps/server/dimoo_run/core/config.py
tests/server/test_config.py
```

配置对象：

```text
Settings
RuntimeConfig
DatabaseConfig
RedisConfig
ConsoleConfig
ObservabilityConfig
```

默认值：

```text
runtime.mode = dev
runtime.environment = local
database.url = sqlite+aiosqlite:///./data/dimoorun.db
redis.url = redis://localhost:6379/0
console.enabled = true
observability.tracing = false
```

测试要求：

- [x] 默认配置是 Dev Mode。
- [x] mode 只能是 `dev | production | enterprise`。
- [x] environment 默认 `local`。

### Task 4：创建 Worker 入口骨架

创建文件：

```text
apps/worker/dimoo_run_worker/__init__.py
apps/worker/dimoo_run_worker/main.py
```

Worker 当前只做进程入口，不执行任务。

命令：

```powershell
uv run python apps/worker/dimoo_run_worker/main.py
```

期望输出：

```text
DimooRun worker process ready
```

### Task 5：创建 Console 入口骨架

创建文件：

```text
apps/console/package.json
apps/console/index.html
apps/console/src/main.ts
apps/console/src/App.vue
```

Console 首屏只显示：

```text
DimooRun Console
Runtime Control Plane
```

样式要求：

- [x] 不做营销页。
- [x] 不做低代码画布。
- [x] 使用控制台风格基础布局。
- [x] 使用克制的浅色背景和清晰文字。

验收命令：

```powershell
cd apps/console
npm install
npm run build
```

如果当前环境没有 Node，可以只提交文件并在最终说明中标记未运行前端 build。

### Task 6：创建示例目录

创建：

```text
examples/langgraph/README.md
examples/compatibility/README.md
```

`examples/langgraph/README.md` 说明：

```text
这里放 LangGraph Agent 示例。
示例必须覆盖 invoke、stream、thread_id、checkpoint、interrupt/resume。
```

`examples/compatibility/README.md` 说明：

```text
这里放 LangGraph Compatibility API 示例。
示例必须覆盖 assistants、threads、runs、stream。
```

### Task 7：更新 README

README 必须与当前设计保持一致：

- [x] 早期 Adapter 范围只写 LangGraph、LangChain Agent、DeepAgents。
- [x] 删除 HTTP Agent、CrewAI、LlamaIndex 等早期承诺。
- [x] 增加 `execution_plans/` 目录说明。
- [x] 保留“业务黑盒，运行白盒”。
- [x] 明确项目当前仍处于设计和初始化阶段。

## 5. 验收清单

- [x] `uv run pytest -q` 通过。
- [x] `uv run python main.py` 仍输出 `Hello from dimoorun!`。
- [x] `/healthz` 测试通过。
- [x] `execution_plans/` 已在 README 中说明。
- [x] README 与 `DESIGN_SPEC.md` 的 Adapter 范围一致。
- [x] 仓库结构符合后续计划预期。
- [x] `npm run build` 通过。

## 6. 提交建议

已落地提交：

```text
0c5bac0 chore: establish project foundation
```

提交前检查：

```powershell
git status --short
uv run pytest -q
```

## 7. 设计回查清单

- [x] README 的定位与第 2 章一致，没有把项目写成 Builder。
- [x] README 的 Adapter 范围与第 10.3 章一致，只写 LangGraph / LangChain Agent / DeepAgents。
- [x] 目录结构与第 52 章一致，后续计划有明确落点。
- [x] Dev Mode 默认配置与第 17.1 章一致。
- [x] MVP 骨架没有提前实现第 53.3 章列为暂缓的复杂能力。

## 8. 后续进入 02 / 03 前的注意事项

- `01` 只建立工程骨架，不承诺真实 Runtime 能力。
- `02-domain-persistence-and-api.md` 已在该骨架上完成领域模型、迁移、Repository 和 API contract。
- `03-agent-package-and-adapters.md` 可以继续复用当前 server / worker / examples 目录边界。
