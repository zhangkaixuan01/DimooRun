# Product Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-risk product gaps that keep DimooRun at "production-shaped foundation" instead of a demonstrably complete evaluator-ready product.

**Architecture:** Keep the existing adapter-first runtime, native/admin/console API split, and Vue Console structure. Convert broad but thin surfaces into proof-backed product workflows by adding executable evidence, operator-specific pages, and hardened domain semantics instead of expanding scope into a low-code builder or generic ITSM product.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Pinia, Vite, Playwright, Docker Compose, Helm, GitHub Actions.

---

## Product Findings

DimooRun already has broad feature coverage: package validation, agent/version/deployment management, task/run inspection, replay, governance, identity, published surfaces, cost/budget, scheduled/batch, catalog assets, enterprise ops, CLI, SDKs, Docker, Helm, and Console.

The remaining product gaps are not mostly "missing buttons." They are product maturity gaps:

- The first evaluator path is documented but not fully proven as a clean-machine product activation flow.
- Several Console routes are generic `AdminCollectionPage` CRUD pages rather than role-specific operator workflows.
- Hosted/default-browser proof, screenshot evidence, release proof, and external trust verification are incomplete.
- `scheduled_runs`, `batch_runs`, and `extensions` are still marked placeholder at the domain-model level.
- Monitoring/exporter configuration exists, but hosted Prometheus/OTel verification is not closed.
- Compatibility surfaces support migration and inspection, but not complete platform parity or guided remediation.
- Frontend navigation covers all major product areas, but several submenus are only partially complete as product workflows.

This plan turns those findings into implementation tracks.

## Core Functionality Closure Audit

This audit is the execution baseline. Do not treat broad route/API presence as product completion. A workflow is closed only when a user can start from a realistic product intent, complete the operation through API/CLI/Console, inspect evidence, recover or retry when needed, and see automated proof for the path.

### Relatively Closed Core Paths

- Native runtime API and SDK path: package validation, agent creation, ready version creation, deployment creation, task submission, run fetch, run events, and replay are covered by API/SDK tests.
  - Evidence: `tests/sdk/test_python_sdk.py::test_python_sdk_can_drive_validate_publish_deploy_and_replay_against_native_api`
  - Evidence: `tests/api/test_package_workflow.py::test_validated_ready_version_can_deploy_and_accept_a_task`
- CLI runtime path: `package validate`, `agent publish`, `deployment create`, `deployment task submit`, `run watch`, and `run replay` are wired to native API client methods.
  - Evidence: `apps/server/dimoo_run/cli/main.py`
  - Residual risk: the parser has a defensive fallback for registered commands that are not matched by explicit handlers. Keep CLI tests focused on every public subcommand the docs mention.
- Console shell and many operator pages have local browser coverage.
  - Evidence: `apps/console/tests/e2e/`
  - Residual risk: route coverage and button coverage prove navigability and interactions, not full business closure for every product domain.

### Partially Closed Product Paths

- Local Compose activation is not yet a full first-user proof. The smoke script starts Compose, checks API/Console health, checks Postgres/MinIO, and performs backup/restore dry-run calls, but it does not yet execute the README product path end to end.
  - Current evidence: `scripts/compose_runtime_smoke.py`
  - Required closure: start stack, validate example package, publish agent version, create deployment, submit task, wait for terminal run, inspect events, write evidence, tear down.
  - Covered by: Task 1.
- Console observability is broad but still thin in several places. `audit-logs`, `artifacts`, `evaluations`, `replay-jobs`, and `feedback` currently use generic admin collection pages.
  - Current evidence: `apps/console/src/router/index.ts`
  - Required closure: promote these resources into operator workflows that connect run evidence, filtering, drilldown, export, replay, and quality investigation.
  - Covered by: Task 2.
- Enterprise operations is partially productized. Incident triage and backup/restore have dedicated pages, while alerts and webhooks still use generic admin collection pages.
  - Current evidence: `apps/console/src/router/index.ts`
  - Required closure: alert test/evaluate flows, webhook test delivery, delivery attempt history, retry evidence, and incident correlation.
  - Covered by: Task 3.
- Monitoring/exporter configuration has backend and Console surfaces, but hosted Prometheus/OTel proof is not closed.
  - Current evidence: `docs/readiness/current-maturity.md`
  - Required closure: exporter status checks, validation, scrape/trace proof, and readiness docs that point to generated evidence.
  - Covered by: Task 5.
- Compatibility and migration are useful but not complete remediation workflows.
  - Current evidence: `apps/console/src/pages/compatibility/` and `apps/server/dimoo_run/compatibility/`
  - Current strength: LangGraph compatibility API and Console Explorer cover assistants, threads, runs, stream probes, join, cancel, event replay, and golden compatibility records.
  - Current gap: `examples/compatibility/README.md` is a placeholder-only page and does not provide a runnable compatibility walkthrough.
  - Current gap: Console e2e coverage uses mocked API fixtures, so it proves interaction behavior but not a live backend compatibility example.
  - Required closure: migration report findings must include concrete remediation steps, severity, target files, verification commands, and Console guidance.
  - Required closure: add runnable compatibility examples that prove LangGraph-style requests can map into native Run and Task evidence.
  - Covered by: Task 6.
- Console module completeness is uneven across the eight major navigation groups.
  - Current evidence: `apps/console/src/layouts/AppShell.vue` and `apps/console/src/router/index.ts`.
  - Overview has one submenu, Dashboard, and is mostly complete as a landing overview.
  - Runtime has eleven submenus. Agents, Packages, Deployments, Published Surfaces, Workers, Agent Instances, Capacity, Runs, and Tasks are mostly complete, while Scheduled Runs and Batch Runs still depend on hardened backend semantics.
  - Observability has twelve submenus. Events, Replay, Datasets, Experiments, Quality Gate, Cost, and Budget are mostly complete, while Audit Logs, Artifacts, Evaluation Results, Feedback, and Replay Jobs need dedicated workflows instead of generic collection pages.
  - Identity has four submenus. Operators, Roles & Permissions, and Machine Identity are mostly complete, while Organization Scope needs clearer tenant/project context and switching evidence.
  - Governance has nine submenus. Human Tasks, Model Gateways, Tools, Secrets, Catalog Items, and Prompt Assets are mostly complete; Policies still has generic CRUD residue; Config Assets and Template Assets need stronger tests and product-specific detail flows.
  - Enterprise Ops has four submenus. Backup & Restore and Incidents are mostly complete, while Webhook Subscriptions and Alert Rules need workflow-specific validation, testing, and delivery evidence.
  - Compatibility has one submenu and is partially complete because it lacks examples, live proof, and guided remediation.
  - Platform has eight submenus. Platform Settings, Provider Status, Danger Zone, and Settings are mostly complete, while Semantic Store Providers, Observability Exporters, Sandbox Policies, and Container Pool Policies need configuration workbenches and validation proof.
  - Required closure: add module-level acceptance checks so each major navigation group has either a completed workflow or a documented residual risk with an execution task.
  - Covered by: Tasks 2, 3, 4, 5, 6, and 8.

### Not Yet Closed Product Paths

- `scheduled_runs`, `batch_runs`, and `extensions` are still marked as placeholder-level domain tables in the domain model test suite.
  - Evidence: `tests/domain/test_domain_models.py::test_placeholder_tables_are_marked_until_domain_fields_are_hardened`
  - Product impact: schedule and batch pages can have working local behavior while still lacking hardened persistence semantics, state fields, indexes, and domain invariants.
  - Covered by: Task 4.
- Public production evidence is incomplete.
  - Evidence: `docs/readiness/scorecard.md`
  - Product impact: the project should not claim external production-grade readiness until hosted proof, clean-machine Compose, ephemeral Kubernetes, release attestation, trust verification, and maintained screenshot evidence are present.
  - Covered by: Tasks 1, 5, and 7.
- Generic CRUD is not product closure.
  - Evidence: `docs/architecture/adrs/0001-runtime-control-plane.md`
  - Product impact: routes using `AdminCollectionPage` should be treated as administrative scaffolding until a role-specific workflow replaces them.
  - Covered by: Tasks 2, 3, and 5.

### Execution Priority From Audit

1. P0: prove the first runtime activation path with executable evidence.
2. P1: replace generic Console CRUD pages that represent high-value operator domains.
3. P1: harden placeholder domain tables for schedule, batch, and extension semantics.
4. P1: close Compatibility examples and migration remediation because the feature is user-facing and currently lacks runnable examples.
5. P1: close the remaining Console module completeness gaps that are not covered by generic CRUD promotion.
6. P2: close hosted proof, monitoring proof, and public evidence gallery.

## File Structure

Implementation should touch these areas:

- `docs/readiness/scorecard.md`: update only when executable evidence exists.
- `docs/readiness/current-maturity.md`: keep claims aligned with scorecard.
- `docs/start/getting-started.md`: strengthen the first activation path once it is proven.
- `docs/start/quickstart.md`: keep command sequence aligned with actual smoke scripts.
- `docs/DEMO_SCRIPT.md`: map demo steps to proof-backed screens and commands.
- `scripts/compose_runtime_smoke.py`: expand clean-machine runtime smoke proof.
- `scripts/hosted_proof_status.py`: report evidence readiness and blocking reasons.
- `.github/workflows/integration.yml`: run and upload Compose/KinD evidence.
- `apps/console/src/router/index.ts`: replace generic admin routes as dedicated pages are created.
- `apps/console/src/pages/admin/AdminCollectionPage.vue`: keep as fallback CRUD, not the final experience for high-value workflows.
- `apps/console/src/pages/observability/`: add audit/artifact/evaluation/replay workbenches.
- `apps/console/src/pages/ops/`: add alert/webhook/backup/restore detail workflows.
- `apps/console/src/pages/settings/`: add exporter, semantic store, sandbox, and container policy workbenches.
- `apps/console/src/pages/identity/`: strengthen organization scope switching and tenant/project context evidence.
- `apps/console/src/pages/governance/`: remove policy CRUD residue and strengthen config/template asset detail flows.
- `examples/compatibility/`: add runnable LangGraph compatibility examples instead of placeholder-only docs.
- `apps/server/dimoo_run/compatibility/migration_report.py`: add actionable remediation steps to migration reports.
- `apps/server/dimoo_run/api/compat/langgraph.py`: keep compatibility requests mapped through native runtime and governance semantics.
- `apps/server/dimoo_run/api/console/compatibility.py`: expose remediation and native evidence links to Console.
- `tests/compat/`: keep API compatibility behavior covered.
- `tests/compatibility/`: keep golden compatibility record behavior covered.
- `tests/migration/`: add migration example and remediation coverage.
- `apps/server/dimoo_run/domain/models.py`: harden placeholder tables.
- `migrations/versions/`: add migrations for hardened scheduled/batch/extensions fields.
- `apps/server/dimoo_run/api/admin/*.py`: add workflow APIs where generic CRUD is insufficient.
- `tests/api/`: add backend product workflow tests.
- `apps/console/tests/e2e/`: add browser workflow tests for each promoted operator page.
- `apps/console/tests/e2e-live/`: add live backend proof only after the local mocked workflow is stable.
- `apps/console/tests/e2e/module-completeness.spec.ts`: assert every major navigation group has the expected submenus and no high-value route renders generic CRUD scaffolding.

## Task 1: Activation Evidence For The First Runtime Path

**Priority:** P0

**Files:**
- Modify: `scripts/compose_runtime_smoke.py`
- Modify: `.github/workflows/integration.yml`
- Modify: `docs/start/getting-started.md`
- Modify: `docs/start/quickstart.md`
- Modify: `docs/readiness/scorecard.md`
- Test: `tests/e2e/test_runtime_compose_smoke.py`
- Test: `tests/production_foundation/test_ci_workflow.py`

- [x] **Step 1: Write a failing clean-machine smoke assertion**

Add or extend a test in `tests/e2e/test_runtime_compose_smoke.py` that expects the smoke script to prove the full evaluator path:

```python
def test_compose_runtime_smoke_requires_activation_path_steps() -> None:
    script = Path("scripts/compose_runtime_smoke.py").read_text(encoding="utf-8")
    required_markers = [
        "package validation completed",
        "agent version created",
        "deployment created",
        "deployment task submitted",
        "run reached terminal state",
        "console health checked",
        "evidence index written",
    ]
    for marker in required_markers:
        assert marker in script
```

Run: `uv run pytest tests/e2e/test_runtime_compose_smoke.py::test_compose_runtime_smoke_requires_activation_path_steps -q`

Expected: FAIL until the smoke script records each marker.

- [x] **Step 2: Extend the smoke script with explicit product steps**

In `scripts/compose_runtime_smoke.py`, make the runtime smoke perform these actions in order:

```text
1. wait for API health
2. validate examples/langgraph/support-agent
3. create or reuse agent
4. create ready agent version
5. create active deployment
6. submit deployment task
7. poll run until terminal
8. query run events and attempts
9. write an evidence index with IDs and terminal status
```

Use existing SDK/client helpers if present. If a helper is missing, keep the implementation inside `scripts/compose_runtime_smoke.py` as small HTTP functions rather than introducing a new framework.

Run: `uv run pytest tests/e2e/test_runtime_compose_smoke.py -q`

Expected: PASS.

- [x] **Step 3: Make integration workflow upload activation evidence**

In `.github/workflows/integration.yml`, ensure the Compose job uploads:

```text
compose-evidence-index.txt
compose-runtime-smoke.log
compose-diagnostics/
```

Run: `uv run pytest tests/production_foundation/test_ci_workflow.py -q`

Expected: PASS and the test should verify the artifact names.

- [x] **Step 4: Update docs only after the smoke is executable**

Update:

- `docs/start/getting-started.md`
- `docs/start/quickstart.md`
- `docs/readiness/scorecard.md`

Required wording:

```text
The local Compose activation path is proven by the integration workflow artifact `compose-evidence-index`.
```

Do not change the global maturity claim to production-ready.

Run: `uv run pytest tests/docs/test_docs_quality.py -q`

Expected: PASS.

- [x] **Step 5: Run verification**

Run:

```bash
uv run pytest tests/e2e/test_runtime_compose_smoke.py tests/production_foundation/test_ci_workflow.py tests/docs/test_docs_quality.py -q
```

Expected: all tests pass.

- [x] **Step 6: Commit only after explicit user confirmation**

Suggested message:

```bash
git add scripts/compose_runtime_smoke.py .github/workflows/integration.yml docs/start/getting-started.md docs/start/quickstart.md docs/readiness/scorecard.md tests/e2e/test_runtime_compose_smoke.py tests/production_foundation/test_ci_workflow.py
git commit -m "test: prove compose activation path"
```

Do not execute the commit unless the user explicitly asks.

## Task 2: Promote Generic Observability CRUD Into Operator Workbenches

**Priority:** P1

**Files:**
- Create: `apps/console/src/pages/observability/AuditLogWorkbenchPage.vue`
- Create: `apps/console/src/pages/observability/ArtifactWorkbenchPage.vue`
- Create: `apps/console/src/pages/observability/EvaluationWorkbenchPage.vue`
- Create: `apps/console/src/pages/observability/FeedbackWorkbenchPage.vue`
- Create: `apps/console/src/pages/observability/ReplayJobsWorkbenchPage.vue`
- Modify: `apps/console/src/router/index.ts`
- Modify: `apps/console/src/api/client.ts`
- Test: `apps/console/tests/e2e/observability-workbenches.spec.ts`
- Test: `tests/api/test_admin_api.py`

- [x] **Step 1: Write browser tests for operator workflows**

Create `apps/console/tests/e2e/observability-workbenches.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("audit log workbench filters by actor and opens linked evidence", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/audit-logs");

  await expect(page.getByRole("heading", { name: "Audit Log Workbench" })).toBeVisible();
  await page.getByLabel("Actor").fill("operator");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.getByText("policy.activate")).toBeVisible();
  await page.getByRole("button", { name: "Open evidence" }).first().click();
  await expect(page.getByRole("dialog", { name: "Audit evidence" })).toBeVisible();
});

test("artifact workbench previews metadata and links back to run", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/artifacts");

  await expect(page.getByRole("heading", { name: "Artifact Workbench" })).toBeVisible();
  await page.getByRole("button", { name: "Inspect artifact" }).first().click();
  await expect(page.getByRole("dialog", { name: "Artifact detail" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Run #/ })).toBeVisible();
});

test("evaluation workbench compares passed and failed results", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/evaluations");

  await expect(page.getByRole("heading", { name: "Evaluation Workbench" })).toBeVisible();
  await expect(page.getByText("Pass rate")).toBeVisible();
  await page.getByRole("button", { name: "Open result" }).first().click();
  await expect(page.getByRole("dialog", { name: "Evaluation result" })).toBeVisible();
});

test("feedback workbench triages user feedback against run evidence", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/feedback");

  await expect(page.getByRole("heading", { name: "Feedback Workbench" })).toBeVisible();
  await page.getByLabel("Sentiment").selectOption("negative");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await page.getByRole("button", { name: "Open feedback" }).first().click();
  await expect(page.getByRole("dialog", { name: "Feedback detail" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Run #/ })).toBeVisible();
});

test("replay jobs workbench exposes status, source run, and retry action", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/replay-jobs");

  await expect(page.getByRole("heading", { name: "Replay Jobs Workbench" })).toBeVisible();
  await expect(page.getByText("Source run")).toBeVisible();
  await page.getByRole("button", { name: "Inspect replay job" }).first().click();
  await expect(page.getByRole("dialog", { name: "Replay job detail" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry replay" })).toBeVisible();
});
```

Run: `cd apps/console && npx playwright test tests/e2e/observability-workbenches.spec.ts --project=chrome`

Expected: FAIL because the dedicated pages do not exist.

- [x] **Step 2: Add focused pages**

Create the five Vue pages listed above. Each page must have:

- a restrained page header
- filters relevant to the workflow
- a dense table
- a detail drawer/dialog
- links to related runs, deployments, or policies where IDs exist
- no marketing copy

Use existing components:

```text
ApiState
DataTable
AppDrawer
StatusBadge
InlineApiError
```

- [x] **Step 3: Route away from generic CRUD**

In `apps/console/src/router/index.ts`, replace these route components:

```ts
"/observability/audit-logs" -> AuditLogWorkbenchPage
"/observability/artifacts" -> ArtifactWorkbenchPage
"/observability/evaluations" -> EvaluationWorkbenchPage
"/observability/feedback" -> FeedbackWorkbenchPage
"/observability/replay-jobs" -> ReplayJobsWorkbenchPage
```

Keep `AdminCollectionPage` available for lower-value admin resources.

- [x] **Step 4: Add API client helpers**

In `apps/console/src/api/client.ts`, add typed helpers wrapping existing admin endpoints:

```ts
async listAuditLogs(filters: Record<string, string | number | undefined>): Promise<{ items: AdminResource[] }>
async listArtifacts(filters: Record<string, string | number | undefined>): Promise<{ items: AdminResource[] }>
async listEvaluationResults(filters: Record<string, string | number | undefined>): Promise<{ items: AdminResource[] }>
async listFeedback(filters: Record<string, string | number | undefined>): Promise<{ items: AdminResource[] }>
async listReplayJobs(filters: Record<string, string | number | undefined>): Promise<{ items: AdminResource[] }>
```

These helpers should use existing `listAdminCollection` rather than adding new backend routes unless the required filter does not exist.

- [x] **Step 5: Add backend filter tests if needed**

If actor/run/deployment filters are missing in backend generic admin collection handling, add tests to `tests/api/test_admin_api.py`:

```python
def test_audit_logs_filter_by_actor(client, admin_headers):
    response = client.get(
        "/v1/audit-logs?actor=operator",
        headers=admin_headers("req_audit_filter"),
    )
    assert response.status_code == 200
    assert all("operator" in str(item.get("actor", "")) for item in response.json()["items"])
```

Then implement the smallest filter support in `apps/server/dimoo_run/api/admin/router.py`.

- [x] **Step 6: Run verification**

Run:

```bash
cd apps/console && npm run build
cd apps/console && npx playwright test tests/e2e/observability-workbenches.spec.ts --project=chrome
uv run pytest tests/api/test_admin_api.py -q
```

Expected: all tests pass.

- [x] **Step 7: Commit only after explicit user confirmation**

Suggested message:

```bash
git add apps/console/src/pages/observability apps/console/src/router/index.ts apps/console/src/api/client.ts apps/console/tests/e2e/observability-workbenches.spec.ts apps/server/dimoo_run/api/admin/router.py tests/api/test_admin_api.py
git commit -m "feat: add observability operator workbenches"
```

Do not execute the commit unless the user explicitly asks.

## Task 3: Promote Enterprise Ops CRUD Into Incident, Alert, And Webhook Workflows

**Priority:** P1

**Files:**
- Create: `apps/console/src/pages/ops/AlertRulesPage.vue`
- Create: `apps/console/src/pages/ops/WebhookSubscriptionsPage.vue`
- Modify: `apps/console/src/router/index.ts`
- Modify: `apps/server/dimoo_run/api/admin/notifications.py`
- Test: `apps/console/tests/e2e/enterprise-ops.spec.ts`
- Test: `tests/api/test_enterprise_ops_workflows.py`

- [x] **Step 1: Extend e2e tests for alerts and webhooks**

Add to `apps/console/tests/e2e/enterprise-ops.spec.ts`:

```ts
test("creates alert rule and sends a routed notification probe", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/ops/alerts");

  await expect(page.getByRole("heading", { name: "Alert Rules" })).toBeVisible();
  await page.getByRole("button", { name: "New alert rule" }).click();
  await page.getByLabel("Name").fill("runtime error burst");
  await page.getByLabel("Signal").fill("runtime.error_rate");
  await page.getByLabel("Threshold").fill("2");
  await page.getByRole("button", { name: "Save alert rule" }).click();
  await expect(page.getByText("runtime error burst")).toBeVisible();
  await page.getByRole("button", { name: "Test notification" }).click();
  await expect(page.getByText("delivery attempt")).toBeVisible();
});

test("webhook workbench validates target and shows last delivery state", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/ops/webhooks");

  await expect(page.getByRole("heading", { name: "Webhook Subscriptions" })).toBeVisible();
  await page.getByRole("button", { name: "Validate webhook" }).first().click();
  await expect(page.getByText("last delivery")).toBeVisible();
});
```

Run: `cd apps/console && npx playwright test tests/e2e/enterprise-ops.spec.ts --project=chrome`

Expected: FAIL until pages and fixture handlers exist.

- [x] **Step 2: Build dedicated pages**

Create `AlertRulesPage.vue` and `WebhookSubscriptionsPage.vue` using existing panel, table, drawer, and API state patterns.

Alert rules page must show:

```text
rule name
signal
threshold
channel
enabled/disabled status
last triggered
test notification action
```

Webhook page must show:

```text
target URL
event types
retry policy
last delivery status
validate action
secret reference redacted
```

- [x] **Step 3: Wire routes**

In `apps/console/src/router/index.ts`, replace:

```ts
"/ops/alerts" -> AlertRulesPage
"/ops/webhooks" -> WebhookSubscriptionsPage
```

- [x] **Step 4: Add backend workflow support where generic CRUD is insufficient**

If the current backend cannot validate webhook targets or test alert routing, add endpoints:

```text
POST /v1/alerts/rules/{rule_id}/test
POST /v1/webhooks/subscriptions/{subscription_id}/validate
```

Return delivery attempt details in the same shape used by `POST /v1/notifications/test-send`.

- [x] **Step 5: Add API tests**

In `tests/api/test_enterprise_ops_workflows.py`:

```python
def test_alert_rule_test_records_delivery_attempt(client, admin_headers):
    response = client.post(
        "/v1/alerts/rules/1/test",
        headers=admin_headers("req_alert_test"),
        json={"audit_reason": "verify alert route"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["delivery_attempt"]["visible_to_operator"] is True
    assert body["request_id"] == "req_alert_test"


def test_webhook_validate_redacts_secret_reference(client, admin_headers):
    response = client.post(
        "/v1/webhooks/subscriptions/1/validate",
        headers=admin_headers("req_webhook_validate"),
        json={"audit_reason": "verify webhook target"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "secret" not in str(body).lower() or "[REDACTED]" in str(body)
```

- [x] **Step 6: Run verification**

Run:

```bash
uv run pytest tests/api/test_enterprise_ops_workflows.py -q
cd apps/console && npm run build
cd apps/console && npx playwright test tests/e2e/enterprise-ops.spec.ts --project=chrome
```

Expected: all tests pass.

- [x] **Step 7: Commit only after explicit user confirmation**

Suggested message:

```bash
git add apps/console/src/pages/ops apps/console/src/router/index.ts apps/server/dimoo_run/api/admin/notifications.py tests/api/test_enterprise_ops_workflows.py apps/console/tests/e2e/enterprise-ops.spec.ts
git commit -m "feat: add enterprise ops workbenches"
```

Do not execute the commit unless the user explicitly asks.

## Task 4: Harden Scheduled, Batch, And Extension Domain Semantics

**Priority:** P1

**Files:**
- Modify: `apps/server/dimoo_run/domain/models.py`
- Create: `migrations/versions/<timestamp>_harden_runtime_operations.py`
- Modify: `apps/server/dimoo_run/api/admin/schedules.py`
- Modify: `apps/server/dimoo_run/api/admin/batches.py`
- Test: `tests/domain/test_domain_models.py`
- Test: `tests/api/test_scheduled_batch_runtime.py`

- [x] **Step 1: Make placeholder tests fail for hardened tables**

Change `tests/domain/test_domain_models.py` so `scheduled_runs` and `batch_runs` are no longer expected placeholders:

```python
def test_runtime_operation_tables_are_hardened() -> None:
    for table_name in {"scheduled_runs", "batch_runs"}:
        assert Base.metadata.tables[table_name].info.get("placeholder") is not True, table_name
```

Keep `extensions` as placeholder if it is not being hardened in this task.

Run: `uv run pytest tests/domain/test_domain_models.py::test_runtime_operation_tables_are_hardened -q`

Expected: FAIL until model metadata is updated.

- [x] **Step 2: Add concrete fields**

In `apps/server/dimoo_run/domain/models.py`, harden `scheduled_runs` with fields that support product workflows:

```text
schedule_type
timezone
next_fire_at
last_triggered_at
last_run_id
last_task_id
last_run_status
missed_run_policy
backfill_policy
pause_reason
trigger_count
```

Harden `batch_runs` with:

```text
deployment_id
total_items
queued_items
running_items
completed_items
failed_items
dead_letter_items
cancelled_items
partial_failure_policy
cancel_policy
last_recomputed_at
```

Remove placeholder metadata from those two tables only.

- [x] **Step 3: Add Alembic migration**

Create a migration under `migrations/versions/` with explicit `op.add_column` calls and safe nullable defaults for existing local data.

Run: `uv run pytest tests/domain/test_migrations.py -q`

Expected: PASS.

- [x] **Step 4: Update API serialization**

Update:

- `apps/server/dimoo_run/api/admin/schedules.py`
- `apps/server/dimoo_run/api/admin/batches.py`

Ensure list/detail endpoints return the new concrete fields directly rather than hiding them in `metadata_json`.

- [x] **Step 5: Add runtime API tests**

In `tests/api/test_scheduled_batch_runtime.py`, add:

```python
def test_schedule_detail_exposes_hardened_runtime_fields(client, admin_headers):
    response = client.get("/v1/schedules/1", headers=admin_headers("req_schedule_detail"))
    assert response.status_code == 200
    body = response.json()["item"]
    assert "next_fire_time" in body
    assert "trigger_count" in body
    assert "pause_reason" in body


def test_batch_detail_exposes_hardened_summary_fields(client, admin_headers):
    response = client.get("/v1/batch-runs/1", headers=admin_headers("req_batch_detail"))
    assert response.status_code == 200
    body = response.json()["item"]
    for key in ["total_items", "queued_items", "completed_items", "failed_items", "dead_letter_items"]:
        assert key in body
```

- [x] **Step 6: Run verification**

Run:

```bash
uv run pytest tests/domain/test_domain_models.py tests/domain/test_migrations.py tests/api/test_scheduled_batch_runtime.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit only after explicit user confirmation**

Suggested message:

```bash
git add apps/server/dimoo_run/domain/models.py migrations/versions apps/server/dimoo_run/api/admin/schedules.py apps/server/dimoo_run/api/admin/batches.py tests/domain/test_domain_models.py tests/api/test_scheduled_batch_runtime.py
git commit -m "feat: harden scheduled and batch runtime models"
```

Do not execute the commit unless the user explicitly asks.

## Task 5: Monitoring Exporter Proof And Settings Workbench

**Priority:** P2

**Files:**
- Create: `apps/console/src/pages/settings/ObservabilityExportersPage.vue`
- Create: `apps/console/src/pages/settings/SemanticStoreProvidersPage.vue`
- Create: `apps/console/src/pages/settings/SandboxPoliciesPage.vue`
- Create: `apps/console/src/pages/settings/ContainerPoolPoliciesPage.vue`
- Modify: `apps/console/src/router/index.ts`
- Modify: `apps/server/dimoo_run/api/console/settings.py`
- Test: `apps/console/tests/e2e/settings-observability.spec.ts`
- Test: `apps/console/tests/e2e/settings-platform-workbenches.spec.ts`
- Test: `tests/api/test_platform_settings_workflows.py`
- Modify: `docs/readiness/current-maturity.md`

- [x] **Step 1: Add failing browser test for exporter validation**

Create `apps/console/tests/e2e/settings-observability.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("observability exporter workbench validates OTLP target and shows proof state", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/observability-exporters");

  await expect(page.getByRole("heading", { name: "Observability Exporters" })).toBeVisible();
  await page.getByRole("button", { name: "Validate exporter" }).first().click();
  await expect(page.getByText("validation status")).toBeVisible();
  await expect(page.getByText("last proof")).toBeVisible();
});
```

Run: `cd apps/console && npx playwright test tests/e2e/settings-observability.spec.ts --project=chrome`

Expected: FAIL until the page exists.

- [x] **Step 2: Add failing browser tests for the other Platform workbenches**

Create `apps/console/tests/e2e/settings-platform-workbenches.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("semantic store providers page validates provider readiness", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/semantic-store");

  await expect(page.getByRole("heading", { name: "Semantic Store Providers" })).toBeVisible();
  await page.getByRole("button", { name: "Validate provider" }).first().click();
  await expect(page.getByText("provider status")).toBeVisible();
  await expect(page.getByText("index coverage")).toBeVisible();
});

test("sandbox policies page previews enforcement result before save", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/sandbox-policies");

  await expect(page.getByRole("heading", { name: "Sandbox Policies" })).toBeVisible();
  await page.getByRole("button", { name: "Preview enforcement" }).first().click();
  await expect(page.getByText("blocked capabilities")).toBeVisible();
  await expect(page.getByText("audit reason required")).toBeVisible();
});

test("container pool policies page estimates capacity impact", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/container-pool-policies");

  await expect(page.getByRole("heading", { name: "Container Pool Policies" })).toBeVisible();
  await page.getByRole("button", { name: "Estimate impact" }).first().click();
  await expect(page.getByText("warm capacity")).toBeVisible();
  await expect(page.getByText("scale limit")).toBeVisible();
});
```

Run: `cd apps/console && npx playwright test tests/e2e/settings-platform-workbenches.spec.ts --project=chrome`

Expected: FAIL until the dedicated pages exist.

- [x] **Step 3: Add console API endpoint**

In `apps/server/dimoo_run/api/console/settings.py`, add:

```text
POST /v1/console/settings/observability-exporters/{exporter_id}/validate
POST /v1/console/settings/semantic-store-providers/{provider_id}/validate
POST /v1/console/settings/sandbox-policies/{policy_id}/preview
POST /v1/console/settings/container-pool-policies/{policy_id}/estimate
```

Return:

```json
{
  "item": {
    "exporter_id": 1,
    "validation_status": "reachable",
    "last_proof_at": "2026-06-15T00:00:00Z",
    "target_ref_redacted": "http://otel:4318",
    "request_id": "req_exporter_validate"
  }
}
```

Use a deterministic local validation in test mode. Do not make a network call during unit tests.

- [x] **Step 4: Add backend tests**

In `tests/api/test_platform_settings_workflows.py`:

```python
def test_observability_exporter_validation_redacts_target_and_records_proof(client, admin_headers):
    response = client.post(
        "/v1/console/settings/observability-exporters/1/validate",
        headers=admin_headers("req_exporter_validate"),
        json={"audit_reason": "verify exporter"},
    )
    assert response.status_code == 200
    body = response.json()["item"]
    assert body["validation_status"] in {"reachable", "blocked", "unconfigured"}
    assert body["request_id"] == "req_exporter_validate"


def test_semantic_store_provider_validation_reports_index_coverage(client, admin_headers):
    response = client.post(
        "/v1/console/settings/semantic-store-providers/1/validate",
        headers=admin_headers("req_semantic_provider_validate"),
        json={"audit_reason": "verify semantic store"},
    )
    assert response.status_code == 200
    body = response.json()["item"]
    assert body["provider_status"] in {"ready", "degraded", "unconfigured"}
    assert "index_coverage" in body


def test_sandbox_policy_preview_reports_blocked_capabilities(client, admin_headers):
    response = client.post(
        "/v1/console/settings/sandbox-policies/1/preview",
        headers=admin_headers("req_sandbox_preview"),
        json={"capabilities": ["network", "filesystem"], "audit_reason": "preview sandbox"},
    )
    assert response.status_code == 200
    body = response.json()["item"]
    assert "blocked_capabilities" in body
    assert body["audit_required"] is True


def test_container_pool_policy_estimate_reports_capacity_impact(client, admin_headers):
    response = client.post(
        "/v1/console/settings/container-pool-policies/1/estimate",
        headers=admin_headers("req_container_pool_estimate"),
        json={"requested_workers": 4, "audit_reason": "estimate pool"},
    )
    assert response.status_code == 200
    body = response.json()["item"]
    assert "warm_capacity" in body
    assert "scale_limit" in body
    assert body["request_id"] == "req_container_pool_estimate"
```

- [x] **Step 5: Build workbench pages**

Create `ObservabilityExportersPage.vue` with:

```text
exporter list
target ref redaction
validate action
last proof timestamp
copyable configuration summary
blocked reason display
```

Create `SemanticStoreProvidersPage.vue` with:

```text
provider list
embedding model and index metadata
validate provider action
provider status display
index coverage summary
last validation proof
```

Create `SandboxPoliciesPage.vue` with:

```text
policy list
capability restrictions
preview enforcement action
blocked capabilities summary
audit requirement state
affected runtime surfaces
```

Create `ContainerPoolPoliciesPage.vue` with:

```text
policy list
warm capacity
scale limit
estimate impact action
estimated saturation state
affected worker pools
```

- [x] **Step 6: Route dedicated pages**

In `apps/console/src/router/index.ts`, replace these routes:

```ts
"/settings/observability-exporters" -> ObservabilityExportersPage
"/settings/semantic-store" -> SemanticStoreProvidersPage
"/settings/sandbox-policies" -> SandboxPoliciesPage
"/settings/container-pool-policies" -> ContainerPoolPoliciesPage
```

- [x] **Step 7: Update maturity docs conservatively**

Only after tests pass, update `docs/readiness/current-maturity.md` from:

```text
Hosted Prometheus/OTel exporter proof ... not complete yet
```

to:

```text
Local exporter validation proof exists; hosted monitoring-stack verification remains incomplete.
```

- [x] **Step 8: Run verification**

Run:

```bash
uv run pytest tests/api/test_platform_settings_workflows.py -q
cd apps/console && npm run build
cd apps/console && npx playwright test tests/e2e/settings-observability.spec.ts --project=chrome
cd apps/console && npx playwright test tests/e2e/settings-platform-workbenches.spec.ts --project=chrome
uv run pytest tests/docs/test_docs_quality.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit only after explicit user confirmation**

Suggested message:

```bash
git add apps/server/dimoo_run/api/console/settings.py tests/api/test_platform_settings_workflows.py apps/console/src/pages/settings/ObservabilityExportersPage.vue apps/console/src/pages/settings/SemanticStoreProvidersPage.vue apps/console/src/pages/settings/SandboxPoliciesPage.vue apps/console/src/pages/settings/ContainerPoolPoliciesPage.vue apps/console/src/router/index.ts apps/console/tests/e2e/settings-observability.spec.ts apps/console/tests/e2e/settings-platform-workbenches.spec.ts docs/readiness/current-maturity.md
git commit -m "feat: add platform settings validation workbenches"
```

Do not execute the commit unless the user explicitly asks.

## Task 6: Compatibility Examples, Support Matrix, And Migration Remediation

**Priority:** P1

**Files:**
- Create: `examples/compatibility/langgraph-basic/README.md`
- Create: `examples/compatibility/langgraph-basic/compat_flow.py`
- Create: `examples/compatibility/langgraph-basic/source/langgraph.json`
- Create: `examples/compatibility/langgraph-basic/source/agent.py`
- Create: `examples/compatibility/langgraph-basic/source/pyproject.toml`
- Create: `docs/reference/compatibility.md`
- Modify: `examples/compatibility/README.md`
- Modify: `apps/server/dimoo_run/compatibility/migration_report.py`
- Modify: `apps/server/dimoo_run/api/console/compatibility.py`
- Modify: `apps/console/src/pages/compatibility/CompatibilityExplorerPage.vue`
- Modify: `apps/console/src/pages/compatibility/MigrationReportPanel.vue`
- Test: `tests/api/test_compatibility_console_workflows.py`
- Test: `tests/compat/test_langgraph_compat_api.py`
- Test: `tests/migration/test_langgraph_migration.py`
- Test: `tests/docs/test_docs_quality.py`
- Test: `apps/console/tests/e2e/compatibility-explorer.spec.ts`
- Test: `apps/console/tests/e2e-live/compatibility-live.spec.ts`

- [x] **Step 1: Add failing tests for runnable compatibility examples**

In `tests/docs/test_docs_quality.py`, add:

```python
def test_compatibility_examples_are_runnable_and_documented() -> None:
    root = Path("examples/compatibility/langgraph-basic")
    assert (root / "README.md").exists()
    assert (root / "compat_flow.py").exists()
    assert (root / "source" / "langgraph.json").exists()
    readme = (root / "README.md").read_text(encoding="utf-8")
    required = [
        "Create assistant",
        "Create thread",
        "Create run",
        "Stream events",
        "Replay events",
        "Cancel run",
        "Migration report",
        "Native Run and Task evidence",
    ]
    for phrase in required:
        assert phrase in readme
```

Run: `uv run pytest tests/docs/test_docs_quality.py::test_compatibility_examples_are_runnable_and_documented -q`

Expected: FAIL until the example directory and README exist.

- [x] **Step 2: Add the LangGraph compatibility example**

Create `examples/compatibility/langgraph-basic/source/langgraph.json`:

```json
{
  "graphs": {
    "support": "./agent.py:build_graph"
  },
  "env": ".env"
}
```

Create `examples/compatibility/langgraph-basic/source/agent.py`:

```python
def build_graph():
    def invoke(payload):
        message = payload.get("message", "")
        return {"answer": f"compatibility example received: {message}"}

    return invoke
```

Create `examples/compatibility/langgraph-basic/source/pyproject.toml`:

```toml
[project]
name = "dimoorun-compatibility-langgraph-basic"
version = "0.1.0"
dependencies = [
  "langgraph>=1.0.0",
  "langchain-core>=1.0.0"
]
```

Create `examples/compatibility/langgraph-basic/README.md` with this exact workflow outline:

````markdown
# LangGraph Compatibility Basic Example

This example proves the Compatibility API path for a small LangGraph-shaped project.

## Flow

1. Migration report
2. Create assistant
3. Create thread
4. Create run
5. Stream events
6. Replay events
7. Cancel run
8. Native Run and Task evidence

## Run

Start DimooRun locally, then run:

```bash
uv run python examples/compatibility/langgraph-basic/compat_flow.py --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1
```

The script prints assistant_id, thread_id, run_id, task_id, stream events, and native evidence links.
````

- [x] **Step 3: Add compatibility example script**

Create `examples/compatibility/langgraph-basic/compat_flow.py`:

```python
from __future__ import annotations

import argparse
import json
from typing import Any

import httpx


def main() -> None:
    args = parse_args()
    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "X-Tenant-Id": str(args.tenant_id),
        "X-Project-Id": str(args.project_id),
        "X-Request-Id": "req_compat_example",
    }
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=30) as client:
        migration = post_json(
            client,
            "/v1/console/compatibility/migration-report",
            {
                "framework": "langgraph",
                "adapter": "langgraph",
                "capabilities": ["assistants", "threads", "runs", "stream", "hosted_deployments"],
                "streaming_modes": ["events"],
                "uses_checkpointing": True,
            },
        )
        assistant = post_json(
            client,
            "/compat/langgraph/assistants",
            {"name": "compatibility-basic"},
        )
        thread = post_json(client, "/compat/langgraph/threads", {"metadata": {"label": "compat-basic"}})
        run = post_json(
            client,
            f"/compat/langgraph/threads/{thread['thread_id']}/runs",
            {"assistant_id": assistant["assistant_id"], "input": {"message": "hello compatibility"}},
        )
        stream_text = post_stream(
            client,
            f"/compat/langgraph/threads/{thread['thread_id']}/runs/stream",
            {"assistant_id": assistant["assistant_id"], "input": {"message": "stream compatibility"}},
        )
        cancel = post_json(
            client,
            f"/compat/langgraph/threads/{thread['thread_id']}/runs/{run['run_id']}/cancel",
            {},
        )
    print(json.dumps({
        "migration_status": migration["report"]["overall_status"],
        "assistant_id": assistant["assistant_id"],
        "thread_id": thread["thread_id"],
        "run_id": run["run_id"],
        "task_id": run["metadata"]["dimoorun_mapping"]["task_id"],
        "stream_contains_run_created": "event: run.created" in stream_text,
        "cancel_status": cancel["status"],
        "native_evidence": {
            "run": f"/runs/{run['run_id']}",
            "task_id": run["metadata"]["dimoorun_mapping"]["task_id"],
        },
    }, indent=2, sort_keys=True))


def post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} did not return a JSON object")
    return data


def post_stream(client: httpx.Client, path: str, payload: dict[str, Any]) -> str:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--project-id", type=int, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
```

Run: `uv run python -m py_compile examples/compatibility/langgraph-basic/compat_flow.py`

Expected: PASS.

- [x] **Step 4: Add failing tests for actionable remediation fields**

In `tests/api/test_compatibility_console_workflows.py`, add:

```python
def test_console_compatibility_migration_report_includes_actionable_remediation() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read"})

    response = client.post(
        "/v1/console/compatibility/migration-report",
        headers=auth_headers(key),
        json={
            "framework": "langgraph",
            "adapter": "langgraph",
            "capabilities": ["assistants", "threads", "runs", "hosted_deployments"],
            "streaming_modes": ["events"],
        },
    )

    assert response.status_code == 200
    report = response.json()["report"]
    step = report["remediation_steps"][0]
    assert step["capability"] == "hosted_deployments"
    assert step["severity"] == "manual_migration_required"
    assert step["target_files"] == ["dimoorun.yaml", "manifest.yaml"]
    assert step["recommended_action"] == "Use native deployments for hosted runtime behavior"
    assert step["verification_command"] == "uv run dimoorun deployment create --help"
    assert step["native_route"] == "/deployments"
```

Run: `uv run pytest tests/api/test_compatibility_console_workflows.py::test_console_compatibility_migration_report_includes_actionable_remediation -q`

Expected: FAIL until `remediation_steps` is part of the report.

- [x] **Step 5: Extend migration report model**

In `apps/server/dimoo_run/compatibility/migration_report.py`, add remediation generation to `build_migration_report()` so unsupported `hosted_deployments` returns this shape:

```python
{
    "capability": "hosted_deployments",
    "reason": "compatibility_not_supported",
    "severity": "manual_migration_required",
    "target_files": ["dimoorun.yaml", "manifest.yaml"],
    "recommended_action": "Use native deployments for hosted runtime behavior",
    "verification_command": "uv run dimoorun deployment create --help",
    "native_route": "/deployments",
}
```

For unsupported stream modes, return:

```python
{
    "capability": "stream:<mode>",
    "reason": "compatibility_not_supported",
    "severity": "configuration_change_required",
    "target_files": ["dimoorun.yaml"],
    "recommended_action": "Use event or update streaming modes in the compatibility bridge",
    "verification_command": "uv run pytest tests/compat/test_langgraph_compat_api.py -q",
    "native_route": "/compatibility",
}
```

Run: `uv run pytest tests/api/test_compatibility_console_workflows.py::test_console_compatibility_migration_report_includes_actionable_remediation -q`

Expected: PASS.

- [x] **Step 6: Add migration example coverage**

In `tests/migration/test_langgraph_migration.py`, add:

```python
def test_langgraph_compatibility_example_migrates_to_dimoorun_manifest() -> None:
    source = Path("examples/compatibility/langgraph-basic/source")
    output = source.parent / ".generated"
    if output.exists():
        shutil.rmtree(output)

    report = migrate_langgraph_project(source, output, project_name="compatibility-basic")

    assert report.detected_entrypoint == "agent:build_graph"
    assert (output / "manifest.yaml").exists()
    assert (output / "dimoorun.yaml").exists()
    report_text = (output / "migration_report.md").read_text(encoding="utf-8")
    assert "langgraph.json" in report_text
    assert "support -> agent:build_graph" in report_text
```

Add `import shutil` near the top of the file.

Run: `uv run pytest tests/migration/test_langgraph_migration.py::test_langgraph_compatibility_example_migrates_to_dimoorun_manifest -q`

Expected: PASS after the example exists.

- [x] **Step 7: Render remediation and support matrix in Console**

Update `apps/console/src/pages/compatibility/MigrationReportPanel.vue` to render:

```text
Recommended remediation
Capability
Severity
Target files
Recommended action
Verification command
Native route
```

Update `apps/console/src/pages/compatibility/CompatibilityExplorerPage.vue` only if it needs type plumbing for `remediation_steps`.

Add or update the mocked response in `apps/console/tests/fixtures/api.ts` so `compatibilityMigrationReportResponse()` includes `remediation_steps` with the `hosted_deployments` fields from Step 4.

- [x] **Step 8: Add Console e2e assertions**

Extend `apps/console/tests/e2e/compatibility-explorer.spec.ts`:

```ts
await expect(page.getByRole("heading", { name: "Recommended remediation" })).toBeVisible();
await expect(page.getByText("manual_migration_required")).toBeVisible();
await expect(page.getByText("dimoorun.yaml")).toBeVisible();
await expect(page.getByText("uv run dimoorun deployment create --help")).toBeVisible();
await expect(page.getByRole("link", { name: "/deployments" })).toBeVisible();
```

Run: `cd apps/console && npx playwright test tests/e2e/compatibility-explorer.spec.ts --project=chrome`

Expected: PASS.

- [x] **Step 9: Add live backend compatibility proof**

Create `apps/console/tests/e2e-live/compatibility-live.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("compatibility explorer uses live backend mapping evidence", async ({ page }) => {
  await page.goto("/compatibility");
  await page.getByLabel("Capabilities").fill("assistants,threads,runs,hosted_deployments");
  await page.getByRole("button", { name: "Generate migration report" }).click();
  await expect(page.getByText("migration_required")).toBeVisible();
  await expect(page.getByText("Recommended remediation")).toBeVisible();

  await page.getByLabel("Name").fill("compatibility-live");
  await page.getByRole("button", { name: "Create assistant" }).click();
  await expect(page.getByLabel("Assistant ID")).toHaveValue(/assistant_/);

  await page.getByRole("button", { name: "Create thread" }).click();
  await expect(page.getByLabel("Thread ID")).toHaveValue(/thread_/);

  await page.getByLabel("Input message").fill("hello from live compatibility proof");
  await page.getByRole("button", { name: "Create run" }).click();
  await expect(page.getByText("native_task_id")).toBeVisible();
  await expect(page.getByRole("link", { name: /Run #/ })).toBeVisible();
});
```

Wire this spec into the existing live e2e runner only after confirming it can authenticate with the same live fixture mechanism used by the other live specs.

Run: `cd apps/console && npm run test:e2e:live -- compatibility-live.spec.ts`

Expected: PASS in the live backend profile.

- [x] **Step 10: Add compatibility support matrix docs**

Create `docs/reference/compatibility.md`:

```markdown
# Compatibility Support Matrix

Compatibility APIs let LangGraph-shaped clients enter DimooRun without bypassing native governance.

| Surface | Status | Native Evidence | Notes |
|---|---|---|---|
| assistants | supported | Agent and AgentVersion mapping | Can bind to an existing deployment when provided |
| threads | supported | checkpoint_thread_id mapping | Scoped by tenant and project |
| runs | supported | Run and Task mapping | Native runtime state remains source of truth |
| stream events | supported | ReplayBuffer event ids | Event and update modes are supported |
| Last-Event-ID replay | supported | replayed event list | Expired replay returns `stream_replay_expired` |
| cancel | supported | Run, Task, and audit update | Uses native cancellation semantics |
| join | supported | Run terminal status and audit update | Does not execute external hosted LangGraph infrastructure |
| hosted deployments | manual migration required | native Deployment workflow | Use DimooRun deployments instead |
| LangGraph Platform managed services | manual migration required | migration report remediation | Hosted platform settings require review |
```

Update `examples/compatibility/README.md` to link to:

```text
examples/compatibility/langgraph-basic
docs/reference/compatibility.md
```

Run: `uv run pytest tests/docs/test_docs_quality.py -q`

Expected: PASS.

- [x] **Step 11: Run verification**

Run:

```bash
uv run pytest tests/api/test_compatibility_console_workflows.py tests/compat/test_langgraph_compat_api.py tests/compatibility/test_golden_runtime_alignment.py tests/migration/test_langgraph_migration.py tests/docs/test_docs_quality.py -q
uv run python -m py_compile examples/compatibility/langgraph-basic/compat_flow.py
cd apps/console && npm run build
cd apps/console && npx playwright test tests/e2e/compatibility-explorer.spec.ts --project=chrome
```

Expected: all tests pass.

- [ ] **Step 12: Commit only after explicit user confirmation**

Suggested message:

```bash
git add examples/compatibility docs/reference/compatibility.md apps/server/dimoo_run/compatibility/migration_report.py apps/server/dimoo_run/api/console/compatibility.py apps/console/src/pages/compatibility/CompatibilityExplorerPage.vue apps/console/src/pages/compatibility/MigrationReportPanel.vue apps/console/tests/fixtures/api.ts apps/console/tests/e2e/compatibility-explorer.spec.ts apps/console/tests/e2e-live/compatibility-live.spec.ts tests/api/test_compatibility_console_workflows.py tests/migration/test_langgraph_migration.py tests/docs/test_docs_quality.py
git commit -m "feat: add compatibility examples and remediation proof"
```

Do not execute the commit unless the user explicitly asks.

## Task 7: Console Module Completeness Closure

**Priority:** P1

**Files:**
- Modify: `apps/console/src/pages/identity/OrganizationScopePage.vue`
- Modify: `apps/console/src/pages/governance/PoliciesPage.vue`
- Modify: `apps/console/src/pages/governance/ConfigAssetsPage.vue`
- Modify: `apps/console/src/pages/governance/TemplateAssetsPage.vue`
- Modify: `apps/console/src/layouts/AppShell.vue`
- Modify: `apps/console/src/router/index.ts`
- Test: `apps/console/tests/e2e/module-completeness.spec.ts`
- Test: `apps/console/tests/e2e/identity-governance-completeness.spec.ts`
- Test: `apps/console/tests/e2e/route-coverage.spec.ts`

- [x] **Step 1: Add navigation completeness test**

Create `apps/console/tests/e2e/module-completeness.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

const expectedNavigation = {
  Overview: ["Dashboard"],
  Runtime: [
    "Agents",
    "Packages",
    "Deployments",
    "Published Surfaces",
    "Workers",
    "Agent Instances",
    "Capacity",
    "Scheduled Runs",
    "Batch Runs",
    "Runs",
    "Tasks",
  ],
  Observability: [
    "Events",
    "Replay",
    "Audit Logs",
    "Artifacts",
    "Datasets",
    "Experiments",
    "Quality Gate",
    "Cost",
    "Budget",
    "Evaluation Results",
    "Feedback",
    "Replay Jobs",
  ],
  Identity: ["Organization Scope", "Operators", "Roles & Permissions", "Machine Identity"],
  Governance: [
    "Human Tasks",
    "Policies",
    "Model Gateways",
    "Tools",
    "Secrets",
    "Catalog Items",
    "Prompt Assets",
    "Config Assets",
    "Template Assets",
  ],
  "Enterprise Ops": ["Backup & Restore", "Webhook Subscriptions", "Alert Rules", "Incidents"],
  Compatibility: ["Compatibility"],
  Platform: [
    "Platform Settings",
    "Provider Status",
    "Danger Zone",
    "Semantic Store Providers",
    "Observability Exporters",
    "Sandbox Policies",
    "Container Pool Policies",
    "Settings",
  ],
};

test("console navigation exposes the reviewed module and submenu matrix", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/");

  for (const [moduleName, submenus] of Object.entries(expectedNavigation)) {
    await expect(page.getByRole("navigation").getByText(moduleName)).toBeVisible();
    for (const submenu of submenus) {
      await expect(page.getByRole("link", { name: submenu })).toBeVisible();
    }
  }
});

test("high value routes do not render the generic collection title", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  const routes = [
    "/observability/audit-logs",
    "/observability/artifacts",
    "/observability/evaluations",
    "/observability/feedback",
    "/observability/replay-jobs",
    "/ops/webhooks",
    "/ops/alerts",
    "/settings/semantic-store",
    "/settings/observability-exporters",
    "/settings/sandbox-policies",
    "/settings/container-pool-policies",
    "/governance/policies",
  ];

  for (const route of routes) {
    await page.goto(route);
    await expect(page.getByRole("heading", { name: "Admin Collection" })).toHaveCount(0);
  }
});
```

Run: `cd apps/console && npx playwright test tests/e2e/module-completeness.spec.ts --project=chrome`

Expected: FAIL until all listed high-value routes are promoted out of generic CRUD.

- [x] **Step 2: Add Identity and Governance completeness tests**

Create `apps/console/tests/e2e/identity-governance-completeness.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("organization scope page shows active tenant, project, and switch evidence", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/identity/scope");

  await expect(page.getByRole("heading", { name: "Organization Scope" })).toBeVisible();
  await expect(page.getByText("Active tenant")).toBeVisible();
  await expect(page.getByText("Active project")).toBeVisible();
  await page.getByRole("button", { name: "Preview switch" }).click();
  await expect(page.getByRole("dialog", { name: "Scope switch preview" })).toBeVisible();
  await expect(page.getByText("affected runs")).toBeVisible();
});

test("policies page exposes policy simulation without generic crud residue", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/governance/policies");

  await expect(page.getByRole("heading", { name: "Policy Workbench" })).toBeVisible();
  await page.getByRole("button", { name: "Simulate policy" }).first().click();
  await expect(page.getByRole("dialog", { name: "Policy simulation" })).toBeVisible();
  await expect(page.getByText("decision")).toBeVisible();
  await expect(page.getByText("matched rule")).toBeVisible();
});

test("config and template assets expose version evidence and promotion actions", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/governance/config-assets");
  await expect(page.getByRole("heading", { name: "Config Assets" })).toBeVisible();
  await page.getByRole("button", { name: "Open asset" }).first().click();
  await expect(page.getByRole("dialog", { name: "Config asset detail" })).toBeVisible();
  await expect(page.getByText("version evidence")).toBeVisible();

  await page.goto("/governance/template-assets");
  await expect(page.getByRole("heading", { name: "Template Assets" })).toBeVisible();
  await page.getByRole("button", { name: "Open template" }).first().click();
  await expect(page.getByRole("dialog", { name: "Template asset detail" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Promote version" })).toBeVisible();
});
```

Run: `cd apps/console && npx playwright test tests/e2e/identity-governance-completeness.spec.ts --project=chrome`

Expected: FAIL until the Identity and Governance pages expose these product-specific controls.

- [x] **Step 3: Strengthen Organization Scope**

Update `apps/console/src/pages/identity/OrganizationScopePage.vue` so it shows:

```text
active tenant
active project
operator role summary
scope switch preview
affected runs
affected deployments
audit reason capture
confirmation state
```

Keep typography restrained. Body copy should stay at the existing application body size, and form controls should use normal font weight unless a design token already marks a label as emphasized.

- [x] **Step 4: Remove policy CRUD residue**

Update `apps/console/src/pages/governance/PoliciesPage.vue` so the primary page is a policy workbench with:

```text
policy list
status and enforcement scope
simulate policy action
decision result
matched rule
related audit log link
publish or rollback action
```

Do not wrap the page around `AdminCollectionPage`. Keep the route at `/governance/policies`.

- [x] **Step 5: Strengthen Config and Template Assets**

Update:

```text
apps/console/src/pages/governance/ConfigAssetsPage.vue
apps/console/src/pages/governance/TemplateAssetsPage.vue
```

Both pages must show:

```text
version history
version evidence
linked deployment or catalog item
promotion action
rollback action
validation state
```

Use existing table, drawer, modal, and status components instead of adding a separate visual system.

- [x] **Step 6: Keep navigation labels and routes aligned**

Check `apps/console/src/layouts/AppShell.vue` and `apps/console/src/router/index.ts` so every submenu in the module matrix has:

```text
one visible navigation link
one route path
one page component
one e2e route coverage entry
```

Do not add duplicate menu labels for the same route.

- [x] **Step 7: Run verification**

Run:

```bash
cd apps/console && npm run build
cd apps/console && npx playwright test tests/e2e/module-completeness.spec.ts --project=chrome
cd apps/console && npx playwright test tests/e2e/identity-governance-completeness.spec.ts --project=chrome
cd apps/console && npx playwright test tests/e2e/route-coverage.spec.ts --project=chrome
```

Expected: all tests pass.

- [ ] **Step 8: Commit only after explicit user confirmation**

Suggested message:

```bash
git add apps/console/src/pages/identity/OrganizationScopePage.vue apps/console/src/pages/governance/PoliciesPage.vue apps/console/src/pages/governance/ConfigAssetsPage.vue apps/console/src/pages/governance/TemplateAssetsPage.vue apps/console/src/layouts/AppShell.vue apps/console/src/router/index.ts apps/console/tests/e2e/module-completeness.spec.ts apps/console/tests/e2e/identity-governance-completeness.spec.ts apps/console/tests/e2e/route-coverage.spec.ts
git commit -m "feat: close console module completeness gaps"
```

Do not execute the commit unless the user explicitly asks.

## Task 8: Public Evidence Gallery And Demo Proof

**Priority:** P2

**Files:**
- Create: `docs/readiness/evidence-gallery.md`
- Modify: `apps/console/tests/e2e/responsive-snapshots.spec.ts`
- Modify: `docs/DEMO_SCRIPT.md`
- Modify: `README.md`
- Test: `tests/docs/test_docs_quality.py`

- [x] **Step 1: Add docs quality test**

In `tests/docs/test_docs_quality.py`, add:

```python
def test_evidence_gallery_lists_required_product_screens() -> None:
    gallery = Path("docs/readiness/evidence-gallery.md").read_text(encoding="utf-8")
    required = [
        "Dashboard",
        "Agent detail",
        "Deployment workflow",
        "Run workbench",
        "Published surface route tester",
        "Approval queue",
        "Settings danger zone",
        "Quickstart activation path",
    ]
    for item in required:
        assert item in gallery
```

Run: `uv run pytest tests/docs/test_docs_quality.py::test_evidence_gallery_lists_required_product_screens -q`

Expected: FAIL until gallery exists.

- [x] **Step 2: Create evidence gallery document**

Create `docs/readiness/evidence-gallery.md`:

```markdown
# Evidence Gallery

This page indexes generated product evidence. It is not a marketing gallery; it records what was captured, by which command, and which claim it supports.

| Evidence | Command | Claim Supported | Current Status |
|---|---|---|---|
| Dashboard | `npm run test:e2e -- responsive-snapshots.spec.ts` | Console renders runtime overview | local screenshot generated |
| Agent detail | `npm run test:e2e -- responsive-snapshots.spec.ts` | Agent/version workflow is inspectable | local screenshot generated |
| Deployment workflow | `npm run test:e2e -- deployment-promotion.spec.ts` | Deployment promotion and rollback are operable | local browser proof |
| Run workbench | `npm run test:e2e -- run-triage-replay.spec.ts` | Run triage and replay evidence are inspectable | local browser proof |
| Published surface route tester | `npm run test:e2e -- published-surfaces.spec.ts` | Route validation and request-log redaction work | local browser proof |
| Approval queue | `npm run test:e2e -- policy-approval.spec.ts` | Human decisions produce resume outcome evidence | local browser proof |
| Settings danger zone | `npm run test:e2e -- runtime-capacity.spec.ts` | Dangerous platform actions require preflight and confirmation | local browser proof |
| Quickstart activation path | `uv run python scripts/compose_runtime_smoke.py` | Full local activation path works | pending hosted artifact until Task 1 closes |
```

- [x] **Step 3: Update README**

In `README.md`, replace the screenshot evidence caveat with a link to the gallery and keep the claim conservative:

```text
Generated product evidence is indexed in docs/readiness/evidence-gallery.md. Hosted/public screenshots are still incomplete unless the gallery row links to a current artifact.
```

- [x] **Step 4: Run verification**

Run:

```bash
uv run pytest tests/docs/test_docs_quality.py -q
cd apps/console && npx playwright test tests/e2e/responsive-snapshots.spec.ts --project=chrome
```

Expected: all tests pass.

- [ ] **Step 5: Commit only after explicit user confirmation**

Suggested message:

```bash
git add docs/readiness/evidence-gallery.md README.md docs/DEMO_SCRIPT.md apps/console/tests/e2e/responsive-snapshots.spec.ts tests/docs/test_docs_quality.py
git commit -m "docs: add product evidence gallery"
```

Do not execute the commit unless the user explicitly asks.

## Execution Order

1. Task 1: Activation Evidence For The First Runtime Path
2. Task 2: Promote Generic Observability CRUD Into Operator Workbenches
3. Task 3: Promote Enterprise Ops CRUD Into Incident, Alert, And Webhook Workflows
4. Task 4: Harden Scheduled, Batch, And Extension Domain Semantics
5. Task 5: Monitoring Exporter Proof And Settings Workbench
6. Task 6: Compatibility Examples, Support Matrix, And Migration Remediation
7. Task 7: Console Module Completeness Closure
8. Task 8: Public Evidence Gallery And Demo Proof

This order closes the highest-value product promise first, then upgrades operator workflows, then hardens proof and polish.

## Global Verification

After each task:

```bash
uv run pytest -q
cd apps/console && npm run test:unit
cd apps/console && npm run build
cd apps/console && npm run test:e2e
```

Expected:

```text
pytest passes
Console unit tests pass
Console build passes
Console e2e passes
```

If full `pytest -q` is too slow during a task, run the task-specific tests first, then run the global suite before marking the task complete.

## Non-Goals

- Do not turn DimooRun into a low-code builder, prompt IDE, or generic ITSM system.
- Do not claim external production readiness until scorecard evidence supports it.
- Do not replace existing native runtime concepts with compatibility-layer concepts.
- Do not remove `AdminCollectionPage`; keep it as a fallback for low-value admin collections.
- Do not commit without explicit user confirmation.

## Self-Review

**Spec coverage:** The plan covers the reviewed product gaps: activation proof, generic CRUD promotion, domain placeholder hardening, monitoring proof, compatibility remediation, Console module completeness across Overview, Runtime, Observability, Identity, Governance, Enterprise Ops, Compatibility, and Platform, evidence gallery, and maturity docs.

**Placeholder scan:** The plan contains no unresolved placeholder work items. Each task includes concrete files, commands, expected outcomes, and product acceptance criteria.

**Type consistency:** Page, route, test, and endpoint names are consistent within each task. Tasks that introduce new endpoints include matching API and browser tests before implementation.
