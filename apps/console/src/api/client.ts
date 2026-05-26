import { agents, deployments, events, humanTasks, runs, tasks } from "./mockData";
import type { Agent, Deployment, Run } from "./types";
import {
  createDimooRunClient,
  type NativeAgentRead,
  type NativeDeploymentRead,
  type NativeRunRead,
} from "./generated/dimoorun";

export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};

function page<T>(items: T[]): CursorPage<T> {
  return { items, nextCursor: null };
}

function nativeBaseUrl(): string | null {
  return import.meta.env.VITE_DIMOORUN_API_BASE_URL || null;
}

function nativeHeaders(idempotencyKey?: string): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-Id": crypto.randomUUID(),
    "X-Tenant-Id": import.meta.env.VITE_DIMOORUN_TENANT_ID || "tenant_1",
    "X-Project-Id": import.meta.env.VITE_DIMOORUN_PROJECT_ID || "project_1",
  };
  const apiKey = import.meta.env.VITE_DIMOORUN_API_KEY;
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  return headers;
}

function nativeClient(idempotencyKey?: string) {
  const baseUrl = nativeBaseUrl();
  if (!baseUrl) throw new Error("DimooRun API base URL is not configured.");
  return createDimooRunClient({
    baseUrl,
    headers: nativeHeaders(idempotencyKey),
  });
}

function mapNativeAgent(agent: NativeAgentRead): Agent {
  return {
    id: agent.id,
    name: agent.name,
    framework: "LangGraph",
    adapter: "langgraph",
    version: "latest",
    capabilities: [],
    deployments: 0,
    lastRunStatus: agent.status,
    releasedAt: new Date().toISOString(),
  };
}

function mapNativeRun(run: NativeRunRead): Run {
  return {
    id: run.id,
    agent: run.agent_id,
    framework: "LangGraph",
    adapter: "langgraph",
    version: run.agent_version_id,
    actor: "api",
    status: run.status === "pending" ? "running" : (run.status as Run["status"]),
    latencyMs: 0,
    costUsd: 0,
    startedAt: new Date().toISOString(),
    trigger: "api",
    deployment: run.deployment_id || "direct",
    traceId: run.thread_id || run.id,
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

export const consoleClient = {
  getDashboardSummary() {
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
    };
  },
  listAgents: () => page(agents),
  listDeployments: () => page(deployments),
  listRuns: () => page(runs),
  getRun(runId: string): Run | null {
    return runs.find((run) => run.id === runId) ?? null;
  },
  listTasks: () => page(tasks),
  listEvents: () => page(events),
  listHumanTasks: () => page(humanTasks),
};

export const nativeConsoleClient = {
  async listAgents(): Promise<CursorPage<Agent>> {
    const payload = await nativeClient().listAgents();
    return page(payload.map(mapNativeAgent));
  },
  async listDeployments(): Promise<CursorPage<Deployment>> {
    const payload = await nativeClient().listDeployments();
    return page(payload.map(mapNativeDeployment));
  },
  async getRun(runId: string): Promise<Run> {
    const payload = await nativeClient().getRun(runId);
    return mapNativeRun(payload);
  },
  async createRun(agentId: string, input: Record<string, unknown>) {
    const idempotencyKey = crypto.randomUUID();
    return nativeClient(idempotencyKey).createTask(agentId, input, idempotencyKey);
  },
};
