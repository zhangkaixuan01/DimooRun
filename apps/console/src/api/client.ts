import type { Agent, AgentVersion, Deployment, HumanTask, ResourceId, Run, RunAttempt, RuntimeEvent, Task, TaskCreateResult } from "./types";
import {
  createDimooRunClient,
  DimooRunApiError,
  type ConsoleLoginResponse,
  type ConsoleOperatorRead,
  type NativeAgentRead,
  type NativeAgentVersionRead,
  type NativeDeploymentCreatePayload,
  type NativeDeploymentRead,
  type NativeDeploymentTaskCreatePayload,
  type NativeDeploymentUpdatePayload,
  type NativeEventRead,
  type NativeRunRead,
  type NativeTaskCreatePayload,
  type NativeTaskRead,
} from "./generated/dimoorun";
import { readCurrentScope, SCOPE_KEY, type ConsoleScope } from "./scope";

export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};

export type ApiMode = "live" | "offline";

export type ConsoleApiError = {
  errorCode: string;
  message: string;
  requestId: string | null;
  details: Record<string, unknown> | null;
};

export type DashboardSummary = {
  runCountToday: number;
  successRate: number;
  p95LatencyMs: number;
  p99LatencyMs: number;
  queueBacklog: number;
  workerReady: number;
  workerTotal: number;
  monthlyCostUsd: number;
  pendingApprovals: number;
  runningRuns: number;
  activeIncidents: number;
};

export type AdminResource = Record<string, unknown> & {
  id: ResourceId;
  status?: string;
  name?: string;
  created_at?: string;
  updated_at?: string;
};

export type ConsoleOperator = ConsoleOperatorRead;
export type ConsoleLogin = ConsoleLoginResponse;
export type ConsoleOperatorSession = AdminResource & {
  operator_id: ResourceId;
  status: string;
  last_used_at: string;
  expires_at: string;
  revoked_at: string | null;
  revoke_reason: string | null;
  ip_address: string | null;
  user_agent: string | null;
};
export type MachineApiKeyCreate = {
  item: AdminResource;
  plain_key: string;
  request_id: string | null;
};

const TOKEN_KEY = "dimoorun.console.token";
const OPERATOR_KEY = "dimoorun.console.operator";

function page<T>(items: T[]): CursorPage<T> {
  return { items, nextCursor: null };
}

export function apiBaseUrl(): string | null {
  return import.meta.env.VITE_DIMOORUN_API_BASE_URL || null;
}

export function apiMode(): ApiMode {
  return apiBaseUrl() ? "live" : "offline";
}

export function isApiConfigured(): boolean {
  return apiMode() === "live";
}

export function toConsoleApiError(error: unknown): ConsoleApiError {
  if (error instanceof DimooRunApiError) {
    return {
      errorCode: error.errorCode || `http_${error.status}`,
      message: error.message,
      requestId: error.requestId,
      details: error.details,
    };
  }
  if (error instanceof Error) {
    return {
      errorCode: "console_client_error",
      message: error.message,
      requestId: null,
      details: null,
    };
  }
  return {
    errorCode: "unknown_error",
    message: "Unknown console API error.",
    requestId: null,
    details: null,
  };
}

function nativeHeaders(idempotencyKey?: string, scopeOverride?: Partial<ConsoleScope>): HeadersInit {
  const scope = { ...readCurrentScope(), ...scopeOverride };
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-Id": crypto.randomUUID(),
    "X-Tenant-Id": String(scope.tenant_id),
    "X-Project-Id": String(scope.project_id),
    "X-Environment": scope.environment,
  };
  const sessionToken = localStorage.getItem(TOKEN_KEY);
  if (sessionToken?.startsWith("sess_")) headers.Authorization = `Bearer ${sessionToken}`;
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  return headers;
}

function nativeClient(idempotencyKey?: string, scopeOverride?: Partial<ConsoleScope>) {
  const baseUrl = apiBaseUrl();
  if (!baseUrl) {
    throw new Error("DimooRun API base URL is not configured.");
  }
  return withUnauthorizedHandling(createDimooRunClient({
    baseUrl,
    headers: nativeHeaders(idempotencyKey, scopeOverride),
  }));
}

function withUnauthorizedHandling<T extends Record<string, unknown>>(client: T): T {
  return new Proxy(client, {
    get(target, property, receiver) {
      const value = Reflect.get(target, property, receiver);
      if (typeof value !== "function") return value;
      return (...args: unknown[]) => {
        const result = value.apply(target, args);
        if (!result || typeof result.then !== "function") return result;
        return result.catch((error: unknown) => {
          handleUnauthorized(error);
          throw error;
        });
      };
    },
  });
}

function handleUnauthorized(error: unknown): void {
  if (!(error instanceof DimooRunApiError) || error.status !== 401) return;
  if (!localStorage.getItem(TOKEN_KEY)) return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(OPERATOR_KEY);
  localStorage.removeItem(SCOPE_KEY);
  window.dispatchEvent(new CustomEvent("dimoorun:auth-invalidated", { detail: error.errorCode }));
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (!window.location.pathname.startsWith("/login")) {
    window.location.assign(`/login?redirect=${encodeURIComponent(current)}`);
  }
}

function mapNativeAgent(
  agent: NativeAgentRead,
  counts: { versionCount?: number; deploymentCount?: number } = {},
): Agent {
  return {
    id: agent.id,
    name: agent.name,
    description: agent.description,
    status: agent.status,
    createdAt: agent.created_at,
    versionCount: counts.versionCount ?? 0,
    deploymentCount: counts.deploymentCount ?? 0,
  };
}

function mapNativeAgentVersion(version: NativeAgentVersionRead): AgentVersion {
  return {
    id: version.id,
    agentId: version.agent_id,
    version: version.version,
    packageUri: version.package_uri,
    framework: version.framework,
    adapter: version.adapter,
    entrypoint: version.entrypoint,
    capabilities: version.capabilities,
    manifest: version.manifest,
    status: version.status,
  };
}

function mapNativeDeployment(deployment: NativeDeploymentRead): Deployment {
  const runtimeStatus =
    deployment.runtime_status === "failed" || deployment.runtime_status === "stopped"
      ? "degraded"
      : deployment.runtime_status === "not_loaded"
        ? "warming_up"
        : (deployment.runtime_status as Deployment["runtimeStatus"]);
  const desiredStatus =
    deployment.desired_status === "draft"
      ? "paused"
      : deployment.desired_status === "archived"
        ? "stopped"
        : (deployment.desired_status as Deployment["desiredStatus"]);
  return {
    id: deployment.id,
    agent: String(deployment.agent_id),
    environment: deployment.environment,
    version: String(deployment.agent_version_id),
    desiredStatus,
    runtimeStatus,
    instances: deployment.replicas,
    config: deployment.config ?? {},
    runningRuns: 0,
    queueBacklog: 0,
    worker: "native-worker",
    heartbeatAt: new Date().toISOString(),
    executionProfile: "default",
    modelGateway: "default",
  };
}

function mapNativeRun(run: NativeRunRead): Run {
  const status = run.status === "pending" ? "running" : run.status;
  return {
    id: run.id,
    agent: String(run.agent_id),
    framework: "LangGraph",
    adapter: "native",
    version: String(run.agent_version_id),
    actor: "api",
    status: ["succeeded", "failed", "running", "timeout", "cancelled"].includes(status)
      ? (status as Run["status"])
      : "running",
    createdAt: run.created_at,
    startedAt: run.started_at,
    finishedAt: run.finished_at,
    latencyMs: run.latency_ms,
    trigger: "api",
    deployment: run.deployment_id ? String(run.deployment_id) : "direct",
    traceId: run.thread_id || String(run.id),
    input: run.input,
    output: run.output,
    error: run.error,
  };
}

function mapNativeEvent(event: NativeEventRead): RuntimeEvent {
  return {
    runId: event.run_id,
    sequence: event.sequence,
    eventId: event.event_id,
    type: event.type,
    status: event.visibility_level,
    summary: `run ${event.run_id}: ${JSON.stringify(event.payload)}`,
    payload: event.payload,
  };
}

function mapNativeRunAttempt(attempt: Record<string, unknown>): RunAttempt {
  return {
    id: Number(attempt.id),
    runId: Number(attempt.run_id),
    taskId: attempt.task_id === null || attempt.task_id === undefined ? null : Number(attempt.task_id),
    attemptNo: Number(attempt.attempt_no),
    workerId: attempt.worker_id === null || attempt.worker_id === undefined ? null : String(attempt.worker_id),
    status: String(attempt.status || "unknown"),
    error: attempt.error === null || attempt.error === undefined ? null : String(attempt.error),
  };
}

function mapNativeTask(task: NativeTaskRead): Task {
  return {
    id: task.id,
    runId: task.run_id,
    status: ["queued", "leased", "running", "retrying", "dead_letter", "succeeded", "cancelled"].includes(task.status)
      ? (task.status as Task["status"])
      : "queued",
    attempt: task.attempt,
    queue: task.queue,
    workerId: "native-worker",
    heartbeatAt: "",
    leaseUntil: "",
    fencingToken: 0,
    retryCount: Math.max(0, task.attempt - 1),
    deadLetterReason: task.dead_letter_reason || undefined,
    partitionKey: task.partition_key || undefined,
    resourceClass: task.resource_class || undefined,
    quotaBlockingReason: task.quota_blocking_reason as Task["quotaBlockingReason"],
  };
}

function mapAdminHumanTask(item: AdminResource): HumanTask {
  const status = typeof item.status === "string" ? item.status : "pending";
  const risk = typeof item.risk === "string" ? item.risk : "medium";
  return {
    id: item.id,
    source: String(item.source || item.name || "admin"),
    risk: ["medium", "high", "critical"].includes(risk) ? (risk as HumanTask["risk"]) : "medium",
    status: ["pending", "approved", "rejected"].includes(status)
      ? (status as HumanTask["status"])
      : "pending",
    assignee: String(item.assignee || "unassigned"),
    expiresAt: String(item.expires_at || item.expiresAt || ""),
  };
}

export const liveConsoleClient = {
  async login(email: string, password: string): Promise<ConsoleLogin> {
    return nativeClient().login(email, password);
  },
  async me(): Promise<ConsoleOperator> {
    return (await nativeClient().me()).operator;
  },
  async logout() {
    return nativeClient().logout();
  },
  async changePassword(currentPassword: string, newPassword: string) {
    return nativeClient(crypto.randomUUID()).changePassword(currentPassword, newPassword);
  },
  async getDashboardSummary(): Promise<DashboardSummary> {
    const [deploymentsPage, humanTasksPage, runsPage, incidentsPage] = await Promise.all([
      this.listDeployments(),
      this.listHumanTasks(),
      this.listRuns(),
      this.listAdminCollection("/v1/incidents"),
    ]);
    const completedRuns = runsPage.items.filter((run) => run.status === "succeeded" || run.status === "failed");
    const succeededRuns = runsPage.items.filter((run) => run.status === "succeeded");
    return {
      runCountToday: runsPage.items.length,
      successRate: completedRuns.length ? succeededRuns.length / completedRuns.length : 0,
      p95LatencyMs: 0,
      p99LatencyMs: 0,
      queueBacklog: deploymentsPage.items.reduce((total, item) => total + item.queueBacklog, 0),
      workerReady: deploymentsPage.items.filter((item) => item.runtimeStatus === "ready").length,
      workerTotal: deploymentsPage.items.length,
      monthlyCostUsd: 0,
      pendingApprovals: humanTasksPage.items.filter((task) => task.status === "pending").length,
      runningRuns: runsPage.items.filter((run) => run.status === "running").length,
      activeIncidents: incidentsPage.items.filter((item) => item.status !== "resolved").length,
    };
  },
  async listAgents(): Promise<CursorPage<Agent>> {
    const client = nativeClient();
    const [agents, deployments] = await Promise.all([
      client.listAgents(),
      client.listDeployments(),
    ]);
    const versionsByAgent = await Promise.all(
      agents.map(async (agent) => [agent.id, await client.listAgentVersions(agent.id)] as const),
    );
    const versionCounts = new Map(
      versionsByAgent.map(([agentId, versions]) => [agentId, versions.length]),
    );
    const deploymentCounts = deployments.reduce((counts, deployment) => {
      counts.set(deployment.agent_id, (counts.get(deployment.agent_id) ?? 0) + 1);
      return counts;
    }, new Map<ResourceId, number>());
    return page(
      agents.map((agent) =>
        mapNativeAgent(agent, {
          versionCount: versionCounts.get(agent.id) ?? 0,
          deploymentCount: deploymentCounts.get(agent.id) ?? 0,
        }),
      ),
    );
  },
  async createAgent(payload: Record<string, unknown>): Promise<Agent> {
    const created = await nativeClient(crypto.randomUUID()).createAgent(payload);
    return mapNativeAgent(created);
  },
  async updateAgent(agentId: ResourceId, payload: Record<string, unknown>): Promise<Agent> {
    const updated = await nativeClient(crypto.randomUUID()).updateAgent(agentId, payload);
    return mapNativeAgent(updated);
  },
  async archiveAgent(agentId: ResourceId): Promise<Agent> {
    const archived = await nativeClient(crypto.randomUUID()).archiveAgent(agentId);
    return mapNativeAgent(archived);
  },
  async listAgentVersions(agentId: ResourceId): Promise<CursorPage<AgentVersion>> {
    const payload = await nativeClient().listAgentVersions(agentId);
    return page(payload.map(mapNativeAgentVersion));
  },
  async createAgentVersion(agentId: ResourceId, payload: Record<string, unknown>): Promise<AgentVersion> {
    const created = await nativeClient(crypto.randomUUID()).createAgentVersion(agentId, payload);
    return mapNativeAgentVersion(created);
  },
  async updateAgentVersion(agentId: ResourceId, version: string, payload: Record<string, unknown>): Promise<AgentVersion> {
    const updated = await nativeClient(crypto.randomUUID()).updateAgentVersion(agentId, version, payload);
    return mapNativeAgentVersion(updated);
  },
  async archiveAgentVersion(agentId: ResourceId, version: string): Promise<AgentVersion> {
    const archived = await nativeClient(crypto.randomUUID()).archiveAgentVersion(agentId, version);
    return mapNativeAgentVersion(archived);
  },
  async listDeployments(): Promise<CursorPage<Deployment>> {
    const payload = await nativeClient().listDeployments();
    return page(payload.map(mapNativeDeployment));
  },
  async createDeployment(payload: NativeDeploymentCreatePayload): Promise<Deployment> {
    const created = await nativeClient(crypto.randomUUID()).createDeployment(payload);
    return mapNativeDeployment(created);
  },
  async updateDeployment(deploymentId: ResourceId, payload: NativeDeploymentUpdatePayload): Promise<Deployment> {
    const updated = await nativeClient(crypto.randomUUID()).updateDeployment(deploymentId, payload);
    return mapNativeDeployment(updated);
  },
  async archiveDeployment(deploymentId: ResourceId): Promise<Deployment> {
    const archived = await nativeClient(crypto.randomUUID()).archiveDeployment(deploymentId);
    return mapNativeDeployment(archived);
  },
  async controlDeployment(deploymentId: ResourceId, operation: string): Promise<Deployment> {
    const payload = await nativeClient(crypto.randomUUID()).controlDeployment(deploymentId, operation);
    return mapNativeDeployment(payload);
  },
  async createDeploymentTask(deploymentId: ResourceId, payload: NativeDeploymentTaskCreatePayload): Promise<TaskCreateResult> {
    const response = await nativeClient(crypto.randomUUID()).createDeploymentTask(
      deploymentId,
      payload,
      crypto.randomUUID(),
    );
    return {
      runId: response.run_id,
      taskId: response.task_id,
      status: response.status,
      replayed: response.replayed,
    };
  },
  async listRuns(): Promise<CursorPage<Run>> {
    const payload = await nativeClient().listRuns();
    return page(payload.map(mapNativeRun));
  },
  async getRun(runId: ResourceId): Promise<Run | null> {
    const payload = await nativeClient().getRun(runId);
    return mapNativeRun(payload);
  },
  async controlRun(runId: ResourceId, operation: string): Promise<Run> {
    const payload = await nativeClient(crypto.randomUUID()).controlRun(runId, operation);
    return mapNativeRun(payload);
  },
  async replayRun(runId: ResourceId, agentVersionId?: ResourceId | null): Promise<Run> {
    const payload = await nativeClient(crypto.randomUUID()).replayRun(runId, {
      agent_version_id: agentVersionId ?? undefined,
    });
    return mapNativeRun(payload);
  },
  async createTask(agentId: ResourceId, payload: NativeTaskCreatePayload): Promise<TaskCreateResult> {
    const response = await nativeClient(crypto.randomUUID()).createTask(
      agentId,
      payload,
      crypto.randomUUID(),
    );
    return {
      runId: response.run_id,
      taskId: response.task_id,
      status: response.status,
      replayed: response.replayed,
    };
  },
  async listRunEvents(runId: ResourceId): Promise<CursorPage<RuntimeEvent>> {
    const payload = await nativeClient().listRunEvents(runId);
    return page(payload.map(mapNativeEvent));
  },
  async listRunAttempts(runId: ResourceId): Promise<CursorPage<RunAttempt>> {
    const payload = await nativeClient().listRunAttempts(runId);
    return page(payload.map(mapNativeRunAttempt));
  },
  async listTasks(): Promise<CursorPage<Task>> {
    const payload = await nativeClient().listTasks();
    return page(payload.map(mapNativeTask));
  },
  async cancelTask(taskId: ResourceId): Promise<Task> {
    const payload = await nativeClient(crypto.randomUUID()).cancelTask(taskId);
    return mapNativeTask(payload as NativeTaskRead);
  },
  async listEvents(): Promise<CursorPage<RuntimeEvent>> {
    const payload = await nativeClient().listEvents();
    return page(payload.map(mapNativeEvent));
  },
  async listHumanTasks(): Promise<CursorPage<HumanTask>> {
    const payload = await nativeClient().listAdminCollection<AdminResource>("/v1/human-tasks");
    return page(payload.items.map(mapAdminHumanTask));
  },
  async decideHumanTask(taskId: ResourceId, decision: "approve" | "reject"): Promise<HumanTask> {
    const payload = await nativeClient(crypto.randomUUID()).postAdminAction<AdminResource>(
      `/v1/human-tasks/${taskId}/${decision}`,
      { decision_payload: { source: "console" } },
    );
    return mapAdminHumanTask(payload.item);
  },
  async listAdminCollection(path: string, scopeOverride?: Partial<ConsoleScope>): Promise<CursorPage<AdminResource>> {
    const payload = await nativeClient(undefined, scopeOverride).listAdminCollection<AdminResource>(path);
    return page(payload.items);
  },
  async createAdminItem(path: string, payload: Record<string, unknown>): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).createAdminItem<AdminResource>(path, payload);
    return response.item;
  },
  async updateAdminItem(path: string, resourceId: ResourceId, payload: Record<string, unknown>): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).updateAdminItem<AdminResource>(path, resourceId, payload);
    return response.item;
  },
  async deleteAdminItem(path: string, resourceId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).deleteAdminItem<AdminResource>(path, resourceId);
    return response.item;
  },
  async revokeOperatorSessions(operatorId: ResourceId): Promise<void> {
    await nativeClient(crypto.randomUUID()).postAdminAction(`/v1/identity/operators/${operatorId}/revoke-sessions`);
  },
  async listOperatorSessions(operatorId: ResourceId): Promise<CursorPage<ConsoleOperatorSession>> {
    const payload = await nativeClient().listAdminCollection<ConsoleOperatorSession>(`/v1/identity/operators/${operatorId}/sessions`);
    return page(payload.items);
  },
  async resetOperatorPassword(operatorId: ResourceId, newPassword: string): Promise<void> {
    await nativeClient(crypto.randomUUID()).postAdminAction(`/v1/identity/operators/${operatorId}/reset-password`, {
      new_password: newPassword,
    });
  },
  async deleteOperator(operatorId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).deleteAdminItem<AdminResource>("/v1/identity/operators", operatorId);
    return response.item;
  },
  async listServiceAccounts(): Promise<CursorPage<AdminResource>> {
    return this.listAdminCollection("/v1/identity/service-accounts");
  },
  async createServiceAccount(payload: Record<string, unknown>): Promise<AdminResource> {
    return this.createAdminItem("/v1/identity/service-accounts", payload);
  },
  async updateServiceAccount(serviceAccountId: ResourceId, payload: Record<string, unknown>): Promise<AdminResource> {
    return this.updateAdminItem("/v1/identity/service-accounts", serviceAccountId, payload);
  },
  async deleteServiceAccount(serviceAccountId: ResourceId): Promise<AdminResource> {
    return this.deleteAdminItem("/v1/identity/service-accounts", serviceAccountId);
  },
  async listServiceAccountApiKeys(serviceAccountId: ResourceId): Promise<CursorPage<AdminResource>> {
    return this.listAdminCollection(`/v1/identity/service-accounts/${serviceAccountId}/api-keys`);
  },
  async createServiceAccountApiKey(serviceAccountId: ResourceId, payload: Record<string, unknown>): Promise<MachineApiKeyCreate> {
    return nativeClient(crypto.randomUUID()).createAdminItem<MachineApiKeyCreate["item"]>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys`,
      payload,
    ) as Promise<MachineApiKeyCreate>;
  },
  async disableServiceAccountApiKey(serviceAccountId: ResourceId, keyId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<AdminResource>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys/${keyId}/disable`,
    );
    return response.item;
  },
  async enableServiceAccountApiKey(serviceAccountId: ResourceId, keyId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<AdminResource>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys/${keyId}/enable`,
    );
    return response.item;
  },
  async deleteServiceAccountApiKey(serviceAccountId: ResourceId, keyId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).deleteAdminItem<AdminResource>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys`,
      keyId,
    );
    return response.item;
  },
};

export const consoleClient = liveConsoleClient;
