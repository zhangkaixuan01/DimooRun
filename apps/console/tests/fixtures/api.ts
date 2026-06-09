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

type MockOptions = {
  empty?: boolean;
  errorPath?: string;
  delayPath?: string;
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
        capabilities: { streaming: true },
        manifest: { name: "support-agent" },
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
        capabilities: { streaming: true },
        manifest: { name: "support-agent" },
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

export async function seedConsoleSession(page: Page): Promise<void> {
  await page.addInitScript((sessionOperator) => {
    localStorage.setItem("dimoorun.console.token", "sess_e2e_session");
    localStorage.setItem("dimoorun.console.operator", JSON.stringify(sessionOperator));
    localStorage.setItem("dimoorun.console.scope", JSON.stringify(sessionOperator.allowed_scopes[0]));
  }, e2eOperator);
}

export async function installConsoleApiMocks(
  page: Page,
  options: MockOptions = {},
): Promise<void> {
  const api = makeDashboardApi({ empty: options.empty });
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
    if (path === "/v1/published-surfaces" && route.request().method() === "GET") {
      return fulfillJson(route, makeAdminCollection(publishedSurfaces));
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
      return fulfillJson(route, promotionPreviewResponse(api, Number(promotionPreviewMatch[1]), Number(url.searchParams.get("candidate_version_id"))));
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

function recordValue(record: unknown, key: string): unknown {
  return record && typeof record === "object" && !Array.isArray(record)
    ? (record as Record<string, unknown>)[key]
    : undefined;
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
  if (path.match(/^\/v1\/agents\/\d+\/versions$/)) return api.versions;
  if (path === "/v1/identity/tenants") return makeAdminCollection([{ id: 1, name: "Local Tenant" }]);
  if (path === "/v1/identity/projects") return makeAdminCollection([{ id: 1, name: "DimooRun" }]);
  return makeAdminCollection([]);
}

function promotionPreviewResponse(api: DashboardApiFixture, deploymentId: number, candidateVersionId: number): unknown {
  const deployment = api.deployments.find((item) => item.id === deploymentId);
  if (!deployment) return makeAdminCollection([]);
  const activeRuns = api.runs.filter((item) => item.deployment_id === deploymentId).length;
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
    can_promote: true,
    blocked_reason: null,
    warnings: ["active_runs_will_continue_on_current_version", "queued_tasks_will_use_current_version"],
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
  const deployment = api.deployments.find((item) => item.id === deploymentId);
  if (!deployment) return fulfillError(route);
  const previousVersionId = deployment.agent_version_id;
  deployment.agent_version_id = Number(body.candidate_version_id);
  deployment.config = {
    ...deployment.config,
    promotion: {
      previous_agent_version_id: previousVersionId,
      current_agent_version_id: deployment.agent_version_id,
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
  };
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
