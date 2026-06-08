# Console Core Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the MVP Console workflow so an operator can register an Agent, create an AgentVersion, create an async Task, and inspect the resulting Run/Task/Event records.

**Architecture:** Keep the current Vue Console structure and typed Native API client boundary. Add the missing AgentVersion and Task creation calls to the generated client and expose them through `consoleClient`; add a compact core-flow panel to `AgentsPage.vue` instead of introducing a larger Agent detail subsystem in this pass.

**Tech Stack:** Vue 3, TypeScript, Vite, existing Console contract tests, FastAPI Native API, SQLAlchemy runtime.

**Execution Status (2026-06-01):** Implemented. Console contract tests, Console production build, and focused Native API smoke test passed.

---

## Current Gap

`docs/reference/design-spec.md` defines the MVP minimum loop as:

```text
Register Agent -> Create AgentVersion -> Create Task -> Worker executes -> Console views Run/Task/Event
```

The backend supports the loop through Native API endpoints, and the Console can inspect Runs, Tasks, Events, Attempts, and Replay. The remaining Console gap is that users cannot create an AgentVersion or submit a Task from the UI; they currently need API calls outside the browser.

## File Structure

- Modify `apps/console/tests/console-contract.test.mjs`
  - Add a static contract test that the Console exposes AgentVersion creation and Task submission from the Agents page through `consoleClient`.
- Modify `apps/console/src/api/generated/dimoorun.ts`
  - Add `NativeAgentVersionRead`.
  - Add `createAgentVersion`, `listAgentVersions`, and a payload-capable `createTask`.
- Modify `apps/console/src/api/types.ts`
  - Add `AgentVersion` and `TaskCreateResult`.
- Modify `apps/console/src/api/client.ts`
  - Map native AgentVersion records.
  - Add demo/live `createAgentVersion`, `listAgentVersions`, and `createTask`.
- Modify `apps/console/src/pages/agents/AgentsPage.vue`
  - Add selected-Agent state, AgentVersion form, Task JSON input, error handling, and a Run link after Task creation.
- Modify `apps/console/src/i18n/messages.ts`
  - Add concise Chinese and English labels for the core flow panel.
- Update `docs/history/implementation-update-2026-06-01.md`
  - Record that the Console core flow is implemented and how it maps to the design MVP loop.

## Task 1: Console Contract For Core Flow

**Files:**
- Modify: `apps/console/tests/console-contract.test.mjs`

- [ ] **Step 1: Write the failing contract test**

Add a test named `exposes the MVP agent run flow from the Console` that checks:

```javascript
assert.match(generatedClient, /createAgentVersion/);
assert.match(generatedClient, /listAgentVersions/);
assert.match(generatedClient, /createTask/);
assert.match(consoleClient, /createAgentVersion/);
assert.match(consoleClient, /listAgentVersions/);
assert.match(consoleClient, /createTask/);
assert.match(agentsPage, /versionForm/);
assert.match(agentsPage, /taskInputJson/);
assert.match(agentsPage, /submitTask/);
assert.match(agentsPage, /ResourceLink/);
```

- [ ] **Step 2: Run Console tests to verify RED**

Run:

```powershell
npm run test
```

Expected: FAIL because the Agents page and client do not expose the full core flow yet.

## Task 2: Typed Client Boundary

**Files:**
- Modify: `apps/console/src/api/generated/dimoorun.ts`
- Modify: `apps/console/src/api/types.ts`
- Modify: `apps/console/src/api/client.ts`

- [ ] **Step 1: Add generated Native API methods**

Add `NativeAgentVersionRead`, `createAgentVersion`, `listAgentVersions`, and change `createTask` to accept a payload containing `input`, optional `version`, and optional `thread_id`.

- [ ] **Step 2: Add Console domain methods**

Add `AgentVersion`, `TaskCreateResult`, `mapNativeAgentVersion`, and demo/live client methods:

```ts
listAgentVersions(agentId)
createAgentVersion(agentId, payload)
createTask(agentId, payload)
```

- [ ] **Step 3: Run Console tests**

Run:

```powershell
npm run test
```

Expected: still FAIL until the Agents page exposes the UI state and actions.

## Task 3: Agents Page Core Flow Panel

**Files:**
- Modify: `apps/console/src/pages/agents/AgentsPage.vue`
- Modify: `apps/console/src/i18n/messages.ts`

- [ ] **Step 1: Add Agent selection**

Each row gets a Select button. Selecting an Agent loads its versions and enables the core-flow panel.

- [ ] **Step 2: Add AgentVersion form**

The panel includes inputs for:

```text
version
package_uri
adapter
framework
entrypoint
```

Submitting creates an AgentVersion and refreshes the version list.

- [ ] **Step 3: Add Task form**

The panel includes a JSON textarea for task input and an optional version selector. Submitting creates a Task and displays links to the created Run and Task.

- [ ] **Step 4: Run Console tests and build**

Run:

```powershell
npm run test
npm run build
```

Expected: PASS.

## Verification Gate

Run:

```powershell
cd apps/console
npm run test
npm run build
```

Run backend smoke tests for the endpoints the Console uses:

```powershell
uv run pytest tests/api/test_native_api.py::test_native_agent_task_run_event_flow_is_real -q
```

Expected: all commands pass.

## Self-Review

- Scope is limited to the MVP frontend loop. Full Agent detail pages, version diffing, package upload, deployment promotion, and rich manifest editing remain future work.
- No backend API behavior is required for this pass because the Native API already exposes AgentVersion and Task endpoints.
- The UI uses existing form styles and avoids new design-system dependencies.
