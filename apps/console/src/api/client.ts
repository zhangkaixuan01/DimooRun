import { agents, deployments, events, humanTasks, runs, tasks } from "./mockData";
import type { Agent, Deployment, Run } from "./types";

export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};

type NativeAgentRead = {
  id: string;
  name: string;
  status: string;
};

type NativeRunRead = {
  id: string;
  agent_id: string;
  agent_version_id: string;
  deployment_id: string | null;
  status: string;
  thread_id: string | null;
};

type NativeTaskCreateResponse = {
  run_id: string;
  task_id: string;
  status: string;
  replayed: boolean;
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

async function nativeFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = nativeBaseUrl();
  if (!baseUrl) throw new Error("DimooRun API base URL is not configured.");
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: init?.headers,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.message || `DimooRun API request failed: ${response.status}`);
  }
  return payload as T;
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
    const payload = await nativeFetch<NativeAgentRead[]>("/v1/agents", {
      headers: nativeHeaders(),
    });
    return page(payload.map(mapNativeAgent));
  },
  async listDeployments(): Promise<CursorPage<Deployment>> {
    const payload = await nativeFetch<Deployment[]>("/v1/deployments", {
      headers: nativeHeaders(),
    });
    return page(payload);
  },
  async getRun(runId: string): Promise<Run> {
    const payload = await nativeFetch<NativeRunRead>(`/v1/runs/${runId}`, {
      headers: nativeHeaders(),
    });
    return mapNativeRun(payload);
  },
  async createRun(agentId: string, input: Record<string, unknown>) {
    return nativeFetch<NativeTaskCreateResponse>(`/v1/agents/${agentId}/tasks`, {
      method: "POST",
      headers: nativeHeaders(crypto.randomUUID()),
      body: JSON.stringify({ input }),
    });
  },
};
