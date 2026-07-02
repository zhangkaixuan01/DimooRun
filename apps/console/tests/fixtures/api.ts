import type { Page, Route } from "@playwright/test";

import type {
  AdminCollectionResponse,
  ConsoleDashboardSummaryRead,
  ConsoleRuntimeOverviewRead,
  ConsoleOperatorRead,
  NativeAgentRead,
  NativeAgentVersionRead,
  NativeDeploymentRead,
  NativeEventRead,
  NativeRunIntegrationEvidenceRead,
  NativeRunRead,
} from "../../src/api/generated/dimoorun";

export const e2eScope = {
  tenant_id: 1,
  tenant_name: "Local Tenant",
  project_id: 1,
  project_name: "DimooRun",
  environment: "local",
  environment_name: "Local",
};

export const e2eOperator: ConsoleOperatorRead = {
  id: 1,
  email: "admin@local.dimoorun",
  name: "E2E Operator",
  roles: ["platform_admin"],
  permissions: ["*"],
  allowed_scopes: [e2eScope],
  status: "active",
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
  last_login_at: null,
  password_changed_at: null,
};

export type DashboardApiFixture = {
  agents: NativeAgentRead[];
  versions: NativeAgentVersionRead[];
  deployments: NativeDeploymentRead[];
  runs: NativeRunRead[];
  runtimeOverview: ConsoleRuntimeOverviewRead;
  humanTasks: AdminCollectionResponse<Record<string, unknown>>;
  incidents: AdminCollectionResponse<Record<string, unknown>>;
};

type RuntimeWorkerFixture = Record<string, unknown> & {
  worker_id: string;
  drain_status: string;
  active_attempts: number;
  active_runs: number;
  _blocked_actions?: Record<string, string>;
  _active_task_ids?: number[];
  _active_run_ids?: number[];
};

type RuntimeAgentInstanceFixture = Record<string, unknown> & {
  id: number;
  worker_id: string;
};

type MockOptions = {
  empty?: boolean;
  errorPath?: string;
  delayPath?: string;
};

type GovernedAssetFixture = Record<string, unknown> & {
  id: number;
  kind: "catalog" | "prompt" | "config" | "template";
  name: string;
  version: string;
  status: string;
  type?: string;
  provider?: string;
  risk_level?: string;
  visibility_level?: string;
  environment?: string | null;
  content_ref?: string;
  schema?: Record<string, unknown>;
  variables_schema?: Record<string, unknown>;
  capabilities?: Record<string, unknown>;
  runtime_requirements?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  _validation?: {
    status?: string;
    validated_at?: string | null;
    issues?: Array<{ code: string; field: string; message: string }>;
  };
  _dependencies?: Array<Record<string, unknown>>;
  _used_by?: Array<Record<string, unknown>>;
  _risk_flags?: string[];
};

const createdAt = "2026-06-05T00:00:00.000Z";
const supportedPackageCapabilities = new Set(["invoke", "stream", "streaming"]);

export function makeAdminCollection<T>(items: T[]): AdminCollectionResponse<T> {
  return {
    items,
    count: items.length,
    request_id: "e2e-request",
  };
}

export function makeDashboardApi(options: { empty?: boolean } = {}): DashboardApiFixture {
  if (options.empty) {
    return {
      agents: [],
      versions: [],
      deployments: [],
      runs: [],
      runtimeOverview: runtimeOverview([], [], [], []),
      humanTasks: makeAdminCollection([]),
      incidents: makeAdminCollection([]),
    };
  }
  const deployments = [
    deployment(10, "ready", 13),
    deployment(11, "degraded", 3),
  ];
  const runs = [
    run(1001, "failed", 10, 4300),
    run(1002, "succeeded", 10, 2100),
    run(1003, "pending", 11, null),
  ];
  const humanTasks = makeAdminCollection([
    {
      id: 101,
      name: "approval-101",
      source: "deployment.promote",
      status: "pending",
      risk: "critical",
      assignee: "platform-approver",
      requester: "deploy-bot",
      risk_reason: "Policy denied direct production promotion.",
      decision_context: { run_id: 77, deployment_id: 13 },
      diff: { desired_status: { from: "paused", to: "active" } },
      decision: {},
      resume_outcome: { status: "waiting", task_id: 101 },
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      created_at: createdAt,
      updated_at: createdAt,
    },
    {
      id: 102,
      name: "approval-102",
      source: "deployment.delete",
      status: "pending",
      risk: "high",
      assignee: "platform-approver",
      requester: "security-bot",
      risk_reason: "Delete requires a second reviewer.",
      decision_context: { run_id: 78, deployment_id: 13 },
      diff: { desired_status: { from: "active", to: "deleted" } },
      decision: {},
      resume_outcome: { status: "waiting", task_id: 102 },
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      created_at: createdAt,
      updated_at: createdAt,
    },
  ]);
  const incidents = makeAdminCollection([
    {
      id: 201,
      name: "provider outage",
      status: "open",
      severity: "critical",
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      created_at: createdAt,
      updated_at: createdAt,
    },
  ]);
  return {
    agents: [
      {
        id: 1,
        name: "support-agent",
        description: "Handles governed support triage.",
        status: "active",
        created_at: createdAt,
      },
    ],
    versions: [
      {
        id: 11,
        agent_id: 1,
        version: "1.0.0",
        package_uri: "oci://registry.local/support-agent:1.0.0",
        framework: "langgraph",
        adapter: "langgraph",
        entrypoint: "agent:create_agent",
        capabilities: { invoke: true, streaming: true, required_secret_refs: ["secret://llm/provider"] },
        manifest: {
          name: "support-agent",
          validation_token: "tok_support_100",
          package_digest: "sha256:111111-support",
          signature: { status: "verified" },
          sbom: { status: "available", format: "spdx-json" },
          runtime: { sandbox_profile: "network-egress-llm-only" },
          required_secret_refs: ["secret://llm/provider"],
        },
        status: "ready",
      },
      {
        id: 12,
        agent_id: 1,
        version: "1.1.0",
        package_uri: "oci://registry.local/support-agent:1.1.0",
        framework: "langgraph",
        adapter: "langgraph",
        entrypoint: "agent:create_agent",
        capabilities: { invoke: true, streaming: true, required_secret_refs: ["secret://llm/provider"] },
        manifest: {
          name: "support-agent",
          validation_token: "tok_support_110",
          package_digest: "sha256:222222-support",
          signature: { status: "verified" },
          sbom: { status: "available", format: "spdx-json" },
          runtime: { sandbox_profile: "network-egress-llm-only" },
          required_secret_refs: ["secret://llm/provider"],
        },
        status: "ready",
      },
    ],
    deployments,
    runs,
    runtimeOverview: runtimeOverview(deployments, runs, humanTasks.items, incidents.items),
    humanTasks,
    incidents,
  };
}

export async function seedEnglishLocale(page: Page): Promise<void> {
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
}

export async function seedConsoleSession(page: Page): Promise<void> {
  await page.addInitScript((sessionOperator) => {
    localStorage.setItem("dimoorun.console.token", "sess_e2e_session");
    localStorage.setItem("dimoorun.console.operator", JSON.stringify(sessionOperator));
    localStorage.setItem("dimoorun.console.scope", JSON.stringify(sessionOperator.allowed_scopes[0]));
  }, e2eOperator);
}

export async function forceOfflineMode(page: Page): Promise<void> {
  await page.addInitScript(() => {
    sessionStorage.setItem("dimoorun.console.apiBaseUrlOverride", "");
  });
}

export async function installConsoleApiMocks(
  page: Page,
  options: MockOptions = {},
): Promise<void> {
  await page.addInitScript(() => {
    sessionStorage.setItem("dimoorun.console.apiBaseUrlOverride", `${window.location.origin}/mock-api`);
  });
  const api = makeDashboardApi({ empty: options.empty });
  const runtimeWorkers = makeRuntimeWorkers();
  const runtimeAgentInstances = makeRuntimeAgentInstances();
  let capturedRunDataset = false;
  const incidentTimeline: Array<Record<string, unknown>> = [];
  const incidentDeliveries: Array<Record<string, unknown>> = [];
  const publishedSurfaces: Array<Record<string, unknown>> = [
    {
      id: 501,
      name: "support ingress",
      deployment_id: 10,
      type: "http",
      status: "active",
      created_at: createdAt,
    },
  ];
  const ingressRoutes: Array<Record<string, unknown>> = [
    {
      id: 701,
      name: "support triage",
      surface_id: 501,
      path: "/support/triage",
      auth_mode: "api_key",
      custom_domain: "support.example.com",
      status: "active",
      created_at: createdAt,
    },
  ];
  const publishedRequestLogs: Array<Record<string, unknown>> = [];
  const publishedRolloutHistory: Array<Record<string, unknown>> = [
    {
      operation: "publish",
      version: 1,
      audit_preview: { action: "published_surface.publish" },
      created_at: createdAt,
    },
  ];
  const compatibilityAssistants: Array<Record<string, unknown>> = [];
  const compatibilityThreads: Array<Record<string, unknown>> = [];
  const compatibilityRuns: Array<Record<string, unknown>> = [];
  const governedAssets: GovernedAssetFixture[] = makeGovernedAssets();
  const identityPermissions: Array<Record<string, unknown>> = [
    { id: 1, code: "admin:read", resource: "admin", action: "read", status: "active" },
    { id: 2, code: "identity:role:write", resource: "identity:role", action: "write", status: "active" },
    { id: 3, code: "identity:operator:write", resource: "identity:operator", action: "write", status: "active" },
    { id: 4, code: "identity:service-account:write", resource: "identity:service_account", action: "write", status: "active" },
    { id: 5, code: "run:read", resource: "run", action: "read", status: "active" },
  ];
  const identityRoles: Array<Record<string, unknown>> = [
    {
      id: 11,
      name: "platform_admin",
      description: "Primary operator role",
      status: "active",
      permissions: [
        "admin:read",
        "identity:role:write",
        "identity:operator:write",
        "identity:service-account:write",
        "run:read",
      ],
    },
    {
      id: 12,
      name: "runtime_operator",
      description: "Runtime monitoring role",
      status: "active",
      permissions: ["run:read"],
    },
  ];
  const identityOperators: Array<Record<string, unknown>> = [
    {
      id: 1,
      email: "admin@local.dimoorun",
      name: "E2E Operator",
      roles: ["platform_admin"],
      permissions: ["admin:read", "identity:role:write", "identity:operator:write", "identity:service-account:write", "run:read"],
      allowed_scopes: [e2eScope],
      status: "active",
      created_at: createdAt,
      updated_at: createdAt,
      last_login_at: createdAt,
      password_changed_at: createdAt,
      active_sessions: [
        {
          id: 101,
          operator_id: 1,
          status: "active",
          last_used_at: createdAt,
          expires_at: "2026-12-31T00:00:00.000Z",
          revoked_at: null,
          revoke_reason: null,
          ip_address: "127.0.0.1",
          user_agent: "Playwright Chrome",
        },
      ],
      api_keys_created: [
        {
          id: 601,
          name: "created-for-runtime",
          owner_id: 301,
          scopes: ["run:read"],
          status: "active",
          created_at: createdAt,
          expires_at: "2026-12-31T00:00:00.000Z",
        },
      ],
      recent_audit_actions: [
        {
          id: 9001,
          action: "identity.role.permissions.apply",
          resource_type: "console_role",
          resource_id: 11,
          result: "allowed",
          request_id: "req_identity_preview",
          created_at: createdAt,
        },
      ],
    },
    {
      id: 2,
      email: "reviewer@local.dimoorun",
      name: "Reviewer",
      roles: ["runtime_operator"],
      permissions: ["run:read"],
      allowed_scopes: [e2eScope],
      status: "active",
      created_at: createdAt,
      updated_at: createdAt,
      last_login_at: createdAt,
      password_changed_at: createdAt,
      active_sessions: [
        {
          id: 201,
          operator_id: 2,
          status: "active",
          last_used_at: createdAt,
          expires_at: "2026-12-31T00:00:00.000Z",
          revoked_at: null,
          revoke_reason: null,
          ip_address: "10.0.0.2",
          user_agent: "Chrome",
        },
        {
          id: 202,
          operator_id: 2,
          status: "active",
          last_used_at: createdAt,
          expires_at: "2026-12-31T00:00:00.000Z",
          revoked_at: null,
          revoke_reason: null,
          ip_address: "10.0.0.3",
          user_agent: "Chrome",
        },
      ],
      api_keys_created: [],
      recent_audit_actions: [],
    },
  ];
  const serviceAccounts: Array<Record<string, unknown>> = [
    {
      id: 301,
      tenant_id: 1,
      project_id: 1,
      name: "ci-deployer",
      permissions: ["run:read", "identity:service-account:write"],
      status: "active",
      created_by: "1",
      created_at: createdAt,
      last_used_at: createdAt,
      api_keys: [
        {
          id: 701,
          name: "ci-primary",
          key_prefix: "dmr_ci",
          scopes: ["run:read"],
          status: "active",
          last_used_at: createdAt,
          expires_at: "2026-12-31T00:00:00.000Z",
          scope_diff: {
            added: [],
            removed: ["identity:service-account:write"],
            unchanged: ["run:read"],
          },
        },
      ],
      dependent_deployments: [
        {
          deployment_id: 10,
          agent_id: 1,
          environment: "local",
          published_surfaces: [{ id: 501, name: "support ingress", status: "active" }],
        },
      ],
    },
  ];
  const platformScopedSettings: Array<Record<string, unknown>> = [
    {
      id: 801,
      tenant_id: 1,
      project_id: null,
      environment: null,
      scope_kind: "organization",
      setting_key: "defaults",
      config: {
        default_runtime_mode: "governed",
        default_queue: "default",
        default_artifact_retention_days: 30,
      },
      metadata: { seeded: true },
      updated_at: createdAt,
    },
    {
      id: 802,
      tenant_id: 1,
      project_id: 1,
      environment: null,
      scope_kind: "project",
      setting_key: "defaults",
      config: {
        default_model_gateway: "default",
        default_secret_provider: "external",
        change_review_policy: "two_person",
      },
      metadata: { seeded: true },
      updated_at: createdAt,
    },
    {
      id: 803,
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      scope_kind: "environment",
      setting_key: "defaults",
      config: {
        default_deployment_strategy: "rolling",
        freeze_writes: false,
        default_route_visibility: "internal",
      },
      metadata: { seeded: true },
      updated_at: createdAt,
    },
  ];
  const providerStatuses: Array<Record<string, unknown>> = [
    { provider: "postgres", status: "degraded", summary: "sqlite:///tmp/dimoorun.db", reason: "SQLite is suitable for local development only." },
    { provider: "redis", status: "healthy", summary: "redis://localhost:6379/0", reason: "Queue backend uses Redis." },
    { provider: "object_store", status: "degraded", summary: "local:dimoorun-artifacts", reason: "Artifacts are still stored locally." },
    { provider: "secret_provider", status: "offline", summary: "memory", reason: "0 scoped secret reference(s) registered." },
    { provider: "model_gateway", status: "healthy", summary: "newapi", reason: "1 active model gateway record(s)." },
    { provider: "webhook_transport", status: "degraded", summary: "webhook subscriptions", reason: "0 subscription(s) configured." },
    { provider: "notification_transport", status: "degraded", summary: "notification channels", reason: "0 channel(s) configured." },
    { provider: "observability_exporter", status: "healthy", summary: "otlp", reason: "1 exporter record(s) configured." },
  ];
  const observabilityExporters: Array<Record<string, unknown>> = [
    {
      id: 1401,
      name: "primary-otel",
      exporter_type: "otlp",
      target_ref: "http://otel.internal:4318",
      target_ref_redacted: "http://otel:4318",
      status: "active",
      metadata: { blocked_reason: null },
      tenant_id: 1,
      project_id: 1,
      created_at: createdAt,
      updated_at: createdAt,
    },
  ];
  const semanticStoreProviders: Array<Record<string, unknown>> = [
    {
      id: 1501,
      name: "tenant-memory",
      embedding_model: "text-embedding-3-large",
      connection_ref: "postgresql://vector-store",
      status: "active",
      metadata: { index_coverage: { runs: 92, artifacts: 81 } },
      tenant_id: 1,
      project_id: 1,
      created_at: createdAt,
      updated_at: createdAt,
    },
  ];
  const sandboxPolicies: Array<Record<string, unknown>> = [
    {
      id: 1601,
      name: "restricted-egress",
      isolation_level: "container",
      network_policy: "deny_all",
      filesystem_policy: "read_only",
      status: "active",
      metadata: { affected_surfaces: ["published_surfaces", "replay_jobs"] },
      tenant_id: 1,
      project_id: 1,
      created_at: createdAt,
      updated_at: createdAt,
    },
  ];
  const containerPoolPolicies: Array<Record<string, unknown>> = [
    {
      id: 1701,
      name: "default-pool",
      max_containers: 6,
      cpu_limit: "1000m",
      memory_limit: "1Gi",
      idle_timeout_seconds: 300,
      status: "active",
      metadata: { warm_capacity: 2, worker_pools: ["default", "gpu-burst"] },
      tenant_id: 1,
      project_id: 1,
      created_at: createdAt,
      updated_at: createdAt,
    },
  ];
  const notificationChannels: Array<Record<string, unknown>> = [
    {
      id: 901,
      type: "webhook",
      target_ref: "slack:#ops-finops",
      status: "active",
      metadata: {},
      created_at: createdAt,
      updated_at: createdAt,
      tenant_id: 1,
      project_id: 1,
      environment: "local",
    },
    {
      id: 902,
      type: "webhook",
      target_ref: "slack:#locked-finance",
      status: "active",
      metadata: {},
      created_at: createdAt,
      updated_at: createdAt,
      tenant_id: 1,
      project_id: 1,
      environment: "local",
    },
  ];
  const alertRules: Array<Record<string, unknown>> = [];
  const webhookSubscriptions: Array<Record<string, unknown>> = [
    {
      id: 1101,
      name: "runtime-events",
      target_url: "https://hooks.example.test/runtime",
      event_types: ["run.failed", "incident.created"],
      retry_policy: "3 attempts",
      secret_ref: "secret:runtime/webhook",
      status: "active",
      last_delivery_status: "sent",
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      created_at: createdAt,
      updated_at: createdAt,
    },
  ];
  const costBudgetPolicies: Array<Record<string, unknown>> = [
    {
      id: 951,
      name: "prod-spend-guardrail",
      environment: "local",
      scope_type: "deployment",
      scope_ref: "10",
      threshold_usd: 1.5,
      reset_window: "monthly",
      channel_id: 901,
      action_mode: "require_approval",
      status: "active",
      metadata: {},
      created_at: createdAt,
      updated_at: createdAt,
      tenant_id: 1,
      project_id: 1,
    },
  ];
  const costSavedViews: Array<Record<string, unknown>> = [
    {
      id: 941,
      name: "provider-regressions",
      environment: "local",
      group_by: "provider",
      window_days: 30,
      filters: {},
      status: "active",
      metadata: {},
      created_at: createdAt,
      updated_at: createdAt,
      tenant_id: 1,
      project_id: 1,
    },
  ];
  const scheduledRuns: Array<Record<string, unknown>> = [
    {
      id: 1201,
      name: "nightly-eval",
      status: "active",
      schedule_type: "interval",
      cron_expression: null,
      interval_minutes: 30,
      timezone: "UTC",
      next_fire_time: "2026-06-13T01:30:00.000Z",
      deployment_id: 10,
      input_template: { message: "scheduled" },
      backfill_policy: "latest",
      missed_run_policy: "run_once",
      last_triggered_at: null,
      last_run_id: null,
      last_task_id: null,
      last_run_status: null,
      last_task_status: null,
      last_trigger_source: null,
      trigger_count: 0,
      pause_reason: null,
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      created_at: createdAt,
      updated_at: createdAt,
      metadata: {},
    },
    {
      id: 1202,
      name: "weekday-backfill",
      status: "paused",
      schedule_type: "cron",
      cron_expression: "0 9 * * 1-5",
      interval_minutes: null,
      timezone: "Asia/Shanghai",
      next_fire_time: "2026-06-13T09:00:00.000Z",
      deployment_id: 11,
      input_template: { message: "weekday" },
      backfill_policy: "none",
      missed_run_policy: "catch_up",
      last_triggered_at: "2026-06-12T09:00:00.000Z",
      last_run_id: 1002,
      last_task_id: 2002,
      last_run_status: "succeeded",
      last_task_status: "succeeded",
      last_trigger_source: "automatic",
      trigger_count: 4,
      pause_reason: "maintenance",
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      created_at: createdAt,
      updated_at: createdAt,
      metadata: {},
    },
  ];
  const batchRuns: Array<Record<string, unknown>> = [
    {
      id: 1301,
      name: "backfill-failed-runs",
      status: "partial_failed",
      deployment_id: 10,
      dataset_id: null,
      concurrency: 2,
      retry_policy: { max_attempts: 2 },
      cancel_policy: "best_effort",
      partial_failure_policy: "continue",
      artifact_output_ref: null,
      progress_summary: {
        total_items: 3,
        queued_items: 1,
        running_items: 0,
        retrying_items: 1,
        failed_items: 1,
        dead_letter_items: 0,
        cancelled_items: 0,
        completed_items: 0,
        terminal_items: 1,
      },
      items: [
        { index: 0, status: "queued", input: { message: "one" }, run_id: 4001, task_id: 5001 },
        {
          index: 1,
          status: "failed",
          input: null,
          run_id: null,
          task_id: null,
          error_code: "batch_item_invalid",
          message: "Batch input item must be an object.",
        },
        { index: 2, status: "retrying", input: { message: "two" }, run_id: 4002, task_id: 5002 },
      ],
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      created_at: createdAt,
      updated_at: createdAt,
    },
  ];
  const platformSnapshot = {
    runtime_mode: "production",
    runtime_environment: "local",
    database_mode: "postgresql",
    queue_backend: "redis",
    object_store: { backend: "s3", endpoint_url: "https://s3.example.test", bucket: "dimoorun-artifacts" },
    secret_provider: { provider: "vault", default_scope: "external" },
    model_gateway_provider: { provider: "newapi", default_gateway: "default" },
    artifact_retention: { days: 30, backend: "s3" },
    trace_retention: { days: 14, exporters: ["otlp"] },
    cors: { origins: ["https://console.example.com"], allow_credentials: true },
    runtime_write_protected: true,
    production_safety: { status: "safe", warnings: [] },
    scope_defaults: platformScopedSettings,
    danger_state: { freeze_writes: false, updated_at: createdAt },
  };
  let nextCompatibilityRunId = 3101;
  let nextCompatibilityTaskId = 4101;
  await page.route("**/mock-api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/mock-api", "");
    if (path === options.delayPath) {
      await new Promise((resolve) => setTimeout(resolve, 750));
    }
    if (path === options.errorPath) {
      return fulfillError(route);
    }
    if (path === "/v1/auth/login" && route.request().method() === "POST") {
      return fulfillAuthLogin(route);
    }
    if (path === "/v1/auth/me" && route.request().method() === "GET") {
      return fulfillJson(route, { operator: e2eOperator, request_id: "e2e-request" });
    }
    if (path === "/v1/auth/logout" && route.request().method() === "POST") {
      return fulfillJson(route, { ok: true });
    }
    if (path === "/v1/runtime/metrics/summary" && route.request().method() === "GET") {
      return fulfillJson(route, runtimeMetricsSummary(api, runtimeWorkers, api.incidents.items));
    }
    if (path === "/v1/agents" && route.request().method() === "POST") {
      return fulfillJson(route, createAgentResponse(route, api));
    }
    const agentMutationMatch = path.match(/^\/v1\/agents\/(\d+)$/);
    if (agentMutationMatch && route.request().method() === "PATCH") {
      return fulfillJson(route, updateAgentResponse(route, api, Number(agentMutationMatch[1])));
    }
    if (agentMutationMatch && route.request().method() === "DELETE") {
      return fulfillJson(route, archiveAgentResponse(api, Number(agentMutationMatch[1])));
    }
    const agentVersionCreateMatch = path.match(/^\/v1\/agents\/(\d+)\/versions$/);
    if (agentVersionCreateMatch && route.request().method() === "POST") {
      return fulfillAgentVersionCreate(route, api, Number(agentVersionCreateMatch[1]));
    }
    const agentVersionMutationMatch = path.match(/^\/v1\/agents\/(\d+)\/versions\/([^/]+)$/);
    if (agentVersionMutationMatch && route.request().method() === "PATCH") {
      return fulfillJson(
        route,
        updateAgentVersionResponse(
          route,
          api,
          Number(agentVersionMutationMatch[1]),
          decodeURIComponent(agentVersionMutationMatch[2]),
        ),
      );
    }
    if (agentVersionMutationMatch && route.request().method() === "DELETE") {
      return fulfillJson(
        route,
        archiveAgentVersionResponse(
          api,
          Number(agentVersionMutationMatch[1]),
          decodeURIComponent(agentVersionMutationMatch[2]),
        ),
      );
    }
    if (path === "/v1/deployments" && route.request().method() === "POST") {
      return fulfillJson(route, createDeploymentResponse(route, api));
    }
    const deploymentMutationMatch = path.match(/^\/v1\/deployments\/(\d+)$/);
    if (deploymentMutationMatch && route.request().method() === "PATCH") {
      return fulfillJson(route, updateDeploymentResponse(route, api, Number(deploymentMutationMatch[1])));
    }
    if (deploymentMutationMatch && route.request().method() === "DELETE") {
      return fulfillJson(route, archiveDeploymentResponse(api, Number(deploymentMutationMatch[1])));
    }
    const deploymentTaskMatch = path.match(/^\/v1\/deployments\/(\d+)\/tasks$/);
    if (deploymentTaskMatch && route.request().method() === "POST") {
      return fulfillJson(route, createDeploymentTaskResponse(route, api, Number(deploymentTaskMatch[1])));
    }
    if (path === "/v1/console/identity/role-matrix" && route.request().method() === "GET") {
      return fulfillJson(route, {
        items: identityRoles,
        permissions: identityPermissions,
        request_id: "e2e-request",
      });
    }
    if (path === "/v1/console/settings/platform" && route.request().method() === "GET") {
      return fulfillJson(route, { item: platformSnapshot, request_id: "e2e-request" });
    }
    if (path === "/v1/console/settings/providers" && route.request().method() === "GET") {
      return fulfillJson(route, {
        items: providerStatuses,
        count: providerStatuses.length,
        request_id: "e2e-request",
      });
    }
    if (path === "/v1/observability/exporters" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(observabilityExporters));
    }
    if (path === "/v1/semantic-store/providers" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(semanticStoreProviders));
    }
    if (path === "/v1/sandbox/policies" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(sandboxPolicies));
    }
    if (path === "/v1/container-pool/policies" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(containerPoolPolicies));
    }
    if (path === "/v1/console/costs/summary" && route.request().method() === "GET") {
      return fulfillJson(route, costSummaryResponse(url));
    }
    if (path === "/v1/console/costs/anomalies" && route.request().method() === "GET") {
      return fulfillJson(route, costAnomaliesResponse());
    }
    if (path === "/v1/schedules/preview" && route.request().method() === "POST") {
      return fulfillSchedulePreview(route);
    }
    if (path === "/v1/schedules" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(scheduledRuns));
    }
    if (path === "/v1/schedules" && route.request().method() === "POST") {
      return fulfillScheduleCreate(route, scheduledRuns);
    }
    const scheduleDetailMatch = path.match(/^\/v1\/schedules\/(\d+)$/);
    if (scheduleDetailMatch && route.request().method() === "GET") {
      return fulfillScheduledRunDetail(route, scheduledRuns, Number(scheduleDetailMatch[1]));
    }
    const scheduleActionMatch = path.match(/^\/v1\/schedules\/(\d+)\/(pause|resume|trigger)$/);
    if (scheduleActionMatch && route.request().method() === "POST") {
      return fulfillScheduleAction(
        route,
        scheduledRuns,
        Number(scheduleActionMatch[1]),
        scheduleActionMatch[2],
      );
    }
    if (path === "/v1/batch-runs" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(batchRuns));
    }
    if (path === "/v1/batch-runs" && route.request().method() === "POST") {
      return fulfillBatchRunCreate(route, batchRuns);
    }
    const batchDetailMatch = path.match(/^\/v1\/batch-runs\/(\d+)$/);
    if (batchDetailMatch && route.request().method() === "GET") {
      return fulfillBatchRunDetail(route, batchRuns, Number(batchDetailMatch[1]));
    }
    const batchCancelMatch = path.match(/^\/v1\/batch-runs\/(\d+)\/cancel$/);
    if (batchCancelMatch && route.request().method() === "POST") {
      return fulfillBatchRunCancel(route, batchRuns, Number(batchCancelMatch[1]));
    }
    if (path === "/v1/console/costs/budgets/preview" && route.request().method() === "POST") {
      return fulfillBudgetPreview(route);
    }
    const savedCostViewMatch = path.match(/^\/v1\/console\/costs\/views\/(\d+)$/);
    if (savedCostViewMatch && route.request().method() === "GET") {
      return fulfillSavedCostView(route, costSavedViews, Number(savedCostViewMatch[1]));
    }
    const savedBudgetPreviewMatch = path.match(/^\/v1\/console\/costs\/budgets\/(\d+)\/preview$/);
    if (savedBudgetPreviewMatch && route.request().method() === "GET") {
      return fulfillSavedBudgetPreview(route, costBudgetPolicies, notificationChannels, Number(savedBudgetPreviewMatch[1]));
    }
    if (path === "/v1/console/settings/scoped-defaults" && route.request().method() === "GET") {
      return fulfillJson(route, {
        items: platformScopedSettings,
        count: platformScopedSettings.length,
        request_id: "e2e-request",
      });
    }
    const scopedSettingsMatch = path.match(/^\/v1\/console\/settings\/scoped-defaults\/(organization|project|environment)$/);
    if (scopedSettingsMatch && route.request().method() === "POST") {
      return fulfillPlatformScopedSettings(route, platformScopedSettings, platformSnapshot, scopedSettingsMatch[1]);
    }
    if (path === "/v1/console/settings/danger/preflight" && route.request().method() === "POST") {
      return fulfillPlatformDangerPreflight(route, providerStatuses, platformScopedSettings);
    }
    const dangerActionMatch = path.match(/^\/v1\/console\/settings\/danger\/actions\/([^/]+)$/);
    if (dangerActionMatch && route.request().method() === "POST") {
      return fulfillPlatformDangerAction(route, dangerActionMatch[1], platformScopedSettings, platformSnapshot);
    }
    const exporterValidateMatch = path.match(/^\/v1\/console\/settings\/observability-exporters\/(\d+)\/validate$/);
    if (exporterValidateMatch && route.request().method() === "POST") {
      return fulfillObservabilityExporterValidation(route, observabilityExporters, Number(exporterValidateMatch[1]));
    }
    const semanticValidateMatch = path.match(/^\/v1\/console\/settings\/semantic-store-providers\/(\d+)\/validate$/);
    if (semanticValidateMatch && route.request().method() === "POST") {
      return fulfillSemanticStoreValidation(route, semanticStoreProviders, Number(semanticValidateMatch[1]));
    }
    const sandboxPreviewMatch = path.match(/^\/v1\/console\/settings\/sandbox-policies\/(\d+)\/preview$/);
    if (sandboxPreviewMatch && route.request().method() === "POST") {
      return fulfillSandboxPolicyPreview(route, sandboxPolicies, Number(sandboxPreviewMatch[1]));
    }
    const containerEstimateMatch = path.match(/^\/v1\/console\/settings\/container-pool-policies\/(\d+)\/estimate$/);
    if (containerEstimateMatch && route.request().method() === "POST") {
      return fulfillContainerPoolEstimate(route, containerPoolPolicies, Number(containerEstimateMatch[1]));
    }
    const rolePreviewMatch = path.match(/^\/v1\/identity\/workflows\/roles\/(\d+)\/(preview|apply)$/);
    if (rolePreviewMatch && route.request().method() === "POST") {
      return fulfillIdentityRolePreview(route, identityRoles, identityOperators, Number(rolePreviewMatch[1]), rolePreviewMatch[2]);
    }
    const operatorDetailMatch = path.match(/^\/v1\/console\/identity\/operators\/(\d+)$/);
    if (operatorDetailMatch && route.request().method() === "GET") {
      return fulfillJson(route, operatorAccessDetailResponse(identityOperators, Number(operatorDetailMatch[1])));
    }
    const revokeSessionMatch = path.match(/^\/v1\/identity\/workflows\/operators\/(\d+)\/sessions\/(\d+)\/revoke$/);
    if (revokeSessionMatch && route.request().method() === "POST") {
      return fulfillIdentitySessionRevoke(route, identityOperators, Number(revokeSessionMatch[1]), Number(revokeSessionMatch[2]));
    }
    if (path === "/v1/identity/workflows/sessions/revoke-self" && route.request().method() === "POST") {
      return fulfillJson(route, { ok: true, request_id: "e2e-request" });
    }
    const serviceAccountDetailMatch = path.match(/^\/v1\/console\/identity\/service-accounts\/(\d+)$/);
    if (serviceAccountDetailMatch && route.request().method() === "GET") {
      return fulfillJson(route, serviceAccountDetailResponse(serviceAccounts, Number(serviceAccountDetailMatch[1])));
    }
    if (path === "/v1/identity/service-accounts" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(serviceAccounts.map(serviceAccountSummary)));
    }
    if (path === "/v1/notifications/channels" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(notificationChannels));
    }
    if (path === "/v1/alerts/rules" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(alertRules));
    }
    if (path === "/v1/alerts/rules" && route.request().method() === "POST") {
      const body = parseRequestBody(route);
      const item = {
        id: nextNumericId(alertRules as Array<{ id: number }>),
        name: String(body.name || "alert-rule"),
        signal: String(body.signal || "runtime.error_rate"),
        threshold: Number(body.threshold || 1),
        channel_id: Number(body.channel_id || 901),
        status: "active",
        last_triggered_at: null,
        tenant_id: 1,
        project_id: 1,
        environment: "local",
        created_at: createdAt,
        updated_at: createdAt,
      };
      alertRules.unshift(item);
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        json: { item, request_id: "e2e-request" },
      });
    }
    const alertTestMatch = path.match(/^\/v1\/alerts\/rules\/(\d+)\/test$/);
    if (alertTestMatch && route.request().method() === "POST") {
      return fulfillJson(route, {
        status: "ready",
        rule_id: Number(alertTestMatch[1]),
        delivery_attempt: {
          id: 7001,
          status: "sent",
          visible_to_operator: true,
          redacted_payload: { message: "Synthetic alert route probe" },
        },
        request_id: "e2e-request",
      });
    }
    if (path === "/v1/webhooks/subscriptions" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(webhookSubscriptions));
    }
    const webhookValidateMatch = path.match(/^\/v1\/webhooks\/subscriptions\/(\d+)\/validate$/);
    if (webhookValidateMatch && route.request().method() === "POST") {
      return fulfillJson(route, {
        status: "ready",
        subscription_id: Number(webhookValidateMatch[1]),
        validation: { secret_ref: "[REDACTED]", target_reachable: true },
        last_delivery: { id: 7101, status: "sent", visible_to_operator: true },
        request_id: "e2e-request",
      });
    }
    if (path === "/v1/costs/budgets" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(costBudgetPolicies));
    }
    if (path === "/v1/costs/views" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(activeCostSavedViews(costSavedViews)));
    }
    if (path === "/v1/costs/views" && route.request().method() === "POST") {
      return fulfillCostSavedViewCreate(route, costSavedViews);
    }
    if (path === "/v1/costs/budgets" && route.request().method() === "POST") {
      return fulfillCostBudgetCreate(route, costBudgetPolicies, notificationChannels);
    }
    const costSavedViewMutationMatch = path.match(/^\/v1\/costs\/views\/(\d+)$/);
    if (costSavedViewMutationMatch && route.request().method() === "PATCH") {
      return fulfillCostSavedViewUpdate(route, costSavedViews, Number(costSavedViewMutationMatch[1]));
    }
    if (costSavedViewMutationMatch && route.request().method() === "DELETE") {
      return fulfillJson(route, archiveCostSavedView(costSavedViews, Number(costSavedViewMutationMatch[1])));
    }
    const costBudgetMutationMatch = path.match(/^\/v1\/costs\/budgets\/(\d+)$/);
    if (costBudgetMutationMatch && route.request().method() === "PATCH") {
      return fulfillCostBudgetUpdate(route, costBudgetPolicies, Number(costBudgetMutationMatch[1]));
    }
    if (costBudgetMutationMatch && route.request().method() === "DELETE") {
      return fulfillJson(route, archiveCostBudgetPolicy(costBudgetPolicies, Number(costBudgetMutationMatch[1])));
    }
    const serviceAccountPatchMatch = path.match(/^\/v1\/identity\/service-accounts\/(\d+)$/);
    if (serviceAccountPatchMatch && route.request().method() === "PATCH") {
      return fulfillIdentityServiceAccountPatch(route, serviceAccounts, Number(serviceAccountPatchMatch[1]));
    }
    const serviceAccountCreateKeyMatch = path.match(/^\/v1\/identity\/service-accounts\/(\d+)\/api-keys$/);
    if (serviceAccountCreateKeyMatch && route.request().method() === "POST") {
      return fulfillIdentityCreateApiKey(route, serviceAccounts, Number(serviceAccountCreateKeyMatch[1]));
    }
    const serviceAccountKeyActionMatch = path.match(/^\/v1\/identity\/service-accounts\/(\d+)\/api-keys\/(\d+)\/(disable|enable)$/);
    if (serviceAccountKeyActionMatch && route.request().method() === "POST") {
      return fulfillIdentityApiKeyAction(
        route,
        serviceAccounts,
        Number(serviceAccountKeyActionMatch[1]),
        Number(serviceAccountKeyActionMatch[2]),
        serviceAccountKeyActionMatch[3],
      );
    }
    const serviceAccountRotateMatch = path.match(/^\/v1\/identity\/workflows\/service-accounts\/(\d+)\/api-keys\/(\d+)\/rotate$/);
    if (serviceAccountRotateMatch && route.request().method() === "POST") {
      return fulfillIdentityRotateKey(route, serviceAccounts, Number(serviceAccountRotateMatch[1]), Number(serviceAccountRotateMatch[2]));
    }
    const serviceAccountExpireMatch = path.match(/^\/v1\/identity\/workflows\/service-accounts\/(\d+)\/api-keys\/(\d+)\/force-expire$/);
    if (serviceAccountExpireMatch && route.request().method() === "POST") {
      return fulfillIdentityExpireKey(route, serviceAccounts, Number(serviceAccountExpireMatch[1]), Number(serviceAccountExpireMatch[2]));
    }
    if (path === "/v1/console/workers" && route.request().method() === "GET") {
      return fulfillJson(route, makeRuntimeWorkerCollection(runtimeWorkers));
    }
    const workerDetailMatch = path.match(/^\/v1\/console\/workers\/([^/]+)$/);
    if (workerDetailMatch && route.request().method() === "GET") {
      return fulfillJson(route, runtimeWorkerDetailResponse(runtimeWorkers, decodeURIComponent(workerDetailMatch[1])));
    }
    const workerActionMatch = path.match(/^\/v1\/console\/workers\/([^/]+)\/(drain|undrain|quarantine|restart-request)$/);
    if (workerActionMatch && route.request().method() === "POST") {
      return fulfillRuntimeWorkerAction(
        route,
        runtimeWorkers,
        decodeURIComponent(workerActionMatch[1]),
        workerActionMatch[2],
      );
    }
    if (path === "/v1/console/agent-instances" && route.request().method() === "GET") {
      return fulfillJson(route, makeRuntimeAgentInstanceCollection(runtimeAgentInstances));
    }
    const instanceDetailMatch = path.match(/^\/v1\/console\/agent-instances\/(\d+)$/);
    if (instanceDetailMatch && route.request().method() === "GET") {
      return fulfillJson(route, runtimeAgentInstanceDetailResponse(runtimeAgentInstances, Number(instanceDetailMatch[1])));
    }
    if (path === "/v1/console/capacity" && route.request().method() === "GET") {
      return fulfillJson(route, runtimeCapacitySummaryResponse(runtimeWorkers));
    }
    if (path === "/v1/published-surfaces" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(publishedSurfaces));
    }
    if (path === "/v1/catalog/items" && route.request().method() === "GET") {
      try {
        return fulfillJson(route, makeAdminCollection(listGovernedAssets(governedAssets, "catalog")));
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    if (path === "/v1/catalog/items" && route.request().method() === "POST") {
      try {
        return fulfillGovernedAssetCreate(route, governedAssets, "catalog");
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    if (path === "/v1/assets/prompts" && route.request().method() === "GET") {
      try {
        return fulfillJson(route, makeAdminCollection(listGovernedAssets(governedAssets, "prompt")));
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    if (path === "/v1/assets/prompts" && route.request().method() === "POST") {
      try {
        return fulfillGovernedAssetCreate(route, governedAssets, "prompt");
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    if (path === "/v1/assets/configs" && route.request().method() === "GET") {
      try {
        return fulfillJson(route, makeAdminCollection(listGovernedAssets(governedAssets, "config")));
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    if (path === "/v1/assets/configs" && route.request().method() === "POST") {
      try {
        return fulfillGovernedAssetCreate(route, governedAssets, "config");
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    if (path === "/v1/assets/templates" && route.request().method() === "GET") {
      try {
        return fulfillJson(route, makeAdminCollection(listGovernedAssets(governedAssets, "template")));
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    if (path === "/v1/assets/templates" && route.request().method() === "POST") {
      try {
        return fulfillGovernedAssetCreate(route, governedAssets, "template");
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    const catalogDetailMatch = path.match(/^\/v1\/catalog\/items\/(\d+)$/);
    if (catalogDetailMatch && route.request().method() === "GET") {
      return fulfillGovernedAssetDetail(route, governedAssets, "catalog", Number(catalogDetailMatch[1]));
    }
    const catalogActionMatch = path.match(/^\/v1\/catalog\/items\/(\d+)\/(validate|approve|publish|deprecate|archive|rollback)$/);
    if (catalogActionMatch && route.request().method() === "POST") {
      return fulfillGovernedAssetAction(route, governedAssets, "catalog", Number(catalogActionMatch[1]), catalogActionMatch[2]);
    }
    const promptDetailMatch = path.match(/^\/v1\/assets\/prompts\/(\d+)$/);
    if (promptDetailMatch && route.request().method() === "GET") {
      try {
        return fulfillGovernedAssetDetail(route, governedAssets, "prompt", Number(promptDetailMatch[1]));
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    const promptActionMatch = path.match(/^\/v1\/assets\/prompts\/(\d+)\/(validate|approve|publish|deprecate|archive|rollback)$/);
    if (promptActionMatch && route.request().method() === "POST") {
      try {
        return fulfillGovernedAssetAction(route, governedAssets, "prompt", Number(promptActionMatch[1]), promptActionMatch[2]);
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    const configDetailMatch = path.match(/^\/v1\/assets\/configs\/(\d+)$/);
    if (configDetailMatch && route.request().method() === "GET") {
      return fulfillGovernedAssetDetail(route, governedAssets, "config", Number(configDetailMatch[1]));
    }
    const configActionMatch = path.match(/^\/v1\/assets\/configs\/(\d+)\/(validate|approve|publish|deprecate|archive|rollback)$/);
    if (configActionMatch && route.request().method() === "POST") {
      return fulfillGovernedAssetAction(route, governedAssets, "config", Number(configActionMatch[1]), configActionMatch[2]);
    }
    const templateDetailMatch = path.match(/^\/v1\/assets\/templates\/(\d+)$/);
    if (templateDetailMatch && route.request().method() === "GET") {
      return fulfillGovernedAssetDetail(route, governedAssets, "template", Number(templateDetailMatch[1]));
    }
    const templateActionMatch = path.match(/^\/v1\/assets\/templates\/(\d+)\/(validate|approve|publish|deprecate|archive|rollback)$/);
    if (templateActionMatch && route.request().method() === "POST") {
      return fulfillGovernedAssetAction(route, governedAssets, "template", Number(templateActionMatch[1]), templateActionMatch[2]);
    }
    if (path === "/v1/ingress-routes" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(ingressRoutes));
    }
    if (path === "/v1/console/compatibility/langgraph/assistants" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(compatibilityAssistants));
    }
    if (path === "/v1/console/compatibility/langgraph/assistants" && route.request().method() === "POST") {
      return fulfillJson(route, compatibilityAssistantResponse(route, compatibilityAssistants));
    }
    const compatibilityAssistantMatch = path.match(/^\/v1\/console\/compatibility\/langgraph\/assistants\/([^/]+)$/);
    if (compatibilityAssistantMatch && route.request().method() === "GET") {
      return fulfillJson(route, compatibilityGetAssistantResponse(compatibilityAssistants, compatibilityAssistantMatch[1]));
    }
    if (path === "/v1/console/compatibility/langgraph/threads" && route.request().method() === "POST") {
      return fulfillJson(route, compatibilityThreadResponse(route, compatibilityThreads));
    }
    const compatibilityThreadMatch = path.match(/^\/v1\/console\/compatibility\/langgraph\/threads\/([^/]+)$/);
    if (compatibilityThreadMatch && route.request().method() === "GET") {
      return fulfillJson(route, compatibilityGetThreadResponse(compatibilityThreads, compatibilityThreadMatch[1]));
    }
    const compatibilityRunMatch = path.match(/^\/v1\/console\/compatibility\/langgraph\/threads\/([^/]+)\/runs$/);
    if (compatibilityRunMatch && route.request().method() === "POST") {
      return fulfillJson(
        route,
        compatibilityRunResponse(
          route,
          compatibilityRunMatch[1],
          compatibilityAssistants,
          compatibilityRuns,
          nextCompatibilityRunId++,
          nextCompatibilityTaskId++,
        ),
      );
    }
    const compatibilityStreamMatch = path.match(/^\/v1\/console\/compatibility\/langgraph\/threads\/([^/]+)\/runs\/stream-probe$/);
    if (compatibilityStreamMatch && route.request().method() === "POST") {
      return fulfillJson(
        route,
        compatibilityStreamProbeResponse(
          route,
          compatibilityStreamMatch[1],
          compatibilityAssistants,
          compatibilityRuns,
          nextCompatibilityRunId++,
          nextCompatibilityTaskId++,
        ),
      );
    }
    const compatibilityGetRunMatch = path.match(/^\/v1\/console\/compatibility\/langgraph\/threads\/([^/]+)\/runs\/(\d+)$/);
    if (compatibilityGetRunMatch && route.request().method() === "GET") {
      return fulfillJson(
        route,
        compatibilityGetRunResponse(compatibilityRuns, compatibilityGetRunMatch[1], Number(compatibilityGetRunMatch[2])),
      );
    }
    const compatibilityStreamStatusMatch = path.match(/^\/v1\/console\/compatibility\/langgraph\/threads\/([^/]+)\/runs\/(\d+)\/stream-status$/);
    if (compatibilityStreamStatusMatch && route.request().method() === "GET") {
      return fulfillJson(
        route,
        compatibilityStreamStatusResponse(compatibilityRuns, compatibilityStreamStatusMatch[1], Number(compatibilityStreamStatusMatch[2])),
      );
    }
    const compatibilityReplayMatch = path.match(/^\/v1\/console\/compatibility\/langgraph\/threads\/([^/]+)\/runs\/(\d+)\/events$/);
    if (compatibilityReplayMatch && route.request().method() === "GET") {
      return fulfillJson(
        route,
        compatibilityReplayResponse(route, compatibilityRuns, compatibilityReplayMatch[1], Number(compatibilityReplayMatch[2])),
      );
    }
    const compatibilityJoinMatch = path.match(/^\/v1\/console\/compatibility\/langgraph\/threads\/([^/]+)\/runs\/(\d+)\/join$/);
    if (compatibilityJoinMatch && route.request().method() === "POST") {
      return fulfillJson(
        route,
        compatibilityRunActionResponse(compatibilityRuns, compatibilityJoinMatch[1], Number(compatibilityJoinMatch[2]), "succeeded", "run.join"),
      );
    }
    const compatibilityCancelMatch = path.match(/^\/v1\/console\/compatibility\/langgraph\/threads\/([^/]+)\/runs\/(\d+)\/cancel$/);
    if (compatibilityCancelMatch && route.request().method() === "POST") {
      return fulfillJson(
        route,
        compatibilityRunActionResponse(compatibilityRuns, compatibilityCancelMatch[1], Number(compatibilityCancelMatch[2]), "cancelled", "run.cancel"),
      );
    }
    if (path === "/v1/console/compatibility/migration-report" && route.request().method() === "POST") {
      return fulfillJson(route, compatibilityMigrationReportResponse(route));
    }
    if (path === "/v1/published-surfaces/validate" && route.request().method() === "POST") {
      return fulfillJson(route, publishedSurfaceValidationResponse(route));
    }
    if (path === "/v1/published-surfaces/publish" && route.request().method() === "POST") {
      const response = publishedSurfacePublishResponse(route, publishedSurfaces, ingressRoutes, publishedRolloutHistory);
      return fulfillJson(route, response);
    }
    if (path === "/v1/ingress-routes/test" && route.request().method() === "POST") {
      const response = ingressRouteTestResponse(route, publishedRequestLogs);
      return fulfillJson(route, response);
    }
    const publishedDetailMatch = path.match(/^\/v1\/console\/published-surfaces\/(\d+)$/);
    if (publishedDetailMatch && route.request().method() === "GET") {
      return fulfillJson(
        route,
        publishedSurfaceDetailResponse(
          Number(publishedDetailMatch[1]),
          publishedSurfaces,
          publishedRequestLogs,
          publishedRolloutHistory,
        ),
      );
    }
    const publishedRolloutMatch = path.match(/^\/v1\/published-surfaces\/(\d+)\/rollout$/);
    if (publishedRolloutMatch && route.request().method() === "POST") {
      return fulfillJson(
        route,
        publishedSurfaceRolloutResponse(
          route,
          Number(publishedRolloutMatch[1]),
          publishedSurfaces,
          publishedRolloutHistory,
        ),
      );
    }
    if (path === "/v1/packages/validate" && route.request().method() === "POST") {
      try {
        return fulfillJson(route, packageValidationResponse(parseRequestBody(route)));
      } catch (error) {
        return fulfillError(route, error);
      }
    }
    if (path === "/v1/policies/simulate" && route.request().method() === "POST") {
      return fulfillJson(route, policySimulationResponse(route));
    }
    if (path === "/v1/policies/activate" && route.request().method() === "POST") {
      return fulfillJson(route, policyActivationResponse(route, 1, 1));
    }
    if (path === "/v1/model-gateways/test" && route.request().method() === "POST") {
      return fulfillJson(route, modelGatewayTestResponse(route));
    }
    if (path === "/v1/tools/dry-run" && route.request().method() === "POST") {
      return fulfillJson(route, toolDryRunResponse(route));
    }
    if (path === "/v1/secrets/validate" && route.request().method() === "POST") {
      return fulfillJson(route, secretValidationResponse(route));
    }
    if (path === "/v1/secrets/rotate" && route.request().method() === "POST") {
      return fulfillJson(route, secretRotationResponse(route));
    }
    if (path === "/v1/datasets/capture-run" && route.request().method() === "POST") {
      const response = runDatasetCaptureResponse(route, capturedRunDataset);
      capturedRunDataset = true;
      return fulfillJson(route, response);
    }
    if (path === "/v1/experiments/run" && route.request().method() === "POST") {
      return fulfillJson(route, experimentRunResponse(route));
    }
    if (path === "/v1/quality-gates/preview" && route.request().method() === "POST") {
      return fulfillJson(route, qualityGatePreviewResponse(route));
    }
    const incidentActionMatch = path.match(/^\/v1\/incidents\/(\d+)\/(acknowledge|resolve)$/);
    if (incidentActionMatch && route.request().method() === "POST") {
      return fulfillJson(
        route,
        incidentWorkflowResponse(
          route,
          Number(incidentActionMatch[1]),
          incidentActionMatch[2],
          incidentTimeline,
          incidentDeliveries,
        ),
      );
    }
    if (path === "/v1/notifications/test-send" && route.request().method() === "POST") {
      return fulfillJson(route, notificationTestResponse(route));
    }
    if (path === "/v1/backups/dry-run" && route.request().method() === "POST") {
      return fulfillJson(route, backupDryRunResponse(route));
    }
    if (path === "/v1/backups/restore-dry-run" && route.request().method() === "POST") {
      return fulfillRestoreDryRun(route);
    }
    const policyRollbackMatch = path.match(/^\/v1\/policies\/(\d+)\/rollback$/);
    if (policyRollbackMatch && route.request().method() === "POST") {
      return fulfillJson(route, policyActivationResponse(route, Number(policyRollbackMatch[1]), 2, true));
    }
    const humanDecisionMatch = path.match(/^\/v1\/human-tasks\/(\d+)\/(approve|reject)$/);
    if (humanDecisionMatch && route.request().method() === "POST") {
      return fulfillJson(route, humanTaskDecisionResponse(route, api, Number(humanDecisionMatch[1]), humanDecisionMatch[2]));
    }
    const runEventsMatch = path.match(/^\/v1\/runs\/(\d+)\/events$/);
    if (runEventsMatch && route.request().method() === "GET") {
      return fulfillJson(route, runEvents(Number(runEventsMatch[1])));
    }
    const runAttemptsMatch = path.match(/^\/v1\/runs\/(\d+)\/attempts$/);
    if (runAttemptsMatch && route.request().method() === "GET") {
      return fulfillJson(route, runAttempts(Number(runAttemptsMatch[1])));
    }
    const runIntegrationEvidenceMatch = path.match(/^\/v1\/runs\/(\d+)\/integration-evidence$/);
    if (runIntegrationEvidenceMatch && route.request().method() === "GET") {
      return fulfillJson(route, runIntegrationEvidence(Number(runIntegrationEvidenceMatch[1])));
    }
    const runMatch = path.match(/^\/v1\/runs\/(\d+)$/);
    if (runMatch && route.request().method() === "GET") {
      return fulfillJson(route, api.runs.find((item) => item.id === Number(runMatch[1])) ?? makeAdminCollection([]));
    }
    if (path === "/v1/replay-jobs/compare" && route.request().method() === "POST") {
      return fulfillJson(route, replayComparisonResponse(route, api));
    }
    const datasetCaptureMatch = path.match(/^\/v1\/replay-jobs\/([^/]+)\/dataset-captures$/);
    if (datasetCaptureMatch && route.request().method() === "POST") {
      return fulfillJson(route, datasetCaptureResponse(route, datasetCaptureMatch[1]));
    }
    const promotionPreviewMatch = path.match(/^\/v1\/deployments\/(\d+)\/promotion-preview$/);
    if (promotionPreviewMatch && route.request().method() === "GET") {
      return fulfillJson(
        route,
        promotionPreviewResponse(
          api,
          Number(promotionPreviewMatch[1]),
          Number(url.searchParams.get("candidate_version_id")),
          Number(url.searchParams.get("experiment_run_id")),
        ),
      );
    }
    const promoteMatch = path.match(/^\/v1\/deployments\/(\d+)\/promote$/);
    if (promoteMatch && route.request().method() === "POST") {
      return fulfillPromotion(route, api, Number(promoteMatch[1]));
    }
    const rollbackMatch = path.match(/^\/v1\/deployments\/(\d+)\/rollback$/);
    if (rollbackMatch && route.request().method() === "POST") {
      return fulfillRollback(route, api, Number(rollbackMatch[1]));
    }
    const controlMatch = path.match(/^\/v1\/deployments\/(\d+)\/(activate|pause|resume|drain|stop|restart)$/);
    if (controlMatch && route.request().method() === "POST") {
      return fulfillJson(route, controlDeploymentResponse(api, Number(controlMatch[1]), controlMatch[2]));
    }
    return fulfillJson(route, responseForPath(path, api));
  });
}

function parseRequestBody(route: Route): Record<string, unknown> {
  const body = route.request().postData();
  if (!body) return {};
  const parsed = JSON.parse(body);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed)
    ? parsed as Record<string, unknown>
    : {};
}

function makeGovernedAssets(): GovernedAssetFixture[] {
  return [
    {
      id: 810,
      kind: "prompt",
      name: "support-prompt",
      version: "1.0.0",
      status: "published",
      content_ref: "inline:triage-v1",
      visibility_level: "internal",
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [],
      _used_by: [],
      _risk_flags: [],
    },
    {
      id: 811,
      kind: "prompt",
      name: "support-prompt",
      version: "1.1.0",
      status: "draft",
      content_ref: "inline:triage-v2",
      visibility_level: "internal",
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "pending", validated_at: null, issues: [] },
      _dependencies: [{ kind: "template", name: "support-template", version: "2.0.0" }],
      _used_by: [],
      _risk_flags: [],
    },
    {
      id: 812,
      kind: "prompt",
      name: "live-prompt",
      version: "1.0.0",
      status: "published",
      content_ref: "inline:live",
      visibility_level: "internal",
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [],
      _used_by: [
        {
          resource_kind: "deployment",
          resource_id: 10,
          environment: "production",
          status: "active",
          active: true,
        },
      ],
      _risk_flags: ["active_deployment_dependency"],
    },
    {
      id: 813,
      kind: "prompt",
      name: "broken-prompt",
      version: "latest",
      status: "draft",
      content_ref: "inline:broken",
      visibility_level: "internal",
      created_at: createdAt,
      updated_at: createdAt,
      _validation: {
        status: "failed",
        validated_at: createdAt,
        issues: [
          { code: "explicit_version_required", field: "version", message: "latest is not allowed." },
          { code: "secret_ref_invalid", field: "secret_refs", message: "Invalid secret ref: bad-secret-ref" },
        ],
      },
      _dependencies: [{ kind: "prompt", name: "missing", version: "latest" }],
      _used_by: [],
      _risk_flags: ["floating_version"],
    },
    {
      id: 820,
      kind: "catalog",
      name: "runtime-tool",
      version: "1.0.0",
      status: "published",
      type: "tool",
      provider: "local",
      risk_level: "high",
      schema: {},
      capabilities: { invoke: true },
      runtime_requirements: {},
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [{ kind: "prompt", name: "support-prompt", version: "1.0.0" }],
      _used_by: [{ resource_kind: "agent_version", resource_id: 12, environment: null, status: "ready", active: true }],
      _risk_flags: ["high_risk_component"],
    },
    {
      id: 821,
      kind: "catalog",
      name: "crm-mcp",
      version: "1.0.0",
      status: "published",
      type: "mcp_endpoint",
      provider: "remote",
      risk_level: "medium",
      schema: {},
      capabilities: { invoke: true },
      runtime_requirements: { model_gateway_refs: ["default-gateway"] },
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [{ kind: "prompt", name: "support-prompt", version: "1.0.0" }],
      _used_by: [{ resource_kind: "agent_version", resource_id: 11, environment: null, status: "ready", active: true }],
      _risk_flags: [],
    },
    {
      id: 822,
      kind: "catalog",
      name: "shared-vector-memory",
      version: "1.0.0",
      status: "approved",
      type: "semantic_store",
      provider: "chroma",
      risk_level: "medium",
      schema: {},
      capabilities: { search: true },
      runtime_requirements: { retrieval_mode: "hybrid" },
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [{ kind: "config", name: "production-config", version: "1.0.0" }],
      _used_by: [],
      _risk_flags: [],
    },
    {
      id: 823,
      kind: "catalog",
      name: "governed-sandbox",
      version: "1.0.0",
      status: "published",
      type: "runtime_component",
      provider: "native",
      risk_level: "critical",
      schema: {},
      capabilities: { sandbox: true },
      runtime_requirements: { isolation_level: "process" },
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [{ kind: "template", name: "support-template", version: "2.0.0" }],
      _used_by: [
        { resource_kind: "deployment", resource_id: 10, environment: "production", status: "active", active: true },
      ],
      _risk_flags: ["high_risk_component", "active_deployment_dependency"],
    },
    {
      id: 830,
      kind: "config",
      name: "production-config",
      version: "1.0.0",
      status: "approved",
      content_ref: "inline:cfg",
      environment: "production",
      schema: {},
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [],
      _used_by: [],
      _risk_flags: [],
    },
    {
      id: 840,
      kind: "template",
      name: "support-template",
      version: "2.0.0",
      status: "published",
      type: "template",
      content_ref: "inline:template",
      schema: {},
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [],
      _used_by: [],
      _risk_flags: [],
    },
  ];
}

function listGovernedAssets(
  assets: GovernedAssetFixture[],
  kind: GovernedAssetFixture["kind"],
): Array<Record<string, unknown>> {
  return assets
    .filter((item) => item.kind === kind)
    .map((item) => ({
      id: item.id,
      name: item.name,
      version: item.version,
      status: item.status,
      type: item.type,
      provider: item.provider,
      risk_level: item.risk_level,
      visibility_level: item.visibility_level,
      environment: item.environment ?? null,
      created_at: item.created_at,
      updated_at: item.updated_at,
    }));
}

function governedAssetDetailResponse(
  assets: GovernedAssetFixture[],
  item: GovernedAssetFixture,
): Record<string, unknown> {
  const history = assets
    .filter((entry) => entry.kind === item.kind && entry.name === item.name && entry.type === item.type)
    .sort((left, right) => left.id - right.id);
  const previousIndex = history.findIndex((entry) => entry.id === item.id) - 1;
  const previous = previousIndex >= 0 ? history[previousIndex] : null;
  const changed_fields = previous
    ? [
        {
          field: "content_ref",
          before: previous.content_ref ?? null,
          after: item.content_ref ?? null,
        },
        {
          field: "version",
          before: previous.version,
          after: item.version,
        },
      ].filter((entry) => entry.before !== entry.after)
    : [];
  return {
    item: {
      id: item.id,
      name: item.name,
      version: item.version,
      status: item.status,
      kind: item.kind,
      type: item.type,
      provider: item.provider,
      risk_level: item.risk_level,
      visibility_level: item.visibility_level,
      environment: item.environment ?? null,
      content_ref: item.content_ref,
      schema: item.schema ?? {},
      capabilities: item.capabilities ?? {},
      runtime_requirements: item.runtime_requirements ?? {},
      created_at: item.created_at,
      updated_at: item.updated_at,
    },
    lifecycle: {
      status: item.status,
      last_action: item.status,
    },
    validation: item._validation || { status: "pending", issues: [] },
    dependencies: item._dependencies || [],
    used_by: item._used_by || [],
    risk_flags: item._risk_flags || [],
    version_history: history.map((entry) => ({
      id: entry.id,
      name: entry.name,
      version: entry.version,
      status: entry.status,
    })),
    diff_to_previous: {
      changed_fields,
      has_changes: changed_fields.length > 0,
    },
    environment: item.environment ?? null,
  };
}

function fulfillGovernedAssetCreate(
  route: Route,
  assets: GovernedAssetFixture[],
  kind: GovernedAssetFixture["kind"],
) {
  const body = parseRequestBody(route);
  const created: GovernedAssetFixture = {
    id: nextNumericId(assets),
    kind,
    name: String(body.name || `${kind}-${assets.length + 1}`),
    version: String(body.version || "1.0.0"),
    status: "draft",
    type: typeof body.type === "string" ? body.type : kind === "catalog" ? "tool" : "template",
    provider: typeof body.provider === "string" ? body.provider : "local",
    risk_level: typeof body.risk_level === "string" ? body.risk_level : "medium",
    visibility_level: "internal",
    environment: typeof body.environment === "string" ? body.environment : null,
    content_ref: typeof body.content_ref === "string" ? body.content_ref : "inline:content",
    created_at: createdAt,
    updated_at: createdAt,
    _validation: { status: "pending", validated_at: null, issues: [] },
    _dependencies: [],
    _used_by: [],
    _risk_flags: [],
  };
  assets.unshift(created);
  return fulfillJson(route, { item: listGovernedAssets([created], kind)[0], request_id: "e2e-request" });
}

function fulfillGovernedAssetDetail(
  route: Route,
  assets: GovernedAssetFixture[],
  kind: GovernedAssetFixture["kind"],
  assetId: number,
) {
  const item = assets.find((entry) => entry.kind === kind && entry.id === assetId);
  if (!item) {
    return route.fulfill({
      status: 404,
      contentType: "application/json",
      json: { detail: { error_code: `${kind}_asset_not_found`, message: "Asset not found." } },
    });
  }
  return fulfillJson(route, governedAssetDetailResponse(assets, item));
}

function fulfillGovernedAssetAction(
  route: Route,
  assets: GovernedAssetFixture[],
  kind: GovernedAssetFixture["kind"],
  assetId: number,
  action: string,
) {
  const body = parseRequestBody(route);
  const item = assets.find((entry) => entry.kind === kind && entry.id === assetId);
  if (!item) {
    return route.fulfill({
      status: 404,
      contentType: "application/json",
      json: { detail: { error_code: `${kind}_asset_not_found`, message: "Asset not found." } },
    });
  }
  if (action === "validate") {
    if (item.name === "broken-prompt") {
      return fulfillJson(route, {
        item: { id: item.id, name: item.name, version: item.version, status: item.status },
        lifecycle: { status: item.status },
        validation: item._validation,
      });
    }
    item.status = "validated";
    item.updated_at = createdAt;
    item._validation = { status: "passed", validated_at: createdAt, issues: [] };
    return fulfillJson(route, {
      item: { id: item.id, name: item.name, version: item.version, status: item.status },
      lifecycle: { status: item.status },
      validation: item._validation,
    });
  }
  if (action === "approve") {
    item.status = "approved";
    return fulfillJson(route, {
      item: { id: item.id, name: item.name, version: item.version, status: item.status },
      lifecycle: { status: item.status },
    });
  }
  if (action === "publish") {
    for (const sibling of assets) {
      if (sibling.kind === item.kind && sibling.name === item.name && sibling.id !== item.id && sibling.status === "published") {
        sibling.status = "deprecated";
      }
    }
    item.status = "published";
    return fulfillJson(route, {
      item: { id: item.id, name: item.name, version: item.version, status: item.status },
      lifecycle: { status: item.status },
    });
  }
  if (action === "deprecate" && (item._used_by || []).some((entry) => recordValue(entry, "active") === true)) {
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "asset_in_use_by_active_deployment",
          message: "Asset is still referenced by an active deployment.",
          request_id: "e2e-error-request",
        },
      },
    });
  }
  if (action === "deprecate") {
    item.status = "deprecated";
    return fulfillJson(route, {
      item: { id: item.id, name: item.name, version: item.version, status: item.status },
      lifecycle: { status: item.status },
      used_by: item._used_by || [],
    });
  }
  if (action === "archive") {
    item.status = "archived";
    return fulfillJson(route, {
      item: { id: item.id, name: item.name, version: item.version, status: item.status },
      lifecycle: { status: item.status },
    });
  }
  const targetVersion = String(body.target_version || "");
  const target = assets.find(
    (entry) => entry.kind === kind && entry.name === item.name && entry.version === targetVersion,
  );
  if (!target) {
    return route.fulfill({
      status: 404,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "rollback_target_not_found",
          message: "Rollback target version was not found.",
          request_id: "e2e-error-request",
        },
      },
    });
  }
  item.status = "deprecated";
  target.status = "published";
  return fulfillJson(route, {
    item: { id: target.id, name: target.name, version: target.version, status: target.status },
    rolled_back_from: { id: item.id, name: item.name, version: item.version, status: item.status },
    lifecycle: { status: target.status },
  });
}

function recordValue(record: unknown, key: string): unknown {
  return record && typeof record === "object" && !Array.isArray(record)
    ? (record as Record<string, unknown>)[key]
    : undefined;
}

function fulfillSchedulePreview(route: Route) {
  const body = parseRequestBody(route);
  const timezone = String(body.timezone || "UTC");
  if (timezone === "Mars/Phobos") {
    return route.fulfill({
      status: 400,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "invalid_timezone",
          message: "Schedule preview payload is invalid.",
          request_id: "e2e-error-request",
        },
      },
    });
  }
  return fulfillJson(route, {
    preview: {
      schedule_type: body.cron_expression ? "cron" : "interval",
      timezone,
      cron_expression: body.cron_expression || null,
      interval_minutes: body.interval_minutes || null,
      next_fire_time: "2026-06-13T01:30:00.000Z",
    },
    normalized: body,
    request_id: "e2e-request",
  });
}

function fulfillScheduleCreate(route: Route, scheduledRuns: Array<Record<string, unknown>>) {
  const body = parseRequestBody(route);
  const nextId = Math.max(...scheduledRuns.map((item) => Number(item.id || 0))) + 1;
  const record = {
    id: nextId,
    name: String(body.name || "runtime-schedule"),
    status: "active",
    schedule_type: body.cron_expression ? "cron" : "interval",
    cron_expression: typeof body.cron_expression === "string" ? body.cron_expression : null,
    interval_minutes: body.interval_minutes == null ? null : Number(body.interval_minutes),
    timezone: String(body.timezone || "UTC"),
    next_fire_time: "2026-06-13T02:00:00.000Z",
    deployment_id: Number(body.deployment_id || 10),
    input_template: body.input_template || {},
    backfill_policy: String(body.backfill_policy || "none"),
    missed_run_policy: String(body.missed_run_policy || "skip"),
    last_triggered_at: null,
    last_run_id: null,
    last_task_id: null,
    last_run_status: null,
    last_task_status: null,
    last_trigger_source: null,
    trigger_count: 0,
    pause_reason: null,
    tenant_id: 1,
    project_id: 1,
    environment: "local",
    created_at: createdAt,
    updated_at: createdAt,
    metadata: {},
  };
  scheduledRuns.unshift(record);
  return fulfillJson(route, { item: record, request_id: "e2e-request" });
}

function fulfillScheduledRunDetail(
  route: Route,
  scheduledRuns: Array<Record<string, unknown>>,
  scheduleId: number,
) {
  const item = scheduledRuns.find((record) => Number(record.id) === scheduleId);
  return item
    ? fulfillJson(route, { item, request_id: "e2e-request" })
    : fulfillError(route, new Error("schedule_not_found"));
}

function fulfillScheduleAction(
  route: Route,
  scheduledRuns: Array<Record<string, unknown>>,
  scheduleId: number,
  action: string,
) {
  const item = scheduledRuns.find((record) => Number(record.id) === scheduleId);
  if (!item) return fulfillError(route, new Error("schedule_not_found"));
  if (action === "pause") {
    item.status = "paused";
    item.pause_reason = "maintenance";
  } else if (action === "resume") {
    item.status = "active";
    item.pause_reason = null;
  } else if (action === "trigger") {
    item.last_triggered_at = "2026-06-13T01:15:00.000Z";
    item.last_run_id = 9001;
    item.last_task_id = 9101;
    item.last_run_status = "pending";
    item.last_task_status = "queued";
    item.last_trigger_source = "manual";
    item.trigger_count = Number(item.trigger_count || 0) + 1;
    item.next_fire_time = "2026-06-13T01:45:00.000Z";
    return fulfillJson(route, {
      item,
      triggered_run: { run_id: 9001, task_id: 9101, status: "queued" },
      request_id: "e2e-request",
    });
  }
  return fulfillJson(route, { item, request_id: "e2e-request" });
}

function fulfillBatchRunCreate(route: Route, batchRuns: Array<Record<string, unknown>>) {
  const body = parseRequestBody(route);
  const nextId = Math.max(...batchRuns.map((item) => Number(item.id || 0))) + 1;
  const items = Array.isArray(body.input_items) ? body.input_items : [];
  const normalizedItems = items.map((item, index) => {
    if (item && typeof item === "object" && !Array.isArray(item)) {
      return {
        index,
        status: "queued",
        input: item,
        run_id: 5000 + index,
        task_id: 6000 + index,
      };
    }
    return {
      index,
      status: "failed",
      input: null,
      run_id: null,
      task_id: null,
      error_code: "batch_item_invalid",
      message: "Batch input item must be an object.",
    };
  });
  const queuedItems = normalizedItems.filter((item) => item.status === "queued").length;
  const failedItems = normalizedItems.filter((item) => item.status === "failed").length;
  const record = {
    id: nextId,
    name: String(body.name || "runtime-batch"),
    status: failedItems > 0 ? "partial_failed" : "queued",
    deployment_id: Number(body.deployment_id || 10),
    dataset_id: null,
    concurrency: Number(body.concurrency || 1),
    retry_policy: body.retry_policy || {},
    cancel_policy: String(body.cancel_policy || "queued_only"),
    partial_failure_policy: String(body.partial_failure_policy || "continue"),
    artifact_output_ref: null,
    progress_summary: {
      total_items: normalizedItems.length,
      queued_items: queuedItems,
      running_items: 0,
      retrying_items: 0,
      failed_items: failedItems,
      dead_letter_items: 0,
      cancelled_items: 0,
      completed_items: 0,
      terminal_items: failedItems,
    },
    items: normalizedItems,
    tenant_id: 1,
    project_id: 1,
    environment: "local",
    created_at: createdAt,
    updated_at: createdAt,
  };
  batchRuns.unshift(record);
  return fulfillJson(route, { item: record, request_id: "e2e-request" });
}

function fulfillBatchRunDetail(route: Route, batchRuns: Array<Record<string, unknown>>, batchId: number) {
  const item = batchRuns.find((record) => Number(record.id) === batchId);
  return item
    ? fulfillJson(route, { item, request_id: "e2e-request" })
    : fulfillError(route, new Error("batch_run_not_found"));
}

function fulfillBatchRunCancel(route: Route, batchRuns: Array<Record<string, unknown>>, batchId: number) {
  const item = batchRuns.find((record) => Number(record.id) === batchId);
  if (!item) return fulfillError(route, new Error("batch_run_not_found"));
  const items = Array.isArray(item.items) ? item.items : [];
  for (const entry of items) {
    if (entry && typeof entry === "object" && (entry as Record<string, unknown>).status === "queued") {
      (entry as Record<string, unknown>).status = "cancelled";
    }
  }
  item.status = "partial_failed";
  item.progress_summary = {
    total_items: items.length,
    queued_items: 0,
    running_items: 0,
    retrying_items: 0,
    failed_items: 1,
    dead_letter_items: 0,
    cancelled_items: items.filter((entry) => entry && typeof entry === "object" && (entry as Record<string, unknown>).status === "cancelled").length,
    completed_items: 0,
    terminal_items:
      1 + items.filter((entry) => entry && typeof entry === "object" && (entry as Record<string, unknown>).status === "cancelled").length,
  };
  return fulfillJson(route, { item, request_id: "e2e-request" });
}

function costBreakdown(
  groupBy: string,
  key: string,
  label: string,
  totalCostUsd: number,
  totalTokens: number,
  runCount: number,
  failedRunCount: number,
  latestRunId: number | null,
  qualityGate: Record<string, unknown> | null = null,
): Record<string, unknown> {
  return {
    group_by: groupBy,
    key,
    label,
    total_cost_usd: totalCostUsd,
    total_tokens: totalTokens,
    run_count: runCount,
    failed_run_count: failedRunCount,
    latest_run_id: latestRunId,
    latest_at: createdAt,
    quality_gate: qualityGate,
  };
}

function costSummaryResponse(url: URL): Record<string, unknown> {
  const groupBy = url.searchParams.get("group_by") || "deployment";
  const windowDays = Number(url.searchParams.get("window_days") || 30);
  let breakdown: Array<Record<string, unknown>>;
  if (groupBy === "provider") {
    breakdown = [
      costBreakdown("provider", "openai", "openai", 1.9, 9800, 3, 1, 1003),
      costBreakdown("provider", "anthropic", "anthropic", 0.48, 2100, 1, 0, 1002),
    ];
  } else if (groupBy === "model") {
    breakdown = [
      costBreakdown("model", "gpt-4.1", "gpt-4.1", 1.2, 5200, 1, 1, 1001),
      costBreakdown("model", "gpt-4.1-mini", "gpt-4.1-mini", 0.7, 4600, 2, 0, 1003),
      costBreakdown("model", "claude-3-7-sonnet", "claude-3-7-sonnet", 0.48, 2100, 1, 0, 1002),
    ];
  } else if (groupBy === "run") {
    breakdown = [
      costBreakdown("run", "1001", "Run #1001", 1.2, 5200, 1, 1, 1001),
      costBreakdown("run", "1003", "Run #1003", 0.45, 2800, 1, 0, 1003),
      costBreakdown("run", "1002", "Run #1002", 0.25, 1800, 1, 0, 1002),
    ];
  } else if (groupBy === "agent") {
    breakdown = [
      costBreakdown("agent", "1", "support-agent", 2.38, 11900, 4, 1, 1003),
    ];
  } else {
    breakdown = [
      costBreakdown("deployment", "10", "Deployment #10", 1.9, 9800, 3, 1, 1003, {
        status: "passed",
        promotion_allowed: true,
        blocked_reason: null,
        experiment_run_id: 401,
        average_score: 1.0,
        min_score: 0.8,
        candidate_agent_version_id: 12,
      }),
      costBreakdown("deployment", "11", "Deployment #11", 0.48, 2100, 1, 0, 1002, {
        status: "failed",
        promotion_allowed: false,
        blocked_reason: "quality_gate_failed",
        experiment_run_id: 402,
        average_score: 0.6,
        min_score: 0.8,
        candidate_agent_version_id: 13,
      }),
    ];
  }
  return {
    window_days: windowDays,
    group_by: groupBy,
    total_cost_usd: 2.38,
    total_tokens: 11900,
    run_count: 4,
    failed_run_count: 1,
    breakdown,
  };
}

function costAnomaliesResponse(): Array<Record<string, unknown>> {
  return [
    {
      kind: "high_cost_failed_run",
      severity: "high",
      title: "High-cost failed run",
      summary: "Run #1001 failed after burning most of the monthly deployment budget.",
      cost_usd: 1.2,
      run_id: 1001,
      deployment_id: 10,
      provider: "openai",
      model: "gpt-4.1",
    },
    {
      kind: "cost_spike",
      severity: "critical",
      title: "Deployment spend spike",
      summary: "Deployment #10 is 2.4x above its recent baseline after the latest rollout.",
      cost_usd: 1.9,
      run_id: 1003,
      deployment_id: 10,
      provider: "openai",
      model: "gpt-4.1-mini",
    },
    {
      kind: "provider_error_cost_correlation",
      severity: "medium",
      title: "Provider error cost correlation",
      summary: "OpenAI failures now correlate with elevated token spend in the last window.",
      cost_usd: 1.2,
      run_id: 1001,
      deployment_id: 10,
      provider: "openai",
      model: null,
    },
  ];
}

function fulfillSavedCostView(
  route: Route,
  savedViews: Array<Record<string, unknown>>,
  viewId: number,
) {
  const view = activeCostSavedViews(savedViews).find((item) => Number(item.id) === viewId);
  if (!view) return fulfillError(route, new Error(`Saved cost view ${viewId} not found`));
  const url = new URL(route.request().url());
  url.searchParams.set("group_by", String(view.group_by || "deployment"));
  url.searchParams.set("window_days", String(view.window_days || 30));
  return fulfillJson(route, {
    item: view,
    summary: costSummaryResponse(url),
    anomalies: costAnomaliesResponse(),
  });
}

function fulfillBudgetPreview(route: Route) {
  const body = parseRequestBody(route);
  const notificationChannel = String(body.notification_channel || "");
  if (notificationChannel.includes("locked")) {
    return route.fulfill({
      status: 403,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "policy_update_required",
          message: "Missing permission: policy:update",
          request_id: "e2e-error-request",
          details: {
            required_scope: "policy:update",
          },
        },
      },
    });
  }
  const thresholdUsd = Number(body.threshold_usd || 0);
  const currentSpendUsd = 1.9;
  const projectedSpendUsd = 2.35;
  return fulfillJson(route, {
    scope_type: String(body.scope_type || "deployment"),
    scope_ref: typeof body.scope_ref === "string" ? body.scope_ref : "10",
    reset_window: String(body.reset_window || "monthly"),
    threshold_usd: thresholdUsd,
    current_spend_usd: currentSpendUsd,
    projected_spend_usd: projectedSpendUsd,
    utilization_ratio: thresholdUsd > 0 ? projectedSpendUsd / thresholdUsd : 0,
    would_trigger: thresholdUsd > 0 ? projectedSpendUsd >= thresholdUsd : false,
    notification_preview: `Notification preview -> ${notificationChannel}`,
    action_preview: `Action preview -> ${String(body.action_mode || "warn")}`,
    top_contributors: [
      costBreakdown("deployment", "10", "Deployment #10", 1.9, 9800, 3, 1, 1003),
      costBreakdown("deployment", "11", "Deployment #11", 0.48, 2100, 1, 0, 1002),
    ],
  });
}

function fulfillSavedBudgetPreview(
  route: Route,
  policies: Array<Record<string, unknown>>,
  channels: Array<Record<string, unknown>>,
  policyId: number,
) {
  const policy = policies.find((item) => Number(item.id) === policyId);
  if (!policy) return fulfillError(route, new Error(`Budget policy ${policyId} not found`));
  const channel = channels.find((item) => Number(item.id) === Number(policy.channel_id));
  return fulfillJson(route, {
    scope_type: String(policy.scope_type || "deployment"),
    scope_ref: typeof policy.scope_ref === "string" ? policy.scope_ref : null,
    reset_window: String(policy.reset_window || "monthly"),
    threshold_usd: Number(policy.threshold_usd || 0),
    current_spend_usd: 1.9,
    projected_spend_usd: 2.35,
    utilization_ratio: Number(policy.threshold_usd || 0) > 0 ? 2.35 / Number(policy.threshold_usd) : 0,
    would_trigger: true,
    notification_preview: `Notification preview -> ${String(channel?.target_ref || `channel:${policy.channel_id}`)}`,
    action_preview: `Action preview -> ${String(policy.action_mode || "warn")}`,
    top_contributors: [
      costBreakdown("deployment", "10", "Deployment #10", 1.9, 9800, 3, 1, 1003),
      costBreakdown("deployment", "11", "Deployment #11", 0.48, 2100, 1, 0, 1002),
    ],
  });
}

function fulfillCostBudgetCreate(
  route: Route,
  policies: Array<Record<string, unknown>>,
  channels: Array<Record<string, unknown>>,
) {
  const body = parseRequestBody(route);
  const channelId = Number(body.channel_id || 0);
  if (!channels.some((item) => Number(item.id) === channelId)) {
    return route.fulfill({
      status: 400,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "invalid_admin_resource",
          message: "Parent channel not found.",
          request_id: "e2e-error-request",
          details: { field: "channel_id", reason: "parent_not_found", parent_id: channelId },
        },
      },
    });
  }
  const nextId = Math.max(...policies.map((item) => Number(item.id)), 950) + 1;
  const item = {
    id: nextId,
    name: String(body.name || `budget-${nextId}`),
    environment: "local",
    scope_type: String(body.scope_type || "deployment"),
    scope_ref: typeof body.scope_ref === "string" ? body.scope_ref : null,
    threshold_usd: Number(body.threshold_usd || 0),
    reset_window: String(body.reset_window || "monthly"),
    channel_id: channelId,
    action_mode: String(body.action_mode || "warn"),
    status: "active",
    metadata: {},
    created_at: createdAt,
    updated_at: createdAt,
    tenant_id: 1,
    project_id: 1,
  };
  policies.unshift(item);
  return fulfillJson(route, { item, request_id: "e2e-request" });
}

function fulfillCostSavedViewCreate(
  route: Route,
  savedViews: Array<Record<string, unknown>>,
) {
  const body = parseRequestBody(route);
  const nextId = Math.max(...savedViews.map((item) => Number(item.id)), 940) + 1;
  const item = {
    id: nextId,
    name: String(body.name || `cost-view-${nextId}`),
    environment: "local",
    group_by: String(body.group_by || "deployment"),
    window_days: Number(body.window_days || 30),
    filters: body.filters && typeof body.filters === "object" ? body.filters : {},
    status: "active",
    metadata: {},
    created_at: createdAt,
    updated_at: createdAt,
    tenant_id: 1,
    project_id: 1,
  };
  savedViews.unshift(item);
  return fulfillJson(route, { item, request_id: "e2e-request" });
}

function fulfillCostSavedViewUpdate(
  route: Route,
  savedViews: Array<Record<string, unknown>>,
  viewId: number,
) {
  const savedView = activeCostSavedViews(savedViews).find((item) => Number(item.id) === viewId);
  if (!savedView) return fulfillError(route, new Error(`Saved cost view ${viewId} not found`));
  const body = parseRequestBody(route);
  Object.assign(savedView, {
    name: typeof body.name === "string" ? body.name : savedView.name,
    group_by: typeof body.group_by === "string" ? body.group_by : savedView.group_by,
    window_days: typeof body.window_days === "number" ? body.window_days : savedView.window_days,
    filters: body.filters && typeof body.filters === "object" ? body.filters : savedView.filters,
    updated_at: createdAt,
  });
  return fulfillJson(route, { item: savedView, request_id: "e2e-request" });
}

function fulfillCostBudgetUpdate(
  route: Route,
  policies: Array<Record<string, unknown>>,
  policyId: number,
) {
  const policy = policies.find((item) => Number(item.id) === policyId);
  if (!policy) return fulfillError(route, new Error(`Budget policy ${policyId} not found`));
  const body = parseRequestBody(route);
  Object.assign(policy, body, { updated_at: createdAt });
  return fulfillJson(route, { item: policy, request_id: "e2e-request" });
}

function archiveCostBudgetPolicy(
  policies: Array<Record<string, unknown>>,
  policyId: number,
): Record<string, unknown> {
  const policy = policies.find((item) => Number(item.id) === policyId);
  if (!policy) {
    return { item: { id: policyId, status: "deleted" }, request_id: "e2e-request" };
  }
  policy.status = "deleted";
  return { item: policy, request_id: "e2e-request" };
}

function archiveCostSavedView(
  savedViews: Array<Record<string, unknown>>,
  viewId: number,
): Record<string, unknown> {
  const savedView = activeCostSavedViews(savedViews).find((item) => Number(item.id) === viewId);
  if (!savedView) {
    return { item: { id: viewId, status: "deleted" }, request_id: "e2e-request" };
  }
  savedView.status = "deleted";
  return { item: savedView, request_id: "e2e-request" };
}

function activeCostSavedViews(
  savedViews: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  return savedViews.filter((item) => String(item.status || "active") !== "deleted");
}

function deployment(id: number, runtimeStatus: string, replicas: number): NativeDeploymentRead {
  return {
    id,
    tenant_id: 1,
    project_id: 1,
    agent_id: 1,
    agent_version_id: 11,
    environment: "local",
    desired_status: "active",
    runtime_status: runtimeStatus,
    replicas,
    config: {},
    last_runtime_error: null,
  };
}

function run(
  id: number,
  status: NativeRunRead["status"],
  deploymentId: number,
  latencyMs: number | null,
): NativeRunRead {
  return {
    id,
    agent_id: 1,
    agent_version_id: 11,
    deployment_id: deploymentId,
    status,
    input: { ticket_id: id },
    output: status === "succeeded" ? { routed: true } : null,
    error: status === "failed" ? { message: "provider timeout" } : null,
    thread_id: `thread-${id}`,
    created_at: createdAt,
    started_at: createdAt,
    finished_at: status === "pending" ? null : "2026-06-05T00:00:04.000Z",
    latency_ms: latencyMs,
  };
}

function runEvents(runId: number): NativeEventRead[] {
  return [
    {
      run_id: runId,
      event_id: `evt-${runId}-created`,
      sequence: 1,
      type: "run.created",
      payload: { run_id: runId },
      visibility_level: "public",
    },
    {
      run_id: runId,
      event_id: `evt-${runId}-attempt`,
      sequence: 2,
      type: runId === 1001 ? "attempt.failed" : "task.queued",
      payload: runId === 1001 ? { error: "provider timeout" } : { task_id: 5001 },
      visibility_level: "public",
    },
  ];
}

function runAttempts(runId: number): Array<Record<string, unknown>> {
  if (runId !== 1001) return [];
  return [
    {
      id: 9001,
      run_id: 1001,
      task_id: 8001,
      attempt_no: 1,
      worker_id: "worker-a",
      status: "failed",
      error: "provider timeout",
    },
  ];
}

function runIntegrationEvidence(runId: number): NativeRunIntegrationEvidenceRead {
  if (runId !== 1001) {
    return {
      run_id: runId,
      trace_links: [],
      exporters: [],
      model_gateway: [],
      failures: [],
      records: [],
    };
  }
  return {
    run_id: runId,
    trace_links: [
      {
        provider: "langfuse",
        url: "https://langfuse.example.test/project/support/traces/trace-1001",
        trace_id: "trace-1001",
        label: "Langfuse trace",
        status: "linked",
      },
    ],
    exporters: [
      {
        provider: "opentelemetry",
        exporter_type: "otlp",
        target_ref: "http://otel:4318",
        status: "delivered",
        request_id: "otel-req-1001",
        delivered_at: createdAt,
        message: "Delivered to local OTLP collector",
      },
    ],
    model_gateway: [
      {
        provider: "litellm",
        gateway_id: null,
        gateway_name: "local-litellm",
        gateway_request_id: "gw-req-1001",
        model: "gpt-4.1-mini",
        route: "support-policy",
        prompt_tokens: 118,
        completion_tokens: 42,
        total_tokens: 160,
        cost: 0.0042,
        currency: "USD",
      },
    ],
    failures: [
      {
        provider: "opentelemetry",
        status: "recovered",
        error_code: "otlp_retry",
        message: "First export attempt retried, second delivered",
        retryable: true,
        occurred_at: createdAt,
      },
    ],
    records: [
      {
        evidence_id: "intev_1001",
        source: "console-fixture-api",
        observed_at: createdAt,
        schema: "dimoorun.run.integration_evidence.v1",
      },
    ],
  };
}

function replayComparisonResponse(route: Route, api: DashboardApiFixture): unknown {
  const body = parseRequestBody(route);
  const sourceRunId = Number(body.source_run_id);
  const candidateVersionId = Number(body.candidate_agent_version_id || 12);
  const sourceRun = api.runs.find((item) => item.id === sourceRunId) ?? api.runs[0];
  const replayRun: NativeRunRead = {
    ...sourceRun,
    id: 2001,
    agent_version_id: candidateVersionId,
    status: "pending",
    output: null,
    error: null,
    thread_id: `replay-${sourceRun.id}`,
    latency_ms: null,
  };
  api.runs = [replayRun, ...api.runs.filter((item) => item.id !== replayRun.id)];
  const sourceEvents = runEvents(sourceRun.id);
  const replayEvents = [
    ...runEvents(replayRun.id),
    {
      run_id: replayRun.id,
      event_id: "evt-2001-replayed",
      sequence: 3,
      type: "run.replayed",
      payload: { source_run_id: sourceRun.id, candidate_agent_version_id: candidateVersionId },
      visibility_level: "public",
    },
  ];
  return {
    comparison_id: `cmp-${sourceRun.id}-${candidateVersionId}`,
    source_run: sourceRun,
    replay_run: replayRun,
    source_events: sourceEvents,
    replay_events: replayEvents,
    input_diff: { changed: false, source: sourceRun.input, replay: replayRun.input },
    output_diff: { changed: sourceRun.output !== replayRun.output, source: sourceRun.output, replay: replayRun.output },
    error_diff: { changed: sourceRun.error !== replayRun.error, source: sourceRun.error, replay: replayRun.error },
    event_diff: {
      changed: true,
      source_count: sourceEvents.length,
      replay_count: replayEvents.length,
      added_types: ["run.replayed"],
      removed_types: [],
    },
    latency_delta_ms: null,
    cost_delta_usd: null,
    regression_signal: "changed",
    provenance: {
      source_run_id: sourceRun.id,
      replay_run_id: replayRun.id,
      candidate_agent_version_id: candidateVersionId,
      replay_config: body.replay_config || {},
    },
  };
}

function datasetCaptureResponse(route: Route, comparisonId: string): unknown {
  const body = parseRequestBody(route);
  return {
    capture_id: "dataset-capture-1",
    comparison_id: comparisonId,
    dataset_name: String(body.dataset_name || ""),
    label: typeof body.label === "string" ? body.label : null,
    source_run_id: 1001,
    replay_run_id: 2001,
    provenance: {
      comparison_id: comparisonId,
      source_run_id: 1001,
      replay_run_id: 2001,
    },
  };
}

function policySimulationResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  const draft = body.draft_policy && typeof body.draft_policy === "object"
    ? body.draft_policy as Record<string, unknown>
    : {};
  const sample = body.sample && typeof body.sample === "object"
    ? body.sample as Record<string, unknown>
    : {};
  return {
    decision: {
      result: String(draft.decision || "deny"),
      policy_id: null,
      policy_name: String(draft.name || "deny-prod-delete"),
      reason: String(draft.reason || ""),
    },
    matched_resources: [
      {
        resource_type: String(sample.resource_type || "deployment"),
        resource_id: Number(sample.resource_id || 42),
        action: String(sample.action || "delete"),
        environment: String(sample.environment || "prod"),
      },
    ],
    matched_policies: [],
    audit_preview: {
      action: "policy.simulate",
      resource_type: String(draft.resource_type || "deployment"),
      resource_id: Number(sample.resource_id || 42),
    },
    conflict_warnings: [
      {
        code: "priority_conflict",
        message: "An active policy with the same priority returns a different decision.",
        conflicting_policy_id: 7,
      },
    ],
  };
}

function policyActivationResponse(route: Route, policyId: number, version: number, rollback = false): unknown {
  const body = parseRequestBody(route);
  const draft = body.draft_policy && typeof body.draft_policy === "object"
    ? body.draft_policy as Record<string, unknown>
    : {};
  return {
    item: {
      id: policyId,
      name: String(draft.name || "deny-prod-delete"),
      status: "active",
      decision: String(draft.decision || "deny"),
    },
    version,
    comparison: {
      from_version: rollback ? 2 : version === 1 ? null : version - 1,
      to_version: version,
      changed_fields: [
        {
          field: "decision",
          before: rollback ? "require_approval" : null,
          after: String(draft.decision || (rollback ? "deny" : "deny")),
        },
      ],
    },
    audit: {
      action: rollback ? "policy.rollback" : "policy.activate",
      reason: String(body.audit_reason || ""),
    },
    rollback_target: { policy_id: policyId, version: rollback ? 1 : version },
    conflict_warnings: [],
  };
}

function modelGatewayTestResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  const credentialRef = String(body.credential_ref || "");
  const credentialValid = credentialRef.startsWith("secret:") || credentialRef.startsWith("vault://");
  return {
    credential_validation: {
      valid: credentialValid,
      credential_ref: credentialRef,
      scope: "project",
      disabled_action_reason: credentialValid ? null : "credential_ref_must_use_secret_ref",
    },
    safe_health_probe: {
      status: credentialValid ? "ok" : "blocked",
      provider: String(body.provider_type || "openai"),
      secret_exposed: false,
      checked_at: createdAt,
    },
    budget_preview: {
      model_group: "default",
      monthly_budget_usd: Number(body.monthly_budget_usd || 0),
      estimated_request_cost_usd: 0.002,
      disabled_action_reason: null,
    },
    fallback_preview: {
      target: String(body.fallback_gateway_ref || ""),
      enabled: Boolean(body.fallback_gateway_ref),
      order: [String(body.name || "candidate"), String(body.fallback_gateway_ref || "")],
    },
    provider_error_normalization: {
      raw_status: 503,
      raw_code: "upstream_unavailable",
      normalized_code: "provider_unavailable",
      retryable: true,
    },
    audit_preview: {
      action: "model_gateway.test",
      resource_type: "model_gateway",
      resource_id: String(body.name || ""),
      request_id: "e2e-request",
    },
  };
}

function toolDryRunResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  const riskLevel = String(body.risk_level || "read");
  const requiresApproval = ["write", "admin", "critical"].includes(riskLevel);
  return {
    schema_validation: {
      valid: true,
      missing_fields: [],
      schema_type: "object",
    },
    risk_classification: {
      level: riskLevel,
      requires_approval: requiresApproval,
    },
    policy_preview: {
      decision: requiresApproval ? "require_approval" : "allow",
      matched_policy: "tool-risk-default",
      reason: requiresApproval ? "High-risk tool calls require approval." : "Read-only dry run.",
    },
    approval_requirement: {
      required: requiresApproval,
      role: requiresApproval ? "platform-approver" : null,
    },
    usage_history_link: `/v1/tools/${String(body.name || "tool")}/usage`,
    dry_run_output: {
      status: requiresApproval ? "blocked" : "succeeded",
      side_effects: false,
    },
    audit_preview: {
      action: "tool.dry_run",
      resource_type: "tool",
      resource_id: String(body.name || ""),
      request_id: "e2e-request",
    },
  };
}

function secretValidationResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  const accessContext = body.access_context && typeof body.access_context === "object"
    ? body.access_context as Record<string, unknown>
    : {};
  const ref = String(body.ref || "");
  const valid = ref.includes("://") && !ref.startsWith("plaintext");
  return {
    validation: {
      valid,
      provider: String(body.provider || "external"),
      ref,
      disabled_action_reason: valid ? null : "secret_ref_must_use_external_uri",
    },
    secret_value: null,
    last_used: {
      at: createdAt,
      used_by: String(accessContext.used_by || ""),
    },
    access_audit: {
      action: "secret.validate",
      resource_type: "secret",
      resource_id: String(body.name || ""),
      request_id: "e2e-request",
    },
  };
}

function secretRotationResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  return {
    rotation: {
      status: "rotated",
      previous_ref: "vault://project/model-openai",
      current_ref: String(body.ref || ""),
      reason: String(body.rotation_reason || ""),
    },
    last_used: {
      at: createdAt,
      used_by: String(body.name || ""),
    },
    access_audit: {
      action: "secret.rotate",
      resource_type: "secret",
      resource_id: String(body.name || ""),
      request_id: "e2e-request",
    },
  };
}

function runDatasetCaptureResponse(route: Route, duplicate: boolean): unknown {
  const body = parseRequestBody(route);
  const sourceRunId = Number(body.source_run_id || 1001);
  const redactFields = Array.isArray(body.redact_fields)
    ? body.redact_fields.map(String)
    : [];
  const input: Record<string, unknown> = { ticket_id: sourceRunId };
  for (const field of redactFields) input[field] = "[REDACTED]";
  return {
    dataset_id: 21,
    dataset_name: String(body.dataset_name || "support-regressions"),
    dataset_item_id: 301,
    source_run_id: sourceRunId,
    label: typeof body.label === "string" ? body.label : null,
    payload_preview: {
      input,
      output: null,
      error: { message: "provider timeout", api_key: "[REDACTED]" },
    },
    redaction: { fields: redactFields },
    provenance: {
      source_run_id: sourceRunId,
      dataset_id: 21,
      captured_at: createdAt,
    },
    audit: {
      action: "dataset.capture_run",
      resource_type: "dataset",
      resource_id: 21,
      request_id: "e2e-request",
    },
    duplicate,
    request_id: "e2e-request",
  };
}

function experimentRunResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  const evaluatorConfig = body.evaluator_config && typeof body.evaluator_config === "object"
    ? body.evaluator_config as Record<string, unknown>
    : {};
  const minScore = Number(evaluatorConfig.min_score || 0.8);
  return {
    experiment: {
      id: 101,
      name: String(body.name || "candidate-quality"),
      agent_id: Number(body.agent_id || 1),
      candidate_agent_version_id: Number(body.candidate_agent_version_id || 12),
      dataset_id: Number(body.dataset_id || 21),
      evaluator_config: evaluatorConfig,
      status: "completed",
    },
    run: {
      id: 401,
      experiment_id: 101,
      status: "completed",
      started_at: createdAt,
      finished_at: createdAt,
    },
    results: [
      {
        id: 1,
        experiment_run_id: 401,
        dataset_item_id: 301,
        evaluator_name: "exact_match",
        score: 1,
        passed: 1 >= minScore,
      },
    ],
    score_distribution: {
      count: 1,
      average_score: 1,
      min_score: minScore,
      passed: 1 >= minScore ? 1 : 0,
      failed: 1 >= minScore ? 0 : 1,
    },
    quality_gate: {
      status: 1 >= minScore ? "passed" : "failed",
      promotion_allowed: 1 >= minScore,
      blocked_reason: 1 >= minScore ? null : "quality_gate_failed",
      evidence: { dataset_id: Number(body.dataset_id || 21), experiment_run_id: 401 },
    },
    audit: {
      action: "experiment.run",
      resource_type: "experiment",
      resource_id: 101,
      request_id: "e2e-request",
    },
  };
}

function qualityGatePreviewResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  const experimentRunId = Number(body.experiment_run_id || 0);
  const passed = experimentRunId === 401;
  return {
    status: passed ? "passed" : "failed",
    promotion_allowed: passed,
    blocked_reason: passed ? null : "quality_gate_failed",
    required_evidence: ["experiment_run", "evaluation_results"],
    evidence: {
      experiment_run_id: experimentRunId,
      dataset_id: 21,
      average_score: passed ? 1 : 0,
      min_score: 0.8,
    },
    deployment_id: Number(body.deployment_id || 10),
    candidate_agent_version_id: Number(body.candidate_agent_version_id || 12),
    audit: {
      action: "quality_gate.preview",
      resource_type: "quality_gate",
      resource_id: experimentRunId,
      request_id: "e2e-request",
    },
  };
}

function incidentWorkflowResponse(
  route: Route,
  incidentId: number,
  action: string,
  timeline: Array<Record<string, unknown>>,
  deliveries: Array<Record<string, unknown>>,
): unknown {
  const body = parseRequestBody(route);
  const auditAction = action === "acknowledge" ? "incident.acknowledge" : "incident.resolve";
  const status = action === "acknowledge" ? "acknowledged" : "resolved";
  timeline.push({
    action: auditAction,
    status,
    audit_note: String(body.audit_note || ""),
    created_at: createdAt,
  });
  deliveries.push({
    id: 601 + deliveries.length,
    channel_name: Array.isArray(body.notify_channels) ? String(body.notify_channels[0] || "") : "",
    status: "sent",
    visible_to_operator: true,
  });
  return {
    incident: {
      id: incidentId,
      name: "provider outage",
      status,
      severity: "critical",
    },
    timeline,
    linked_evidence: {
      runs: Array.isArray(body.linked_runs) ? body.linked_runs.map(Number) : [],
      tasks: Array.isArray(body.linked_tasks) ? body.linked_tasks.map(Number) : [],
      events: Array.isArray(body.linked_events) ? body.linked_events.map(String) : [],
    },
    delivery_attempts: deliveries,
    resolution: action === "resolve"
      ? { summary: String(body.resolution_summary || ""), resolved_at: createdAt }
      : null,
    audit: {
      action: auditAction,
      resource_type: "incident",
      resource_id: incidentId,
      request_id: "e2e-request",
    },
  };
}

function notificationTestResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  return {
    status: "sent",
    delivery_attempt: {
      id: 701,
      channel_id: Number(body.channel_id || 55),
      channel_name: String(body.channel_name || "pagerduty-primary"),
      target_ref: String(body.target_ref || "pd://service/runtime"),
      status: "sent",
      visible_to_operator: true,
      redacted_payload: { message: String(body.message || "") },
    },
    audit: {
      action: "notification.test_send",
      resource_type: "notification_channel",
      resource_id: Number(body.channel_id || 55),
      request_id: "e2e-request",
    },
  };
}

function publishedSurfaceValidationResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  const surface = body.surface && typeof body.surface === "object"
    ? body.surface as Record<string, unknown>
    : {};
  const routePath = String(surface.route_path || "");
  const deploymentId = Number(surface.deployment_id);
  const authMode = String(surface.auth_mode || "");
  const corsPolicy = surface.cors_policy && typeof surface.cors_policy === "object"
    ? surface.cors_policy as Record<string, unknown>
    : {};
  const rateLimitPolicy = surface.rate_limit_policy && typeof surface.rate_limit_policy === "object"
    ? surface.rate_limit_policy as Record<string, unknown>
    : {};
  const allowedOrigins = Array.isArray(corsPolicy.allowed_origins)
    ? corsPolicy.allowed_origins.map(String)
    : [];
  const requestsPerMinute = Number(rateLimitPolicy.requests_per_minute);
  const blockedReasons: string[] = [];
  if (!routePath.startsWith("/")) blockedReasons.push("route_path_invalid");
  if (!Number.isInteger(deploymentId) || deploymentId <= 0) blockedReasons.push("deployment_binding_missing");
  if (authMode === "none") blockedReasons.push("auth_mode_unsafe");
  if (allowedOrigins.includes("*")) blockedReasons.push("cors_wildcard_not_allowed");
  if (!Number.isInteger(requestsPerMinute) || requestsPerMinute <= 0) blockedReasons.push("rate_limit_invalid");
  if (surface.policy_enforced === false) blockedReasons.push("policy_engine_required");
  const valid = blockedReasons.length === 0;
  return {
    status: valid ? "valid" : "invalid",
    can_publish: valid,
    checks: {
      route_path: { status: routePath.startsWith("/") ? "valid" : "invalid" },
      deployment_binding: { status: Number.isInteger(deploymentId) && deploymentId > 0 ? "valid" : "invalid" },
      auth_mode: { status: authMode !== "none" ? "valid" : "invalid" },
      cors_policy: { status: allowedOrigins.includes("*") ? "invalid" : "valid" },
      rate_limit_policy: { status: Number.isInteger(requestsPerMinute) && requestsPerMinute > 0 ? "valid" : "invalid" },
      policy_engine: { status: surface.policy_enforced === false ? "invalid" : "valid" },
    },
    blocked_reasons: blockedReasons,
    audit: {
      action: "published_surface.validate",
      resource_type: "published_surface",
      resource_id: Number(surface.surface_id || 501),
      request_id: "e2e-request",
    },
  };
}

function publishedSurfacePublishResponse(
  route: Route,
  surfaces: Array<Record<string, unknown>>,
  routes: Array<Record<string, unknown>>,
  rolloutHistory: Array<Record<string, unknown>>,
): unknown {
  const validation = publishedSurfaceValidationResponse(route) as Record<string, unknown>;
  const body = parseRequestBody(route);
  const surfacePayload = body.surface && typeof body.surface === "object"
    ? body.surface as Record<string, unknown>
    : {};
  const surfaceId = Number(surfacePayload.surface_id || 501);
  const deploymentId = Number(surfacePayload.deployment_id || 10);
  const routeId = Number(surfacePayload.route_id || 701);
  const routePath = String(surfacePayload.route_path || "/support/triage");
  const authMode = String(surfacePayload.auth_mode || "api_key");
  const surface = {
    id: surfaceId,
    name: "support ingress",
    deployment_id: deploymentId,
    type: "http",
    status: "active",
    created_at: createdAt,
  };
  const ingressRoute = {
    id: routeId,
    name: "support triage",
    surface_id: surfaceId,
    path: routePath,
    auth_mode: authMode,
    custom_domain: "support.example.com",
    status: "active",
    created_at: createdAt,
  };
  surfaces.splice(0, surfaces.length, surface);
  routes.splice(0, routes.length, ingressRoute);
  const rollout = {
    operation: "publish",
    version: rolloutHistory.length + 1,
    audit_preview: { action: "published_surface.publish" },
    created_at: createdAt,
  };
  rolloutHistory.push(rollout);
  return {
    ...validation,
    status: "valid",
    can_publish: true,
    blocked_reasons: [],
    surface,
    rollout,
    audit: {
      action: "published_surface.publish",
      resource_type: "published_surface",
      resource_id: surfaceId,
      request_id: "e2e-request",
    },
  };
}

function ingressRouteTestResponse(route: Route, requestLogs: Array<Record<string, unknown>>): unknown {
  const body = parseRequestBody(route);
  const path = String(body.path || "");
  const method = String(body.method || "");
  if (path !== "/support/triage" || method !== "POST") {
    return {
      status: "blocked",
      matched_deployment: {},
      auth_decision: { result: "deny" },
      policy_decision: { result: "deny" },
      expected_runtime_task: {},
      blocked_reasons: ["route_not_matched"],
      request_log: {},
      audit: { action: "ingress_route.test", resource_type: "ingress_route", resource_id: Number(body.route_id || 701) },
    };
  }
  const requestLog = {
    id: 801 + requestLogs.length,
    surface_id: Number(body.surface_id || 501),
    route_id: Number(body.route_id || 701),
    deployment_id: 10,
    environment: "local",
    auth_mode: "api_key",
    status: 200,
    latency_ms: 42,
    auth_result: "allow",
    policy_result: "allow",
    run_id: 9001,
    task_id: 8001,
    trace_id: `trace_${requestLogs.length + 1}`,
    redacted_request_metadata: {
      headers: {
        authorization: "[REDACTED]",
        "x-user": "operator",
      },
    },
    traffic_control: {
      traffic_split: { stable: 100, candidate: 0 },
      shadow_mode: false,
    },
  };
  requestLogs.unshift(requestLog);
  return {
    status: "matched",
    matched_deployment: { deployment_id: 10, environment: "local" },
    auth_decision: { result: "allow", mode: "api_key" },
    policy_decision: { result: "allow", policy_id: "published-surface-runtime-policy" },
    expected_runtime_task: { deployment_id: 10, task_shape: "deployment.invoke" },
    blocked_reasons: [],
    request_log: requestLog,
    audit: { action: "ingress_route.test", resource_type: "ingress_route", resource_id: Number(body.route_id || 701) },
  };
}

function publishedSurfaceDetailResponse(
  surfaceId: number,
  surfaces: Array<Record<string, unknown>>,
  requestLogs: Array<Record<string, unknown>>,
  rolloutHistory: Array<Record<string, unknown>>,
): unknown {
  const surface = surfaces.find((item) => Number(item.id) === surfaceId) ?? surfaces[0];
  return {
    surface,
    deployment_binding_health: {
      status: "healthy",
      deployment_id: Number(surface?.deployment_id || 10),
      environment: "local",
    },
    exposure_health: {
      status: surface?.status === "revoked" ? "blocked" : "ready",
      route_path: "/support/triage",
      published: surface?.status !== "revoked",
      last_live_request_status: surface?.status === "revoked" ? 403 : 200,
      last_live_request_id: requestLogs[0]?.id ?? 9001,
      last_live_trace_id: requestLogs[0]?.trace_id ?? "trace_501_live",
      blocked_reasons: surface?.status === "revoked" ? ["surface_revoked"] : [],
    },
    request_logs: requestLogs.filter((item) => Number(item.surface_id) === surfaceId),
    rollout_history: rolloutHistory,
    actions: {
      revoke: { requires_confirmation: true, disabled_reason: null },
      traffic_split: { requires_confirmation: false, disabled_reason: null },
      rollback: { requires_confirmation: false, disabled_reason: null, recovery_path: "restore_previous_surface_snapshot" },
    },
  };
}

function publishedSurfaceRolloutResponse(
  route: Route,
  surfaceId: number,
  surfaces: Array<Record<string, unknown>>,
  rolloutHistory: Array<Record<string, unknown>>,
): unknown {
  const body = parseRequestBody(route);
  const operation = String(body.operation || "");
  const surface = surfaces.find((item) => Number(item.id) === surfaceId) ?? surfaces[0];
  if (operation === "revoke" && surface) surface.status = "revoked";
  if (operation === "rollback" && surface) surface.status = "active";
  const rollout: Record<string, unknown> = {
    operation,
    version: rolloutHistory.length + 1,
    created_at: createdAt,
  };
  if (operation === "traffic_split") rollout.traffic_split = body.traffic_split;
  if (operation === "rollback") rollout.rollback_to_version = Number(body.rollback_to_version || 1);
  rollout.audit_preview = { action: `published_surface.${operation}` };
  rolloutHistory.push(rollout);
  return {
    surface,
    rollout,
    rollout_history: rolloutHistory,
    audit: {
      action: `published_surface.${operation}`,
      resource_type: "published_surface",
      resource_id: surfaceId,
      request_id: "e2e-request",
    },
  };
}

function backupDryRunResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  return {
    status: "ready",
    plan_id: Number(body.plan_id || 9),
    targets: Array.isArray(body.targets) ? body.targets.map(String) : [],
    storage_ref: String(body.storage_ref || ""),
    scope_proof: {
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      restore_scope: String(body.scope || "project"),
      proof_generated_at: createdAt,
    },
    validation: {
      valid: true,
      checks: ["scope_bound", "storage_ref_present", "targets_selected"],
    },
    audit: {
      action: "backup.dry_run",
      resource_type: "backup_plan",
      resource_id: Number(body.plan_id || 9),
      request_id: "e2e-request",
    },
  };
}

function restoreDryRunResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  return {
    status: "ready",
    backup_ref: String(body.backup_ref || ""),
    targets: Array.isArray(body.targets) ? body.targets.map(String) : [],
    scope_proof: {
      tenant_id: 1,
      project_id: 1,
      environment: "local",
      restore_scope: String(body.restore_scope || "project"),
      proof_generated_at: createdAt,
    },
    validation: {
      valid: true,
      destructive: body.destructive === true,
      destructive_confirmation_required: "RESTORE PROJECT 1",
    },
    audit: {
      action: "restore.dry_run",
      resource_type: "restore_job",
      resource_id: String(body.backup_ref || ""),
      request_id: "e2e-request",
    },
  };
}

function fulfillRestoreDryRun(route: Route) {
  const body = parseRequestBody(route);
  if (body.destructive === true && body.confirmation !== "RESTORE PROJECT 1") {
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "destructive_restore_confirmation_required",
          message: "Destructive restore requires confirmation.",
          request_id: "e2e-error-request",
          details: {
            validation: {
              valid: false,
              destructive_confirmation_required: "RESTORE PROJECT 1",
            },
          },
        },
      },
    });
  }
  return fulfillJson(route, restoreDryRunResponse(route));
}

function humanTaskDecisionResponse(route: Route, api: DashboardApiFixture, taskId: number, decision: string): unknown {
  const body = parseRequestBody(route);
  const decisionPayload = body.decision_payload && typeof body.decision_payload === "object"
    ? body.decision_payload as Record<string, unknown>
    : {};
  const task = api.humanTasks.items.find((item) => Number(item.id) === taskId);
  if (!task) return makeAdminCollection([]);
  if (!String(decisionPayload.comment || "").trim()) {
    return {
      error_code: "decision_comment_required",
      message: "Approval comment is required for human task decisions.",
      request_id: "e2e-error-request",
      details: { field: "decision_payload.comment", task_id: taskId },
    };
  }
  task.status = decision === "approve" ? "approved" : "rejected";
  task.decision = {
    comment: String(decisionPayload.comment || ""),
    decided_by: String(decisionPayload.decided_by || "console"),
  };
  task.resume_outcome = {
    status: decision === "approve" ? "ready" : "blocked",
    task_id: taskId,
    decision: String(task.status),
  };
  return {
    item: task,
    request_id: "e2e-request",
    audit_required: true,
  };
}

function compatibilityAssistantResponse(
  route: Route,
  assistants: Array<Record<string, unknown>>,
): unknown {
  const body = parseRequestBody(route);
  const assistantId = `assistant_${assistants.length + 1}`;
  const result = {
    operation: "assistant.create",
    compat_response: {
      assistant_id: assistantId,
      name: String(body.name || "support-agent"),
      metadata: {
        dimoorun_mapping: {
          tenant_id: 1,
          project_id: 1,
          deployment_id: null,
          agent_id: 1,
          agent_version_id: 11,
        },
      },
    },
    native_resources: {
      assistant_id: assistantId,
      deployment_id: null,
      agent_id: 1,
      agent_version_id: 11,
      tenant_id: 1,
      project_id: 1,
    },
    resource_links: [{ label: "Agent #1", path: "/agents" }],
    unsupported_capability_explanations: [],
    divergence_reason: null,
    golden_record: {
      operation: "assistant.create",
      divergence_reason: null,
    },
  };
  assistants.unshift(result);
  return result;
}

function compatibilityGetAssistantResponse(
  assistants: Array<Record<string, unknown>>,
  assistantId: string,
): unknown {
  return assistants.find(
    (item) => recordValue(item.compat_response, "assistant_id") === assistantId,
  ) ?? assistants[0];
}

function compatibilityThreadResponse(
  route: Route,
  threads: Array<Record<string, unknown>>,
): unknown {
  const body = parseRequestBody(route);
  const threadId = `thread_${threads.length + 1}`;
  const result = {
    operation: "thread.create",
    compat_response: {
      thread_id: threadId,
      metadata: {
        label: String(recordValue(body.metadata, "label") || "migration-check"),
        dimoorun_mapping: {
          checkpoint_thread_id: threadId,
          tenant_id: 1,
          project_id: 1,
        },
      },
    },
    native_resources: {
      thread_id: threadId,
      checkpoint_thread_id: threadId,
      tenant_id: 1,
      project_id: 1,
    },
    resource_links: [],
    unsupported_capability_explanations: [],
    divergence_reason: null,
    golden_record: {
      operation: "thread.create",
      divergence_reason: null,
    },
  };
  threads.unshift(result);
  return result;
}

function compatibilityGetThreadResponse(
  threads: Array<Record<string, unknown>>,
  threadId: string,
): unknown {
  return threads.find(
    (item) => recordValue(item.compat_response, "thread_id") === threadId,
  ) ?? threads[0];
}

function compatibilityRunResponse(
  route: Route,
  threadId: string,
  assistants: Array<Record<string, unknown>>,
  runs: Array<Record<string, unknown>>,
  runId: number,
  taskId: number,
): unknown {
  const body = parseRequestBody(route);
  const assistantId = String(body.assistant_id || "");
  const assistant = assistants.find(
    (item) => recordValue(item.compat_response, "assistant_id") === assistantId,
  );
  const result = {
    operation: "run.create",
    compat_response: {
      run_id: runId,
      thread_id: threadId,
      assistant_id: assistantId,
      status: "queued",
      metadata: {
        dimoorun_mapping: {
          run_id: runId,
          task_id: taskId,
        },
      },
    },
    native_resources: {
      run_id: runId,
      task_id: taskId,
      thread_id: threadId,
      assistant_id: assistantId,
      deployment_id: recordValue(assistant?.native_resources, "deployment_id"),
      agent_id: recordValue(assistant?.native_resources, "agent_id") || 1,
      agent_version_id: recordValue(assistant?.native_resources, "agent_version_id") || 11,
    },
    resource_links: [
      { label: `Run #${runId}`, path: `/runs/${runId}` },
      { label: `Task #${taskId}`, path: "/tasks" },
      { label: "Agent #1", path: "/agents" },
    ],
    unsupported_capability_explanations: [],
    divergence_reason: null,
    golden_record: {
      operation: "run.create",
      expected_semantics: {
        operation: "run.create",
        compat_resource_type: "run",
        native_source_of_truth: ["run", "task", "event", "audit"],
        sdk_shape: "langgraph.run",
        thread_id: threadId,
        assistant_id: assistantId,
        compat_status: "queued",
        native_run_id: runId,
        native_task_id: taskId,
      },
      divergence_reason: null,
    },
  };
  runs.unshift(result);
  return result;
}

function compatibilityGetRunResponse(
  runs: Array<Record<string, unknown>>,
  threadId: string,
  runId: number,
): unknown {
  return runs.find(
    (item) => Number(recordValue(item.compat_response, "run_id")) === runId
      && recordValue(item.compat_response, "thread_id") === threadId,
  ) ?? runs[0];
}

function compatibilityStreamProbeResponse(
  route: Route,
  threadId: string,
  assistants: Array<Record<string, unknown>>,
  runs: Array<Record<string, unknown>>,
  runId: number,
  taskId: number,
): unknown {
  const result = compatibilityRunResponse(route, threadId, assistants, runs, runId, taskId) as Record<
    string,
    unknown
  >;
  result.operation = "run.stream_probe";
  recordValue(result.compat_response, "status");
  (result.compat_response as Record<string, unknown>).status = "running";
  result.stream_events = [
    { event_id: `${runId}:1`, sequence: 1, type: "run.created", payload: { task_id: taskId } },
    { event_id: `${runId}:2`, sequence: 2, type: "task.queued", payload: { task_id: taskId } },
    { event_id: `${runId}:3`, sequence: 3, type: "run.started", payload: { thread_id: threadId } },
  ];
  result.golden_record = {
    operation: "run.stream_probe",
    expected_semantics: {
      operation: "run.stream_probe",
      compat_resource_type: "run",
      native_source_of_truth: ["run", "task", "event", "audit"],
      sdk_shape: "langgraph.run",
      thread_id: threadId,
      assistant_id: recordValue(result.compat_response, "assistant_id"),
      compat_status: "running",
      native_run_id: runId,
      native_task_id: taskId,
      stream_mode: "events",
      event_types: ["run.created", "task.queued", "run.started"],
    },
    divergence_reason: null,
  };
  result.stream_status = {
    event_count: 3,
    latest_event_id: `${runId}:3`,
    replay_from_event_id: `${runId}:1`,
    run_status: "running",
  };
  return result;
}

function compatibilityStreamStatusResponse(
  runs: Array<Record<string, unknown>>,
  threadId: string,
  runId: number,
): unknown {
  const run = compatibilityGetRunResponse(runs, threadId, runId) as Record<string, unknown>;
  return {
    ...run,
    operation: "run.stream_status",
    golden_record: {
      operation: "run.stream_status",
      expected_semantics: {
        operation: "run.stream_status",
        compat_resource_type: "run",
        native_source_of_truth: ["run", "task", "event", "audit"],
        sdk_shape: "langgraph.run",
        thread_id: threadId,
        assistant_id: recordValue(recordValue(run, "compat_response") as Record<string, unknown>, "assistant_id"),
        compat_status: recordValue(run.compat_response, "status") || "running",
        native_run_id: runId,
        native_task_id: Number(recordValue(recordValue(run, "native_resources") as Record<string, unknown>, "task_id") || 0),
        supports_last_event_id_replay: true,
        latest_event_id: `${runId}:3`,
        replay_from_event_id: `${runId}:1`,
      },
      divergence_reason: null,
    },
    stream_status: {
      event_count: 3,
      latest_event_id: `${runId}:3`,
      replay_from_event_id: `${runId}:1`,
      run_status: recordValue(run.compat_response, "status") || "running",
    },
  };
}

function compatibilityReplayResponse(
  route: Route,
  runs: Array<Record<string, unknown>>,
  threadId: string,
  runId: number,
): unknown {
  const url = new URL(route.request().url());
  const lastEventId = url.searchParams.get("last_event_id") || `${runId}:1`;
  const run = compatibilityGetRunResponse(runs, threadId, runId) as Record<string, unknown>;
  const events = lastEventId === `${runId}:1`
    ? [
      { event_id: `${runId}:2`, sequence: 2, type: "task.queued", payload: { task_id: runId + 1000 } },
      { event_id: `${runId}:3`, sequence: 3, type: "run.started", payload: { thread_id: threadId } },
    ]
    : [
      { event_id: `${runId}:3`, sequence: 3, type: "run.started", payload: { thread_id: threadId } },
    ];
  return {
    ...run,
    operation: "run.replay",
    golden_record: {
      operation: "run.replay",
      expected_semantics: {
        operation: "run.replay",
        compat_resource_type: "run",
        native_source_of_truth: ["run", "task", "event", "audit"],
        sdk_shape: "langgraph.run",
        thread_id: threadId,
        assistant_id: recordValue(recordValue(run, "compat_response") as Record<string, unknown>, "assistant_id"),
        compat_status: recordValue(run.compat_response, "status") || "running",
        native_run_id: runId,
        native_task_id: Number(recordValue(recordValue(run, "native_resources") as Record<string, unknown>, "task_id") || 0),
        supports_last_event_id_replay: true,
        replayed_event_types: events.map((event) => String(recordValue(event, "type") || "")),
      },
      divergence_reason: null,
    },
    stream_events: events,
  };
}

function compatibilityRunActionResponse(
  runs: Array<Record<string, unknown>>,
  threadId: string,
  runId: number,
  status: string,
  operation: string,
): unknown {
  const run = runs.find(
    (item) => Number(recordValue(item.compat_response, "run_id")) === runId
      && recordValue(item.compat_response, "thread_id") === threadId,
  ) ?? runs[0];
  if (run) {
    (run.compat_response as Record<string, unknown>).status = status;
    run.operation = operation;
    run.golden_record = {
      operation,
      expected_semantics: {
        operation,
        compat_resource_type: "run",
        native_source_of_truth: ["run", "task", "event", "audit"],
        sdk_shape: "langgraph.run",
        thread_id: threadId,
        assistant_id: recordValue(run.compat_response, "assistant_id"),
        compat_status: status,
        native_run_id: runId,
        native_task_id: Number(recordValue(run.native_resources, "task_id") || 0),
      },
      divergence_reason: null,
    };
  }
  return run;
}

function compatibilityMigrationReportResponse(route: Route): unknown {
  const body = parseRequestBody(route);
  const capabilities = Array.isArray(body.capabilities) ? body.capabilities.map(String) : [];
  const unsupported = capabilities.includes("hosted_deployments")
    ? [
      {
        capability: "hosted_deployments",
        reason: "compatibility_not_supported",
        recommended_workaround: "Use native DimooRun runtime semantics for this feature.",
      },
    ]
    : [];
  return {
    report: {
      framework: String(body.framework || "langgraph"),
      adapter: String(body.adapter || "langgraph"),
      overall_status: unsupported.length > 0 ? "migration_required" : "compatible",
      blocked_reason: null,
      unsupported_capabilities: unsupported,
      required_dimoorun_config: [
        "project.name",
        "agents[].manifest",
        "execution_profiles.default",
        "checkpoint runtime store",
      ],
      adapter_contract_version: "1.0",
      checkpoint_requirements: {
        required: body.uses_checkpointing === true,
        mode: body.uses_checkpointing === true ? "native_runtime_store" : "optional",
      },
      streaming_support: {
        requested_modes: Array.isArray(body.streaming_modes) ? body.streaming_modes : [],
        supported_modes: ["events", "updates"],
        unsupported_modes: [],
        last_event_id_replay: true,
      },
      governance_implications: [
        "Compatibility requests still require tenant and project scoped authentication.",
      ],
      recommended_actions: [
        "Run the compatibility explorer to confirm native Run and Task creation.",
      ],
      remediation_steps: unsupported.length > 0
        ? [
          {
            capability: "hosted_deployments",
            reason: "compatibility_not_supported",
            severity: "manual_migration_required",
            target_files: ["dimoorun.yaml", "manifest.yaml"],
            recommended_action: "Use native deployments for hosted runtime behavior",
            verification_command: "uv run dimoorun deployment create --help",
            native_route: "/deployments",
          },
        ]
        : [],
    },
    golden_record: {
      operation: "migration.report",
      expected_semantics: {
        framework: String(body.framework || "langgraph"),
        adapter: String(body.adapter || "langgraph"),
        capabilities,
        streaming_modes: Array.isArray(body.streaming_modes) ? body.streaming_modes : [],
        supports_last_event_id_replay: true,
      },
      divergence_reason: unsupported.length > 0 ? "compatibility_not_supported" : null,
    },
    request_id: "e2e-request",
  };
}

function fulfillAuthLogin(route: Route) {
  const body = parseRequestBody(route);
  const email = String(body.email || "");
  const password = String(body.password || "");
  if (!email || !password) {
    return route.fulfill({
      status: 400,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "auth_invalid_credentials",
          message: "Email and password are required.",
          request_id: "e2e-error-request",
          details: { field: !email ? "email" : "password" },
        },
      },
    });
  }
  return fulfillJson(route, {
    access_token: "sess_e2e_session",
    token_type: "bearer",
    operator: e2eOperator,
  });
}

function runtimeMetricsSummary(
  api: DashboardApiFixture,
  workers: RuntimeWorkerFixture[],
  incidents: Array<Record<string, unknown>>,
): Record<string, unknown> {
  return {
    summary: dashboardSummary(api.deployments, api.runs, api.humanTasks.items, incidents),
    queues: [
      {
        queue: "default",
        queue_backlog: api.deployments.reduce((total, item) => total + item.replicas, 0),
        running_tasks: api.runs.filter((item) => item.status === "pending").length,
        leased_tasks: 0,
        retrying_tasks: 1,
        dead_letters: api.runs.filter((item) => item.status === "failed").length,
        oldest_task_age_seconds: 48,
      },
    ],
    workers: workers.map((worker) => ({
      worker_id: worker.worker_id,
      heartbeat_age_seconds: worker.heartbeat_age_seconds,
      readiness: worker.readiness,
      liveness: worker.liveness,
      active_attempts: worker.active_attempts,
      retrying_tasks: worker.retrying_tasks,
      dead_letter_tasks: worker.dead_letter_tasks,
    })),
    active_incidents: api.runs
      .filter((item) => item.status === "failed")
      .map((item) => ({
        run_id: item.id,
        status: item.status,
        error_summary: String(item.error?.message || "provider outage"),
        created_at: item.created_at,
      })),
    trend_points: [
      { label: "06-10 09:00", runs: 1, success_rate: 1 },
      { label: "06-10 10:00", runs: 1, success_rate: 0 },
      { label: "06-10 11:00", runs: 1, success_rate: 0.5 },
    ],
  };
}

function createAgentResponse(route: Route, api: DashboardApiFixture): NativeAgentRead {
  const body = parseRequestBody(route);
  const agent: NativeAgentRead = {
    id: nextNumericId(api.agents),
    name: String(body.name || `agent-${api.agents.length + 1}`),
    description: typeof body.description === "string" ? body.description : null,
    status: "active",
    created_at: createdAt,
  };
  api.agents.unshift(agent);
  return agent;
}

function updateAgentResponse(
  route: Route,
  api: DashboardApiFixture,
  agentId: number,
): NativeAgentRead {
  const body = parseRequestBody(route);
  const agent = api.agents.find((item) => item.id === agentId) ?? api.agents[0];
  agent.name = String(body.name || agent.name);
  agent.description = typeof body.description === "string" ? body.description : agent.description;
  if (typeof body.status === "string") {
    agent.status = body.status;
  }
  return agent;
}

function archiveAgentResponse(api: DashboardApiFixture, agentId: number): NativeAgentRead {
  const index = api.agents.findIndex((item) => item.id === agentId);
  const [agent] = index >= 0 ? api.agents.splice(index, 1) : [api.agents[0]];
  return agent;
}

function createAgentVersionResponse(
  route: Route,
  api: DashboardApiFixture,
  agentId: number,
): NativeAgentVersionRead {
  const body = parseRequestBody(route);
  const version: NativeAgentVersionRead = {
    id: nextNumericId(api.versions),
    agent_id: agentId,
    version: String(body.version || `0.0.${api.versions.length + 1}`),
    package_uri: String(body.package_uri || "oci://registry.local/generated-agent:latest"),
    framework: String(body.framework || "langgraph"),
    adapter: String(body.adapter || "langgraph"),
    entrypoint: String(body.entrypoint || "agent:create_agent"),
    capabilities: asRecord(body.capabilities) ?? { invoke: true, stream: true },
    manifest: asRecord(body.manifest) ?? { runtime: { entrypoint: String(body.entrypoint || "agent:create_agent") } },
    status: String(body.status || "ready"),
  };
  api.versions.unshift(version);
  return version;
}

function fulfillAgentVersionCreate(
  route: Route,
  api: DashboardApiFixture,
  agentId: number,
) {
  const body = parseRequestBody(route);
  if (String(body.status || "draft") === "ready" && !hasMockValidationToken(body)) {
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "package_validation_required",
          message: "Agent version must have a valid package validation token before it can become ready.",
          request_id: "e2e-error-request",
          details: {
            package_uri: String(body.package_uri || ""),
            status: "ready",
            required_action: "POST /v1/packages/validate",
          },
        },
      },
    });
  }
  return fulfillJson(route, createAgentVersionResponse(route, api, agentId));
}

function updateAgentVersionResponse(
  route: Route,
  api: DashboardApiFixture,
  agentId: number,
  versionValue: string,
): NativeAgentVersionRead {
  const body = parseRequestBody(route);
  const version = api.versions.find((item) => item.agent_id === agentId && item.version === versionValue) ?? api.versions[0];
  version.version = String(body.version || version.version);
  version.package_uri = String(body.package_uri || version.package_uri);
  version.framework = String(body.framework || version.framework);
  version.adapter = String(body.adapter || version.adapter);
  version.entrypoint = String(body.entrypoint || version.entrypoint);
  version.capabilities = asRecord(body.capabilities) ?? version.capabilities;
  version.manifest = asRecord(body.manifest) ?? version.manifest;
  version.status = String(body.status || version.status);
  return version;
}

function archiveAgentVersionResponse(
  api: DashboardApiFixture,
  agentId: number,
  versionValue: string,
): NativeAgentVersionRead {
  const index = api.versions.findIndex((item) => item.agent_id === agentId && item.version === versionValue);
  const [version] = index >= 0 ? api.versions.splice(index, 1) : [api.versions[0]];
  return version;
}

function createDeploymentResponse(route: Route, api: DashboardApiFixture): NativeDeploymentRead {
  const body = parseRequestBody(route);
  const deployment: NativeDeploymentRead = {
    id: nextNumericId(api.deployments),
    tenant_id: 1,
    project_id: 1,
    agent_id: Number(body.agent_id || 1),
    agent_version_id: Number(body.agent_version_id || 11),
    environment: String(body.environment || "production"),
    desired_status: String(body.desired_status || "draft") as NativeDeploymentRead["desired_status"],
    runtime_status: "not_loaded",
    replicas: Number(body.replicas || 1),
    config: asRecord(body.config) ?? {},
    last_runtime_error: null,
  };
  api.deployments.unshift(deployment);
  return deployment;
}

function updateDeploymentResponse(
  route: Route,
  api: DashboardApiFixture,
  deploymentId: number,
): NativeDeploymentRead {
  const body = parseRequestBody(route);
  const deployment = api.deployments.find((item) => item.id === deploymentId) ?? api.deployments[0];
  deployment.agent_version_id = Number(body.agent_version_id || deployment.agent_version_id);
  deployment.environment = String(body.environment || deployment.environment);
  deployment.replicas = Number(body.replicas || deployment.replicas);
  deployment.config = asRecord(body.config) ?? deployment.config;
  return deployment;
}

function archiveDeploymentResponse(
  api: DashboardApiFixture,
  deploymentId: number,
): NativeDeploymentRead {
  const index = api.deployments.findIndex((item) => item.id === deploymentId);
  const [deployment] = index >= 0 ? api.deployments.splice(index, 1) : [api.deployments[0]];
  return deployment;
}

function createDeploymentTaskResponse(
  route: Route,
  api: DashboardApiFixture,
  deploymentId: number,
): Record<string, unknown> {
  const body = parseRequestBody(route);
  const deployment = api.deployments.find((item) => item.id === deploymentId) ?? api.deployments[0];
  const runId = nextNumericId(api.runs);
  const taskId = runId + 4000;
  api.runs.unshift({
    id: runId,
    tenant_id: 1,
    project_id: 1,
    agent_id: deployment.agent_id,
    agent_version_id: deployment.agent_version_id,
    deployment_id: deployment.id,
    status: "pending",
    thread_id: typeof body.thread_id === "string" ? body.thread_id : `thread-${runId}`,
    input: asRecord(body.input) ?? {},
    output: null,
    error: null,
    created_at: createdAt,
    started_at: null,
    finished_at: null,
    latency_ms: null,
  });
  return {
    run_id: runId,
    task_id: taskId,
    status: "accepted",
    replayed: false,
  };
}

function nextNumericId(items: Array<{ id: number }>): number {
  return items.reduce((maxId, item) => Math.max(maxId, item.id), 0) + 1;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function responseForPath(path: string, api: DashboardApiFixture): unknown {
  if (path === "/v1/console/dashboard-summary") return api.runtimeOverview.summary;
  if (path === "/v1/console/runtime-overview") return api.runtimeOverview;
  if (path === "/v1/console/deployment-health") return api.runtimeOverview.deployment_health;
  if (path === "/v1/console/worker-health") return api.runtimeOverview.worker_health;
  if (path === "/v1/console/recent-failures") return api.runtimeOverview.recent_failures;
  if (path === "/v1/console/pending-actions") return api.runtimeOverview.pending_actions;
  if (path === "/v1/console/action-summary") return { actions: [] };
  if (path === "/v1/agents") return api.agents;
  if (path === "/v1/deployments") return api.deployments;
  if (path === "/v1/runs") return api.runs;
  if (path === "/v1/human-tasks") return api.humanTasks;
  if (path === "/v1/incidents") return api.incidents;
  if (path === "/v1/audit-logs") return observabilityAuditLogs();
  if (path === "/v1/artifacts") return observabilityArtifacts();
  if (path === "/v1/evaluations/results") return observabilityEvaluationResults();
  if (path === "/v1/feedback") return observabilityFeedback();
  if (path === "/v1/replay-jobs") return observabilityReplayJobs();
  const versionsMatch = path.match(/^\/v1\/agents\/(\d+)\/versions$/);
  if (versionsMatch) {
    return api.versions.filter((item) => item.agent_id === Number(versionsMatch[1]));
  }
  if (path === "/v1/identity/tenants") return makeAdminCollection([{ id: 1, name: "Local Tenant" }]);
  if (path === "/v1/identity/projects") return makeAdminCollection([{ id: 1, name: "DimooRun" }]);
  if (path === "/v1/identity/permissions") {
    return makeAdminCollection([
      { id: 1, code: "admin:read", resource: "admin", action: "read", status: "active" },
      { id: 2, code: "identity:role:write", resource: "identity:role", action: "write", status: "active" },
      { id: 3, code: "identity:service-account:write", resource: "identity:service_account", action: "write", status: "active" },
      { id: 4, code: "run:read", resource: "run", action: "read", status: "active" },
    ]);
  }
  if (path === "/v1/identity/roles") {
    return makeAdminCollection([
      { id: 11, name: "platform_admin", permissions: ["admin:read", "identity:role:write", "run:read"] },
      { id: 12, name: "runtime_operator", permissions: ["run:read"] },
    ]);
  }
  return makeAdminCollection([]);
}

function observabilityAuditLogs(): AdminCollectionResponse<Record<string, unknown>> {
  return makeAdminCollection([
    {
      id: 1401,
      action: "policy.activate",
      actor: "operator",
      resource_type: "policy",
      resource_id: 42,
      policy_id: 42,
      run_id: 1001,
      deployment_id: 10,
      status: "allowed",
      request_id: "req-policy-activate",
      created_at: createdAt,
      updated_at: createdAt,
    },
  ]);
}

function observabilityArtifacts(): AdminCollectionResponse<Record<string, unknown>> {
  return makeAdminCollection([
    {
      id: 1501,
      name: "failure-trace.json",
      artifact_type: "trace",
      status: "active",
      run_id: 1001,
      deployment_id: 10,
      storage_ref: "s3://dimoorun-artifacts/runs/1001/failure-trace.json",
      metadata: { content_type: "application/json", bytes: 2048 },
      created_at: createdAt,
      updated_at: createdAt,
    },
  ]);
}

function observabilityEvaluationResults(): AdminCollectionResponse<Record<string, unknown>> {
  return makeAdminCollection([
    {
      id: 1601,
      name: "refund-policy-regression",
      status: "failed",
      result: "failed",
      metric: "Pass rate",
      pass_rate: 0.66,
      run_id: 1001,
      deployment_id: 10,
      dataset_name: "support-regression",
      created_at: createdAt,
      updated_at: createdAt,
    },
    {
      id: 1602,
      name: "checkout-latency",
      status: "succeeded",
      result: "passed",
      metric: "Accuracy",
      pass_rate: 1,
      run_id: 1002,
      deployment_id: 10,
      dataset_name: "latency-baseline",
      created_at: createdAt,
      updated_at: createdAt,
    },
  ]);
}

function observabilityFeedback(): AdminCollectionResponse<Record<string, unknown>> {
  return makeAdminCollection([
    {
      id: 1701,
      name: "refund answer missed policy",
      source: "console",
      status: "open",
      sentiment: "negative",
      run_id: 1001,
      deployment_id: 10,
      comment: "Agent skipped the required retention explanation.",
      created_at: createdAt,
      updated_at: createdAt,
    },
  ]);
}

function observabilityReplayJobs(): AdminCollectionResponse<Record<string, unknown>> {
  return makeAdminCollection([
    {
      id: 1801,
      name: "refund-policy-replay",
      status: "failed",
      run_id: 1001,
      source_run_id: 1001,
      deployment_id: 10,
      replay_run_id: 1004,
      created_at: createdAt,
      updated_at: createdAt,
    },
  ]);
}

function fulfillIdentityRolePreview(
  route: Route,
  roles: Array<Record<string, unknown>>,
  operators: Array<Record<string, unknown>>,
  roleId: number,
  mode: string,
) {
  const role = roles.find((item) => Number(item.id) === roleId);
  if (!role) return fulfillError(route, new Error(`Role ${roleId} not found`));
  const permissions = parseStringList(parseRequestBody(route).permissions);
  const currentPermissions = parseStringList(role.permissions);
  const previewPermissions = [...new Set(permissions)];
  const added = previewPermissions.filter((item) => !currentPermissions.includes(item));
  const removed = currentPermissions.filter((item) => !previewPermissions.includes(item));
  const required = ["admin:read", "identity:role:write"];
  const warnings = required.every((item) => previewPermissions.includes(item))
    ? []
    : [{
      code: "self_lockout_risk",
      message: "Preview removes permissions required to continue role governance for the current operator.",
      required_permissions: required,
      missing_permissions: required.filter((item) => !previewPermissions.includes(item)),
    }];
  if (mode === "apply" && route.request().headers()["x-audit-reason"]?.trim().length === 0) {
    return route.fulfill({
      status: 400,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "audit_reason_required",
          message: "Audit reason is required for role permission changes.",
          request_id: "e2e-error-request",
          details: { field: "audit_reason" },
        },
      },
    });
  }
  if (mode === "apply" && warnings.length > 0) {
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "self_lockout_blocked",
          message: "Current operator cannot remove permissions required for identity governance.",
          request_id: "e2e-error-request",
          details: { warnings },
        },
      },
    });
  }
  if (mode === "apply") {
    role.permissions = previewPermissions;
    const self = operators.find((item) => Number(item.id) === 1);
    if (self) self.permissions = previewPermissions;
  }
  return fulfillJson(route, {
    item: {
      role_id: roleId,
      role_name: String(role.name || roleId),
      current_permissions: currentPermissions,
      preview_permissions: previewPermissions,
      change: {
        added,
        removed,
        unchanged: previewPermissions.filter((item) => currentPermissions.includes(item)),
      },
      affected_operators: operators
        .filter((item) => Array.isArray(item.roles) && item.roles.includes(role.name))
        .map((item) => ({
          operator_id: item.id,
          email: item.email,
          name: item.name,
          current_permissions: currentPermissions,
          preview_permissions: previewPermissions,
        })),
      affected_service_accounts: [],
      warnings,
      policy_conflicts: warnings,
    },
    request_id: "e2e-request",
  });
}

function operatorAccessDetailResponse(
  operators: Array<Record<string, unknown>>,
  operatorId: number,
): Record<string, unknown> {
  const operator = operators.find((item) => Number(item.id) === operatorId) ?? operators[0];
  return {
    item: {
      ...serviceSafeClone(operator),
      active_sessions: serviceSafeClone(operator.active_sessions),
      api_keys_created: serviceSafeClone(operator.api_keys_created),
      recent_audit_actions: serviceSafeClone(operator.recent_audit_actions),
      disable_impact: {
        active_session_count: Array.isArray(operator.active_sessions) ? operator.active_sessions.length : 0,
        api_keys_created_count: Array.isArray(operator.api_keys_created) ? operator.api_keys_created.length : 0,
      },
    },
    request_id: "e2e-request",
  };
}

function fulfillIdentitySessionRevoke(
  route: Route,
  operators: Array<Record<string, unknown>>,
  operatorId: number,
  sessionId: number,
) {
  const operator = operators.find((item) => Number(item.id) === operatorId);
  const sessions = Array.isArray(operator?.active_sessions) ? operator.active_sessions as Array<Record<string, unknown>> : [];
  const activeSessionCount = sessions.filter((item) => item.status === "active").length;
  if (operatorId === 1 && activeSessionCount <= 1) {
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "self_lockout_blocked",
          message: "Current operator cannot revoke the last active identity session.",
          request_id: "e2e-error-request",
          details: { operator_id: operatorId, session_id: sessionId },
        },
      },
    });
  }
  const session = sessions.find((item) => Number(item.id) === sessionId);
  if (session) {
    operator!.active_sessions = sessions.filter((item) => Number(item.id) !== sessionId);
  }
  return fulfillJson(route, { ok: true, request_id: "e2e-request" });
}

function serviceAccountSummary(serviceAccount: Record<string, unknown>): Record<string, unknown> {
  return {
    id: serviceAccount.id,
    tenant_id: serviceAccount.tenant_id,
    project_id: serviceAccount.project_id,
    name: serviceAccount.name,
    permissions: serviceAccount.permissions,
    status: serviceAccount.status,
    created_by: serviceAccount.created_by,
    created_at: serviceAccount.created_at,
    last_used_at: serviceAccount.last_used_at,
  };
}

function serviceAccountDetailResponse(
  accounts: Array<Record<string, unknown>>,
  serviceAccountId: number,
): Record<string, unknown> {
  const account = accounts.find((item) => Number(item.id) === serviceAccountId) ?? accounts[0];
  return {
    item: {
      ...serviceSafeClone(account),
      api_keys: serviceSafeClone(account.api_keys),
      dependent_deployments: serviceSafeClone(account.dependent_deployments),
    },
    request_id: "e2e-request",
  };
}

function fulfillIdentityServiceAccountPatch(
  route: Route,
  accounts: Array<Record<string, unknown>>,
  serviceAccountId: number,
) {
  const account = accounts.find((item) => Number(item.id) === serviceAccountId);
  if (!account) return fulfillError(route);
  Object.assign(account, parseRequestBody(route));
  return fulfillJson(route, { item: serviceAccountSummary(account), request_id: "e2e-request" });
}

function fulfillIdentityCreateApiKey(
  route: Route,
  accounts: Array<Record<string, unknown>>,
  serviceAccountId: number,
) {
  const account = accounts.find((item) => Number(item.id) === serviceAccountId);
  if (!account) return fulfillError(route);
  const payload = parseRequestBody(route);
  const apiKeys = account.api_keys as Array<Record<string, unknown>>;
  const nextId = Math.max(0, ...apiKeys.map((item) => Number(item.id))) + 1;
  const key = {
    id: nextId,
    name: String(payload.name || `key-${nextId}`),
    key_prefix: `dmr_${nextId}`,
    scopes: parseStringList(payload.scopes),
    status: "active",
    last_used_at: null,
    expires_at: typeof payload.expires_at === "string" ? payload.expires_at : null,
    scope_diff: scopeDiff(parseStringList(account.permissions), parseStringList(payload.scopes)),
  };
  apiKeys.unshift(key);
  return fulfillJson(route, {
    item: key,
    plain_key: `dmr_secret_${nextId}`,
    request_id: "e2e-request",
  });
}

function fulfillIdentityApiKeyAction(
  route: Route,
  accounts: Array<Record<string, unknown>>,
  serviceAccountId: number,
  keyId: number,
  action: string,
) {
  const key = findServiceAccountKey(accounts, serviceAccountId, keyId);
  if (!key) return fulfillError(route);
  key.status = action === "enable" ? "active" : "disabled";
  return fulfillJson(route, { item: key, request_id: "e2e-request" });
}

function fulfillIdentityRotateKey(
  route: Route,
  accounts: Array<Record<string, unknown>>,
  serviceAccountId: number,
  keyId: number,
) {
  const account = accounts.find((item) => Number(item.id) === serviceAccountId);
  const currentKey = findServiceAccountKey(accounts, serviceAccountId, keyId);
  if (!account || !currentKey) return fulfillError(route);
  const payload = parseRequestBody(route);
  const apiKeys = account.api_keys as Array<Record<string, unknown>>;
  const nextId = Math.max(0, ...apiKeys.map((item) => Number(item.id))) + 1;
  currentKey.status = "disabled";
  const scopes = parseStringList(payload.scopes).length > 0 ? parseStringList(payload.scopes) : parseStringList(currentKey.scopes);
  const rotated = {
    id: nextId,
    name: String(payload.name || `${String(currentKey.name || currentKey.id)}-rotated`),
    key_prefix: `dmr_rot_${nextId}`,
    scopes,
    status: "active",
    last_used_at: null,
    expires_at: typeof payload.expires_at === "string" ? payload.expires_at : null,
    scope_diff: scopeDiff(parseStringList(account.permissions), scopes),
  };
  apiKeys.unshift(rotated);
  return fulfillJson(route, {
    item: rotated,
    plain_key: `dmr_rotated_secret_${nextId}`,
    rotated_from: currentKey,
    scope_diff: rotated.scope_diff,
    request_id: "e2e-request",
  });
}

function fulfillIdentityExpireKey(
  route: Route,
  accounts: Array<Record<string, unknown>>,
  serviceAccountId: number,
  keyId: number,
) {
  const key = findServiceAccountKey(accounts, serviceAccountId, keyId);
  if (!key) return fulfillError(route);
  key.status = "expired";
  return fulfillJson(route, { item: key, request_id: "e2e-request" });
}

function findServiceAccountKey(
  accounts: Array<Record<string, unknown>>,
  serviceAccountId: number,
  keyId: number,
): Record<string, unknown> | undefined {
  const account = accounts.find((item) => Number(item.id) === serviceAccountId);
  const apiKeys = Array.isArray(account?.api_keys) ? account.api_keys as Array<Record<string, unknown>> : [];
  return apiKeys.find((item) => Number(item.id) === keyId);
}

function scopeDiff(base: string[], scopes: string[]): Record<string, unknown> {
  return {
    added: scopes.filter((item) => !base.includes(item)),
    removed: base.filter((item) => !scopes.includes(item)),
    unchanged: scopes.filter((item) => base.includes(item)),
  };
}

function parseStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function serviceSafeClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function promotionPreviewResponse(
  api: DashboardApiFixture,
  deploymentId: number,
  candidateVersionId: number,
  experimentRunId: number,
): unknown {
  const deployment = api.deployments.find((item) => item.id === deploymentId);
  if (!deployment) return makeAdminCollection([]);
  const activeRuns = api.runs.filter((item) => item.deployment_id === deploymentId).length;
  const qualityGate = {
    status: experimentRunId === 401 ? "passed" : "failed",
    promotion_allowed: experimentRunId === 401,
    blocked_reason: experimentRunId === 401 ? null : "quality_gate_failed",
    required_evidence: ["experiment_run", "evaluation_results"],
    evidence: {
      experiment_run_id: experimentRunId,
      candidate_agent_version_id: candidateVersionId,
      average_score: experimentRunId === 401 ? 1 : 0,
      min_score: 0.8,
    },
  };
  return {
    deployment_id: deployment.id,
    environment: deployment.environment,
    desired_status: deployment.desired_status,
    runtime_status: deployment.runtime_status,
    current_agent_version_id: deployment.agent_version_id,
    candidate_agent_version_id: candidateVersionId,
    active_runs: activeRuns,
    queued_tasks: 1,
    candidate_validation_status: "ready",
    rollback_agent_version_id: deployment.agent_version_id,
    required_permissions: ["agent:deploy"],
    audit_required: true,
    can_promote: qualityGate.promotion_allowed,
    blocked_reason: qualityGate.blocked_reason,
    warnings: ["active_runs_will_continue_on_current_version", "queued_tasks_will_use_current_version"],
    quality_gate: qualityGate,
  };
}

function fulfillPromotion(route: Route, api: DashboardApiFixture, deploymentId: number) {
  const body = parseRequestBody(route);
  const reason = String(body.rollout_reason || "");
  if (reason.includes("policy freeze")) {
    return route.fulfill({
      status: 403,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "policy_denied",
          message: "production freeze",
          request_id: "e2e-error-request",
          details: { deployment_id: deploymentId },
        },
      },
    });
  }
  if (reason.includes("stale")) {
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "deployment_version_conflict",
          message: "Deployment version changed after the promotion workflow was prepared.",
          request_id: "e2e-error-request",
          details: { deployment_id: deploymentId },
        },
      },
    });
  }
  if (Number(body.experiment_run_id || 0) !== 401) {
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      json: {
        detail: {
          error_code: "quality_gate_failed",
          message: "Deployment promotion requires a passing quality gate preview for the candidate version.",
          request_id: "e2e-error-request",
          details: {
            deployment_id: deploymentId,
            experiment_run_id: Number(body.experiment_run_id || 0),
          },
        },
      },
    });
  }
  const deployment = api.deployments.find((item) => item.id === deploymentId);
  if (!deployment) return fulfillError(route);
  const previousVersionId = deployment.agent_version_id;
  deployment.agent_version_id = Number(body.candidate_version_id);
  deployment.config = {
    ...deployment.config,
    promotion: {
      previous_agent_version_id: previousVersionId,
      current_agent_version_id: deployment.agent_version_id,
      experiment_run_id: Number(body.experiment_run_id || 0),
      quality_gate: {
        status: "passed",
        promotion_allowed: true,
        evidence: {
          experiment_run_id: Number(body.experiment_run_id || 0),
          candidate_agent_version_id: deployment.agent_version_id,
        },
      },
      rollout_reason: reason,
    },
  };
  return fulfillJson(route, deployment);
}

function fulfillRollback(route: Route, api: DashboardApiFixture, deploymentId: number) {
  const body = parseRequestBody(route);
  const deployment = api.deployments.find((item) => item.id === deploymentId);
  if (!deployment) return fulfillError(route);
  const promotion = deployment.config.promotion && typeof deployment.config.promotion === "object"
    ? deployment.config.promotion as Record<string, unknown>
    : {};
  const rollbackVersionId = Number(body.rollback_agent_version_id || promotion.previous_agent_version_id || 11);
  const previousVersionId = deployment.agent_version_id;
  deployment.agent_version_id = rollbackVersionId;
  deployment.config = {
    ...deployment.config,
    promotion: {
      ...promotion,
      previous_agent_version_id: previousVersionId,
      current_agent_version_id: rollbackVersionId,
      rollback_reason: String(body.rollback_reason || ""),
    },
  };
  return fulfillJson(route, deployment);
}

function controlDeploymentResponse(api: DashboardApiFixture, deploymentId: number, operation: string): NativeDeploymentRead {
  const deployment = api.deployments.find((item) => item.id === deploymentId);
  if (!deployment) throw new Error(`Deployment ${deploymentId} not found`);
  if (operation === "pause") deployment.desired_status = "paused";
  if (operation === "resume" || operation === "activate" || operation === "restart") deployment.desired_status = "active";
  if (operation === "drain") deployment.desired_status = "draining";
  if (operation === "stop") {
    deployment.desired_status = "stopped";
    deployment.runtime_status = "stopped";
  }
  return deployment;
}

function packageValidationResponse(body: Record<string, unknown>): unknown {
  const framework = String(body.framework || "");
  const adapter = String(body.adapter || "");
  const entrypoint = String(body.entrypoint || "");
  const manifest = body.manifest && typeof body.manifest === "object"
    ? body.manifest as Record<string, unknown>
    : {};
  const runtime = manifest.runtime && typeof manifest.runtime === "object"
    ? manifest.runtime as Record<string, unknown>
    : {};
  const errors: Array<{ field: string; code: string; message: string }> = [];
  if (framework !== adapter) {
    errors.push({
      field: "runtime",
      code: "unsupported_runtime_pair",
      message: "Framework and adapter must use a supported runtime pair.",
    });
  }
  if (runtime.entrypoint !== entrypoint) {
    errors.push({
      field: "manifest.runtime",
      code: "manifest_runtime_mismatch",
      message: "Manifest runtime must match the requested framework, adapter, and entrypoint.",
    });
  }
  const secretRefs = Array.isArray(manifest.secrets)
    ? manifest.secrets.flatMap((item) => {
      if (typeof item === "string") return [item];
      if (item && typeof item === "object" && typeof (item as { ref?: unknown }).ref === "string") {
        return [(item as { ref: string }).ref];
      }
      return [];
    })
    : [];
  const requiredSecretRefs = Array.isArray(body.required_secret_refs)
    ? body.required_secret_refs.filter((item): item is string => typeof item === "string")
    : [];
  const missingSecretRefs = requiredSecretRefs.filter((item) => !secretRefs.includes(item));
  for (const missingSecretRef of missingSecretRefs) {
    errors.push({
      field: "required_secret_refs",
      code: "required_secret_missing",
      message: `Required secret reference is missing from manifest: ${missingSecretRef}`,
    });
  }
  const capabilities = manifest.capabilities && typeof manifest.capabilities === "object" && !Array.isArray(manifest.capabilities)
    ? manifest.capabilities as Record<string, unknown>
    : {};
  for (const capability of Object.keys(capabilities)) {
    if (!supportedPackageCapabilities.has(capability)) {
      errors.push({
        field: "manifest.capabilities",
        code: "unsupported_capability",
        message: `Capability is not supported by the runtime compatibility policy: ${capability}`,
      });
    }
  }
  const warnings = dependencyWarnings(manifest);
  if (errors.length > 0) {
    return {
      status: "invalid",
      ready: false,
      validation_token: null,
      errors,
      warnings,
      missing_secret_refs: missingSecretRefs,
      capabilities,
      next_action: "fix_validation_errors",
    };
  }
  return {
    status: "valid",
    ready: true,
    validation_token: "pkgval_e2e",
    errors: [],
    warnings,
    missing_secret_refs: [],
    capabilities: { invoke: true },
    next_action: "create_ready_agent_version",
  };
}

function hasMockValidationToken(body: Record<string, unknown>): boolean {
  const manifest = asRecord(body.manifest);
  const runtime = manifest ? asRecord(manifest.runtime) : null;
  return Boolean(
    manifest
    && manifest.validation_token === "pkgval_e2e"
    && runtime
    && runtime.framework === body.framework
    && runtime.adapter === body.adapter
    && runtime.entrypoint === body.entrypoint,
  );
}

function dependencyWarnings(manifest: Record<string, unknown>): string[] {
  const dependencies = manifest.dependencies;
  if (dependencies === undefined || dependencies === null) return [];
  if (!Array.isArray(dependencies)) {
    return ["Manifest dependencies should be a list of objects with name and version."];
  }
  const warnings: string[] = [];
  for (const dependency of dependencies) {
    if (!dependency || typeof dependency !== "object" || Array.isArray(dependency)) {
      warnings.push(`Dependency entry must be an object with name and version: ${String(dependency)}`);
      continue;
    }
    const item = dependency as Record<string, unknown>;
    if (typeof item.name !== "string" || item.name.length === 0) {
      warnings.push("Dependency entry must include a non-empty name.");
      continue;
    }
    if (typeof item.version !== "string" || item.version.length === 0) {
      warnings.push(`Dependency ${item.name} does not declare a version.`);
    }
  }
  return warnings;
}

function dashboardSummary(
  deployments: NativeDeploymentRead[],
  runs: NativeRunRead[],
  humanTasks: Array<Record<string, unknown>>,
  incidents: Array<Record<string, unknown>>,
): ConsoleDashboardSummaryRead {
  const completedRuns = runs.filter((item) => item.status === "failed" || item.status === "succeeded");
  const succeededRuns = runs.filter((item) => item.status === "succeeded");
  return {
    run_count_today: runs.length,
    success_rate: completedRuns.length ? succeededRuns.length / completedRuns.length : 0,
    p95_latency_ms: 0,
    p99_latency_ms: 0,
    queue_backlog: deployments.reduce((total, item) => total + item.replicas, 0),
    worker_ready: deployments.filter((item) => item.runtime_status === "ready").length,
    worker_total: deployments.length,
    monthly_cost_usd: 0,
    pending_approvals: humanTasks.filter((item) => item.status === "pending").length,
    running_runs: runs.filter((item) => item.status === "pending").length,
    active_incidents: incidents.filter((item) => item.status !== "resolved").length,
  };
}

function runtimeOverview(
  deployments: NativeDeploymentRead[],
  runs: NativeRunRead[],
  humanTasks: Array<Record<string, unknown>>,
  incidents: Array<Record<string, unknown>>,
): ConsoleRuntimeOverviewRead {
  const failedRuns = runs.filter((item) => item.status === "failed");
  return {
    summary: dashboardSummary(deployments, runs, humanTasks, incidents),
    deployment_health: deployments.map((item) => ({
      deployment_id: item.id,
      environment: item.environment,
      desired_status: item.desired_status,
      runtime_status: item.runtime_status,
      replicas: item.replicas,
      queue_backlog: item.replicas,
      running_runs: 0,
      last_runtime_error: item.last_runtime_error,
    })),
    worker_health: deployments.map((item) => ({
      worker_id: `deployment-${item.id}`,
      deployment_id: item.id,
      environment: item.environment,
      status: item.runtime_status === "ready" ? "ready" : "degraded",
      queue_backlog: item.replicas,
      running_runs: 0,
    })),
    recent_failures: failedRuns.map((item) => ({
      run_id: item.id,
      deployment_id: item.deployment_id,
      agent_id: item.agent_id,
      agent_version_id: item.agent_version_id,
      status: item.status,
      error_summary: "provider outage",
      created_at: item.created_at,
    })),
    pending_actions: humanTasks.map((item, index) => ({
      resource_type: "deployment",
      resource_id: Number(item.id),
      action: String(item.source),
      label: "Promote deployment",
      disabled_reason: index === 0
        ? "Deployment must be active before it can restart."
        : "Second reviewer must resolve the delete request.",
      required_permissions: ["agent:deploy"],
      audit_required: true,
    })),
    trend_points: [
      { label: "06-10 09:00", runs: 1, success_rate: 1 },
      { label: "06-10 10:00", runs: 1, success_rate: 0 },
      { label: "06-10 11:00", runs: 1, success_rate: 0.5 },
    ],
  };
}

function makeRuntimeWorkers(): RuntimeWorkerFixture[] {
  return [
    {
      worker_id: "worker_1",
      environment: "local",
      status: "running",
      drain_status: "active",
      version: "2026.06.10",
      queues: ["default", "priority"],
      capacity: 2,
      active_attempts: 1,
      active_runs: 1,
      heartbeat_age_seconds: 14,
      last_error: "provider timeout",
      liveness: "alive",
      readiness: "ready",
      retrying_tasks: 0,
      dead_letter_tasks: 1,
      deployment_ids: [10],
      restart_requested_at: null,
      _blocked_actions: {
        drain: "Worker has active critical attempt and cannot drain safely.",
      },
      _active_task_ids: [5001],
      _active_run_ids: [1001],
    },
    {
      worker_id: "worker_2",
      environment: "local",
      status: "idle",
      drain_status: "active",
      version: "2026.06.10",
      queues: ["default"],
      capacity: 3,
      active_attempts: 0,
      active_runs: 0,
      heartbeat_age_seconds: 9,
      last_error: null,
      liveness: "alive",
      readiness: "ready",
      retrying_tasks: 0,
      dead_letter_tasks: 0,
      deployment_ids: [11],
      restart_requested_at: null,
      _active_task_ids: [],
      _active_run_ids: [],
    },
  ];
}

function makeRuntimeAgentInstances(): RuntimeAgentInstanceFixture[] {
  return [
    {
      id: 901,
      deployment_id: 10,
      environment: "local",
      agent_id: 1,
      agent_version_id: 11,
      worker_id: "worker_1",
      status: "failed",
      active_runs: 1,
      recent_failures: 3,
      concurrency_limit: 4,
      runtime_config_hash: "cfgf11aa22bb",
      execution_profile_id: "default",
      cache_key: "10:11:default",
      loaded_at: createdAt,
      heartbeat_at: createdAt,
      last_error: "provider timeout",
      deployment_desired_status: "active",
      deployment_runtime_status: "degraded",
    },
    {
      id: 902,
      deployment_id: 11,
      environment: "local",
      agent_id: 1,
      agent_version_id: 12,
      worker_id: "worker_2",
      status: "ready",
      active_runs: 0,
      recent_failures: 0,
      concurrency_limit: 8,
      runtime_config_hash: "cfgf22bb33cc",
      execution_profile_id: "high-memory",
      cache_key: "11:12:high-memory",
      loaded_at: createdAt,
      heartbeat_at: createdAt,
      last_error: null,
      deployment_desired_status: "active",
      deployment_runtime_status: "ready",
    },
  ];
}

function makeRuntimeWorkerCollection(workers: RuntimeWorkerFixture[]): Record<string, unknown> {
  return {
    items: workers.map(runtimeWorkerSummary),
    count: workers.length,
    request_id: "e2e-request",
  };
}

function runtimeWorkerSummary(worker: RuntimeWorkerFixture): Record<string, unknown> {
  return {
    worker_id: worker.worker_id,
    environment: worker.environment,
    status: worker.status,
    drain_status: worker.drain_status,
    version: worker.version,
    queues: worker.queues,
    capacity: worker.capacity,
    active_attempts: worker.active_attempts,
    active_runs: worker.active_runs,
    heartbeat_age_seconds: worker.heartbeat_age_seconds,
    last_error: worker.last_error,
    liveness: worker.liveness,
    readiness: worker.readiness,
    retrying_tasks: worker.retrying_tasks,
    dead_letter_tasks: worker.dead_letter_tasks,
    deployment_ids: worker.deployment_ids,
    restart_requested_at: worker.restart_requested_at,
  };
}

function runtimeWorkerActions(worker: RuntimeWorkerFixture): Array<Record<string, unknown>> {
  const blocked = worker._blocked_actions ?? {};
  const actions = [
    { action: "drain", label: "Drain worker" },
    { action: "undrain", label: "Resume scheduling" },
    { action: "quarantine", label: "Quarantine worker" },
    { action: "restart-request", label: "Request restart" },
  ];
  return actions.map((action) => {
    const disabledReasons: string[] = [];
    if (action.action === "drain" && worker.drain_status !== "active") {
      disabledReasons.push("Worker must be active before it can drain.");
    }
    if (action.action === "undrain" && worker.drain_status !== "draining") {
      disabledReasons.push("Worker must be draining before it can resume scheduling.");
    }
    if (action.action === "quarantine" && worker.active_attempts !== 0) {
      disabledReasons.push("Worker still has active attempts and cannot quarantine safely.");
    }
    if (action.action === "restart-request" && typeof worker.restart_requested_at === "string") {
      disabledReasons.push("Worker already has a pending restart request.");
    }
    if (blocked[action.action]) {
      disabledReasons.unshift(blocked[action.action]);
    }
    return {
      ...action,
      available: disabledReasons.length === 0,
      disabled_reasons: disabledReasons,
      required_permissions: ["agent:deploy"],
      audit_required: true,
    };
  });
}

function runtimeWorkerDetailResponse(
  workers: RuntimeWorkerFixture[],
  workerId: string,
): Record<string, unknown> {
  const worker = workers.find((item) => item.worker_id === workerId) ?? workers[0];
  return {
    item: {
      ...runtimeWorkerSummary(worker),
      active_task_ids: worker._active_task_ids || [],
      active_run_ids: worker._active_run_ids || [],
      actions: runtimeWorkerActions(worker),
    },
    request_id: "e2e-request",
  };
}

function fulfillRuntimeWorkerAction(
  route: Route,
  workers: RuntimeWorkerFixture[],
  workerId: string,
  action: string,
) {
  const worker = workers.find((item) => item.worker_id === workerId);
  if (!worker) return fulfillError(route);
  const selectedAction = runtimeWorkerActions(worker).find((item) => item.action === action);
  if (!selectedAction) return fulfillError(route);
  if (selectedAction.available !== true) {
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      json: {
        error_code: "worker_action_blocked",
        message: String(selectedAction.disabled_reasons?.[0] || "Blocked"),
        request_id: "e2e-error-request",
        details: {
          worker_id: workerId,
          action,
          disabled_reasons: selectedAction.disabled_reasons,
        },
      },
    });
  }
  if (action === "drain") worker.drain_status = "draining";
  if (action === "undrain") worker.drain_status = "active";
  if (action === "quarantine") worker.drain_status = "quarantined";
  if (action === "restart-request") worker.restart_requested_at = createdAt;
  return fulfillJson(route, runtimeWorkerDetailResponse(workers, workerId));
}

function makeRuntimeAgentInstanceCollection(
  instances: RuntimeAgentInstanceFixture[],
): Record<string, unknown> {
  return {
    items: instances.map((instance) => runtimeAgentInstanceSummary(instance)),
    count: instances.length,
    request_id: "e2e-request",
  };
}

function runtimeAgentInstanceSummary(
  instance: RuntimeAgentInstanceFixture,
): Record<string, unknown> {
  return {
    id: instance.id,
    deployment_id: instance.deployment_id,
    environment: instance.environment,
    agent_id: instance.agent_id,
    agent_version_id: instance.agent_version_id,
    worker_id: instance.worker_id,
    status: instance.status,
    active_runs: instance.active_runs,
    recent_failures: instance.recent_failures,
    concurrency_limit: instance.concurrency_limit,
    runtime_config_hash: instance.runtime_config_hash,
    execution_profile_id: instance.execution_profile_id,
    cache_key: instance.cache_key,
    loaded_at: instance.loaded_at,
    heartbeat_at: instance.heartbeat_at,
    last_error: instance.last_error,
  };
}

function runtimeAgentInstanceDetailResponse(
  instances: RuntimeAgentInstanceFixture[],
  instanceId: number,
): Record<string, unknown> {
  const instance = instances.find((item) => item.id === instanceId) ?? instances[0];
  return {
    item: instance,
    request_id: "e2e-request",
  };
}

function runtimeCapacitySummaryResponse(workers: RuntimeWorkerFixture[]): Record<string, unknown> {
  return {
    item: {
      queue_backlog: 3,
      active_attempts: workers.reduce(
        (total, worker) => total + Number(worker.active_attempts || 0),
        0,
      ),
      total_capacity: workers.reduce(
        (total, worker) => total + Number(worker.capacity || 0),
        0,
      ),
      saturation_ratio: 0.5,
      time_to_drain_seconds: 135,
      retry_pressure: 1,
      dead_letter_pressure: 1,
      recommended_action: "hold_drain",
      recommended_reason:
        "Critical attempts are still active. Keep drains blocked until they clear.",
      active_workers: workers.filter((worker) => worker.drain_status === "active").length,
      draining_workers: workers.filter((worker) => worker.drain_status === "draining").length,
      quarantined_workers: workers.filter((worker) => worker.drain_status === "quarantined").length,
      critical_attempts: 1,
      queues: [
        {
          queue: "default",
          queue_backlog: 2,
          leased: 0,
          running: 1,
          retrying: 1,
          dead_letter: 1,
          oldest_task_age_seconds: 48,
        },
        {
          queue: "priority",
          queue_backlog: 1,
          leased: 0,
          running: 0,
          retrying: 0,
          dead_letter: 0,
          oldest_task_age_seconds: 12,
        },
      ],
    },
    request_id: "e2e-request",
  };
}

function fulfillPlatformScopedSettings(
  route: Route,
  scopedSettings: Array<Record<string, unknown>>,
  snapshot: Record<string, unknown>,
  scopeKind: string,
) {
  const body = parseRequestBody(route);
  const config = body.config && typeof body.config === "object" ? body.config as Record<string, unknown> : {};
  const target = scopedSettings.find((item) => item.scope_kind === scopeKind);
  if (!target) return fulfillError(route);
  target.config = { ...(target.config as Record<string, unknown>), ...config };
  target.updated_at = createdAt;
  snapshot.scope_defaults = scopedSettings;
  if (scopeKind === "environment") {
    snapshot.danger_state = {
      ...(snapshot.danger_state as Record<string, unknown>),
      freeze_writes: Boolean((target.config as Record<string, unknown>).freeze_writes),
      updated_at: createdAt,
    };
  }
  return fulfillJson(route, { item: target, request_id: "e2e-request" });
}

function fulfillPlatformDangerPreflight(
  route: Route,
  providerStatuses: Array<Record<string, unknown>>,
  scopedSettings: Array<Record<string, unknown>>,
) {
  const body = parseRequestBody(route);
  const action = String(body.action || "");
  if (action === "rotate_object_store_credentials") {
    return fulfillJson(route, {
      item: {
        action,
        scope_kind: "organization",
        risk_level: "critical",
        available: false,
        blocked_reasons: ["object_store is not healthy enough for this action."],
        confirmation_phrase: "rotate object store credentials",
        affected_resources: [
          { label: "Deployments", count: 2 },
          { label: "Published surfaces", count: 1 },
          { label: "Workers", count: 2 },
        ],
        rollback_notes: "Restore the previous object-store secret ref before retrying uploads.",
        audit_required: true,
      },
      request_id: "e2e-request",
    });
  }
  const environmentDefaults = scopedSettings.find((item) => item.scope_kind === "environment");
  return fulfillJson(route, {
    item: {
      action,
      scope_kind: "environment",
      risk_level: "critical",
      available: true,
      blocked_reasons: [],
      confirmation_phrase: "freeze local writes",
      affected_resources: [
        { label: "Deployments", count: 2 },
        { label: "Published surfaces", count: 1 },
        { label: "Workers", count: 2 },
      ],
      rollback_notes: "Disable the freeze after maintenance and redeploy blocked changes.",
      audit_required: true,
      current_freeze_state: environmentDefaults?.config,
      providers: providerStatuses,
    },
    request_id: "e2e-request",
  });
}

function fulfillPlatformDangerAction(
  route: Route,
  action: string,
  scopedSettings: Array<Record<string, unknown>>,
  snapshot: Record<string, unknown>,
) {
  const body = parseRequestBody(route);
  if (action === "rotate_object_store_credentials") {
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      json: {
        error_code: "dangerous_action_preflight_failed",
        message: "object_store is not healthy enough for this action.",
        request_id: "e2e-error-request",
        details: { action },
      },
    });
  }
  if (String(body.confirmation || "") !== "freeze local writes") {
    return route.fulfill({
      status: 400,
      contentType: "application/json",
      json: {
        error_code: "dangerous_action_confirmation_required",
        message: "Confirmation phrase does not match.",
        request_id: "e2e-error-request",
        details: { action },
      },
    });
  }
  const environmentDefaults = scopedSettings.find((item) => item.scope_kind === "environment");
  if (!environmentDefaults) return fulfillError(route);
  environmentDefaults.config = {
    ...(environmentDefaults.config as Record<string, unknown>),
    freeze_writes: true,
  };
  environmentDefaults.updated_at = createdAt;
  snapshot.danger_state = { freeze_writes: true, updated_at: createdAt };
  snapshot.scope_defaults = scopedSettings;
  return fulfillJson(route, {
    item: {
      action,
      status: "applied",
      scope_setting: environmentDefaults,
      rollback_notes: String(body.rollback_notes || ""),
      request_id: "e2e-request",
    },
    request_id: "e2e-request",
  });
}

function fulfillObservabilityExporterValidation(
  route: Route,
  exporters: Array<Record<string, unknown>>,
  exporterId: number,
) {
  const exporter = exporters.find((entry) => Number(entry.id) === exporterId) ?? exporters[0];
  return fulfillJson(route, {
    item: {
      exporter_id: exporter?.id,
      name: exporter?.name,
      validation_status: "reachable",
      last_proof_at: "2026-06-15T00:00:00Z",
      target_ref_redacted: exporter?.target_ref_redacted,
      blocked_reason: null,
      request_id: "e2e-request",
    },
    request_id: "e2e-request",
  });
}

function fulfillSemanticStoreValidation(
  route: Route,
  providers: Array<Record<string, unknown>>,
  providerId: number,
) {
  const provider = providers.find((entry) => Number(entry.id) === providerId) ?? providers[0];
  return fulfillJson(route, {
    item: {
      provider_id: provider?.id,
      name: provider?.name,
      provider_status: "degraded",
      embedding_model: provider?.embedding_model,
      index_coverage: provider?.metadata?.index_coverage ?? { runs: 0, artifacts: 0 },
      last_validation_proof: "2026-06-15T00:00:00Z",
      request_id: "e2e-request",
    },
    request_id: "e2e-request",
  });
}

function fulfillSandboxPolicyPreview(
  route: Route,
  policies: Array<Record<string, unknown>>,
  policyId: number,
) {
  const policy = policies.find((entry) => Number(entry.id) === policyId) ?? policies[0];
  const body = parseRequestBody(route);
  const capabilities = Array.isArray(body.capabilities) ? body.capabilities : [];
  return fulfillJson(route, {
    item: {
      policy_id: policy?.id,
      name: policy?.name,
      blocked_capabilities: capabilities.filter((capability) => capability === "network" || capability === "filesystem"),
      audit_required: true,
      affected_runtime_surfaces: policy?.metadata?.affected_surfaces ?? [],
      request_id: "e2e-request",
    },
    request_id: "e2e-request",
  });
}

function fulfillContainerPoolEstimate(
  route: Route,
  policies: Array<Record<string, unknown>>,
  policyId: number,
) {
  const policy = policies.find((entry) => Number(entry.id) === policyId) ?? policies[0];
  const body = parseRequestBody(route);
  const requestedWorkers = Number(body.requested_workers ?? 0);
  const scaleLimit = Number(policy?.max_containers ?? 0);
  return fulfillJson(route, {
    item: {
      policy_id: policy?.id,
      name: policy?.name,
      warm_capacity: policy?.metadata?.warm_capacity ?? 0,
      scale_limit: scaleLimit,
      estimated_saturation: scaleLimit > 0 ? Math.min(1, requestedWorkers / scaleLimit) : 1,
      affected_worker_pools: policy?.metadata?.worker_pools ?? [],
      request_id: "e2e-request",
    },
    request_id: "e2e-request",
  });
}

function fulfillJson(route: Route, json: unknown) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    json,
  });
}

function fulfillError(route: Route, error?: unknown) {
  return route.fulfill({
    status: 503,
    contentType: "application/json",
    json: {
      detail: {
        error_code: "e2e_api_error",
        message: error instanceof Error ? error.message : "Mocked API failure.",
        request_id: "e2e-error-request",
        details: { source: "playwright" },
      },
    },
  });
}
