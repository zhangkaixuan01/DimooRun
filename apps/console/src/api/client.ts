import { agents, deployments, events, humanTasks, runs, tasks } from "./mockData";
import type { Agent, Deployment, HumanTask, Run, RuntimeEvent, Task } from "./types";
import {
  createDimooRunClient,
  DimooRunApiError,
  type NativeAgentRead,
  type NativeDeploymentRead,
  type NativeEventRead,
  type NativeRunRead,
  type NativeTaskRead,
  type ConsoleLoginResponse,
  type ConsoleOperatorRead,
} from "./generated/dimoorun";
import { readCurrentScope, SCOPE_KEY, type ConsoleScope } from "./scope";

export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};

export type ApiMode = "live" | "demo" | "offline";

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
  id: string;
  status?: string;
  name?: string;
  created_at?: string;
  updated_at?: string;
};

export type ConsoleOperator = ConsoleOperatorRead;
export type ConsoleLogin = ConsoleLoginResponse;
export type ConsoleOperatorSession = AdminResource & {
  operator_id: string;
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

export function isDemoMode(): boolean {
  return import.meta.env.VITE_DIMOORUN_DEMO_MODE === "true";
}

export function apiMode(): ApiMode {
  if (isDemoMode()) return "demo";
  return apiBaseUrl() ? "live" : "offline";
}

export function isApiConfigured(): boolean {
  return apiMode() !== "offline";
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
    "X-Tenant-Id": scope.tenant_id,
    "X-Project-Id": scope.project_id,
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

function mapNativeAgent(agent: NativeAgentRead): Agent {
  return {
    id: agent.id,
    name: agent.name,
    framework: "LangGraph",
    adapter: "native",
    version: "latest",
    capabilities: [],
    deployments: 0,
    lastRunStatus: agent.status,
    releasedAt: new Date().toISOString(),
  };
}

function mapNativeRun(run: NativeRunRead): Run {
  const status = run.status === "pending" ? "running" : run.status;
  return {
    id: run.id,
    agent: run.agent_id,
    framework: "LangGraph",
    adapter: "native",
    version: run.agent_version_id,
    actor: "api",
    status: ["succeeded", "failed", "running", "timeout", "cancelled"].includes(status)
      ? (status as Run["status"])
      : "running",
    latencyMs: 0,
    costUsd: 0,
    startedAt: new Date().toISOString(),
    trigger: "api",
    deployment: run.deployment_id || "direct",
    traceId: run.thread_id || run.id,
  };
}

function mapNativeEvent(event: NativeEventRead): RuntimeEvent {
  return {
    sequence: event.sequence,
    eventId: event.event_id,
    type: event.type,
    status: event.visibility_level,
    timestamp: new Date().toISOString(),
    summary: JSON.stringify(event.payload),
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
    agent: deployment.agent_id,
    environment: deployment.environment,
    version: deployment.agent_version_id,
    desiredStatus,
    runtimeStatus,
    instances: deployment.replicas,
    runningRuns: 0,
    queueBacklog: 0,
    worker: "native-worker",
    heartbeatAt: new Date().toISOString(),
    executionProfile: "default",
    modelGateway: "default",
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

export const demoConsoleClient = {
  async login(email: string, password: string): Promise<ConsoleLogin> {
    if (!email || !password) throw new Error("Invalid credentials.");
    return {
      access_token: "demo-session-token",
      token_type: "bearer",
      expires_at: new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString(),
      request_id: null,
      operator: {
        id: "operator_demo",
        email,
        name: "Demo Operator",
        roles: ["platform_admin"],
        permissions: ["*"],
        status: "active",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        last_login_at: new Date().toISOString(),
        password_changed_at: new Date().toISOString(),
        allowed_scopes: [
          {
            tenant_id: "tenant_1",
            project_id: "project_1",
            environment: "local",
          },
        ],
      },
    };
  },
  async me(): Promise<ConsoleOperator> {
    return {
      id: "operator_demo",
      email: "demo@local.dimoorun",
      name: "Demo Operator",
      roles: ["platform_admin"],
      permissions: ["*"],
      status: "active",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_login_at: new Date().toISOString(),
      password_changed_at: new Date().toISOString(),
      allowed_scopes: [
        {
          tenant_id: "tenant_1",
          project_id: "project_1",
          environment: "local",
        },
      ],
    };
  },
  async logout() {
    return { ok: true };
  },
  async changePassword() {
    return { ok: true, request_id: null };
  },
  async getDashboardSummary() {
    return {
      runCountToday: 12840,
      successRate: 0.987,
      p95LatencyMs: 2100,
      p99LatencyMs: 4300,
      queueBacklog: 24,
      workerReady: 6,
      workerTotal: 7,
      monthlyCostUsd: 4291,
      pendingApprovals: humanTasks.filter((task) => task.status === "pending").length,
      runningRuns: runs.filter((run) => run.status === "running").length,
      activeIncidents: 2,
    };
  },
  async listAgents() {
    return page(agents);
  },
  async createAgent(payload: Record<string, unknown>) {
    const agent: Agent = {
      id: `agent_demo_${Date.now()}`,
      name: String(payload.name || "demo-agent"),
      framework: "LangGraph",
      adapter: "native",
      version: "latest",
      capabilities: [],
      deployments: 0,
      lastRunStatus: "active",
      releasedAt: new Date().toISOString(),
    };
    agents.unshift(agent);
    return agent;
  },
  async archiveAgent(agentId: string) {
    const agent = agents.find((item) => item.id === agentId);
    if (!agent) throw new Error("Agent not found.");
    agent.lastRunStatus = "archived";
    return agent;
  },
  async listDeployments() {
    return page(deployments);
  },
  async controlDeployment(deploymentId: string, operation: string) {
    const deployment = deployments.find((item) => item.id === deploymentId);
    if (!deployment) throw new Error("Deployment not found.");
    deployment.desiredStatus = operation === "resume" || operation === "activate" ? "active" : operation as Deployment["desiredStatus"];
    return deployment;
  },
  async listRuns() {
    return page(runs);
  },
  async getRun(runId: string) {
    return runs.find((run) => run.id === runId) ?? null;
  },
  async controlRun(runId: string, operation: string) {
    const run = runs.find((item) => item.id === runId);
    if (!run) throw new Error("Run not found.");
    if (operation === "cancel") run.status = "cancelled";
    return run;
  },
  async listRunEvents() {
    return page(events);
  },
  async listTasks() {
    return page(tasks);
  },
  async cancelTask(taskId: string) {
    const task = tasks.find((item) => item.id === taskId);
    if (!task) throw new Error("Task not found.");
    task.status = "cancelled";
    return task;
  },
  async listEvents() {
    return page(events);
  },
  async listHumanTasks() {
    return page(humanTasks);
  },
  async decideHumanTask(taskId: string, decision: "approve" | "reject") {
    const task = humanTasks.find((item) => item.id === taskId);
    if (!task) throw new Error("Human task not found.");
    task.status = decision === "approve" ? "approved" : "rejected";
    return task;
  },
  async listAdminCollection(path: string, scopeOverride?: Partial<ConsoleScope>) {
    void scopeOverride;
    return page([{ id: `${path.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "")}_demo`, status: "active" }]);
  },
  async createAdminItem(path: string, payload: Record<string, unknown>) {
    return { id: String(payload.id || `${path.replace(/[^a-z0-9]+/gi, "_")}_${Date.now()}`), status: "active", ...payload };
  },
  async updateAdminItem(path: string, resourceId: string, payload: Record<string, unknown>) {
    return { id: resourceId, status: "active", path, ...payload };
  },
  async deleteAdminItem(path: string, resourceId: string) {
    return { id: resourceId, status: "deleted", path, deleted_at: new Date().toISOString() };
  },
  async revokeOperatorSessions() {
    return undefined;
  },
  async listOperatorSessions(operatorId: string) {
    return page<ConsoleOperatorSession>([
      {
        id: "session_demo",
        operator_id: operatorId,
        status: "active",
        last_used_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString(),
        revoked_at: null,
        revoke_reason: null,
        ip_address: "127.0.0.1",
        user_agent: "Demo Browser",
      },
    ]);
  },
  async resetOperatorPassword() {
    return undefined;
  },
  async deleteOperator(operatorId: string) {
    return { id: operatorId, status: "deleted" };
  },
  async listServiceAccounts() {
    return page([{ id: "sa_demo", name: "demo-ci", status: "active", permissions: ["agent:read"] }]);
  },
  async createServiceAccount(payload: Record<string, unknown>) {
    return { id: `sa_demo_${Date.now()}`, status: "active", ...payload };
  },
  async updateServiceAccount(serviceAccountId: string, payload: Record<string, unknown>) {
    return { id: serviceAccountId, status: "active", ...payload };
  },
  async deleteServiceAccount(serviceAccountId: string) {
    return { id: serviceAccountId, status: "deleted" };
  },
  async listServiceAccountApiKeys(serviceAccountId: string) {
    return page([{ id: "key_demo", owner_id: serviceAccountId, name: "demo-key", status: "active", scopes: ["agent:read"] }]);
  },
  async createServiceAccountApiKey(serviceAccountId: string, payload: Record<string, unknown>): Promise<MachineApiKeyCreate> {
    return {
      item: { id: `key_demo_${Date.now()}`, owner_id: serviceAccountId, status: "active", ...payload },
      plain_key: "dr_demo_key_shown_once",
      request_id: null,
    };
  },
  async disableServiceAccountApiKey(serviceAccountId: string, keyId: string) {
    return { id: keyId, owner_id: serviceAccountId, status: "disabled" };
  },
};

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
  async getDashboardSummary() {
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
    const payload = await nativeClient().listAgents();
    return page(payload.map(mapNativeAgent));
  },
  async createAgent(payload: Record<string, unknown>): Promise<Agent> {
    const created = await nativeClient(crypto.randomUUID()).createAgent(payload);
    return mapNativeAgent(created);
  },
  async archiveAgent(agentId: string): Promise<Agent> {
    const archived = await nativeClient(crypto.randomUUID()).archiveAgent(agentId);
    return mapNativeAgent(archived);
  },
  async listDeployments(): Promise<CursorPage<Deployment>> {
    const payload = await nativeClient().listDeployments();
    return page(payload.map(mapNativeDeployment));
  },
  async controlDeployment(deploymentId: string, operation: string): Promise<Deployment> {
    const payload = await nativeClient(crypto.randomUUID()).controlDeployment(deploymentId, operation);
    return mapNativeDeployment(payload);
  },
  async listRuns(): Promise<CursorPage<Run>> {
    const payload = await nativeClient().listRuns();
    return page(payload.map(mapNativeRun));
  },
  async getRun(runId: string): Promise<Run | null> {
    const payload = await nativeClient().getRun(runId);
    return mapNativeRun(payload);
  },
  async controlRun(runId: string, operation: string): Promise<Run> {
    const payload = await nativeClient(crypto.randomUUID()).controlRun(runId, operation);
    return mapNativeRun(payload);
  },
  async listRunEvents(runId: string): Promise<CursorPage<RuntimeEvent>> {
    const payload = await nativeClient().listRunEvents(runId);
    return page(payload.map(mapNativeEvent));
  },
  async listTasks(): Promise<CursorPage<Task>> {
    const payload = await nativeClient().listTasks();
    return page(payload.map(mapNativeTask));
  },
  async cancelTask(taskId: string): Promise<Task> {
    const payload = await nativeClient(crypto.randomUUID()).cancelTask(taskId);
    return mapNativeTask(payload as NativeTaskRead);
  },
  async listEvents(): Promise<CursorPage<RuntimeEvent>> {
    return page([]);
  },
  async listHumanTasks(): Promise<CursorPage<HumanTask>> {
    const payload = await nativeClient().listAdminCollection<AdminResource>("/v1/human-tasks");
    return page(payload.items.map(mapAdminHumanTask));
  },
  async decideHumanTask(taskId: string, decision: "approve" | "reject"): Promise<HumanTask> {
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
  async updateAdminItem(path: string, resourceId: string, payload: Record<string, unknown>): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).updateAdminItem<AdminResource>(path, resourceId, payload);
    return response.item;
  },
  async deleteAdminItem(path: string, resourceId: string): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).deleteAdminItem<AdminResource>(path, resourceId);
    return response.item;
  },
  async revokeOperatorSessions(operatorId: string): Promise<void> {
    await nativeClient(crypto.randomUUID()).postAdminAction(`/v1/identity/operators/${operatorId}/revoke-sessions`);
  },
  async listOperatorSessions(operatorId: string): Promise<CursorPage<ConsoleOperatorSession>> {
    const payload = await nativeClient().listAdminCollection<ConsoleOperatorSession>(`/v1/identity/operators/${operatorId}/sessions`);
    return page(payload.items);
  },
  async resetOperatorPassword(operatorId: string, newPassword: string): Promise<void> {
    await nativeClient(crypto.randomUUID()).postAdminAction(`/v1/identity/operators/${operatorId}/reset-password`, {
      new_password: newPassword,
    });
  },
  async deleteOperator(operatorId: string): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).deleteAdminItem<AdminResource>("/v1/identity/operators", operatorId);
    return response.item;
  },
  async listServiceAccounts(): Promise<CursorPage<AdminResource>> {
    return this.listAdminCollection("/v1/identity/service-accounts");
  },
  async createServiceAccount(payload: Record<string, unknown>): Promise<AdminResource> {
    return this.createAdminItem("/v1/identity/service-accounts", payload);
  },
  async updateServiceAccount(serviceAccountId: string, payload: Record<string, unknown>): Promise<AdminResource> {
    return this.updateAdminItem("/v1/identity/service-accounts", serviceAccountId, payload);
  },
  async deleteServiceAccount(serviceAccountId: string): Promise<AdminResource> {
    return this.deleteAdminItem("/v1/identity/service-accounts", serviceAccountId);
  },
  async listServiceAccountApiKeys(serviceAccountId: string): Promise<CursorPage<AdminResource>> {
    return this.listAdminCollection(`/v1/identity/service-accounts/${serviceAccountId}/api-keys`);
  },
  async createServiceAccountApiKey(serviceAccountId: string, payload: Record<string, unknown>): Promise<MachineApiKeyCreate> {
    return nativeClient(crypto.randomUUID()).createAdminItem<MachineApiKeyCreate["item"]>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys`,
      payload,
    ) as Promise<MachineApiKeyCreate>;
  },
  async disableServiceAccountApiKey(serviceAccountId: string, keyId: string): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<AdminResource>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys/${keyId}/disable`,
    );
    return response.item;
  },
};

export const consoleClient = isDemoMode() ? demoConsoleClient : liveConsoleClient;
