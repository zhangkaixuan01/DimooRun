export type StatusTone = "success" | "warning" | "danger" | "neutral" | "running";

export type Agent = {
  id: string;
  name: string;
  framework: "LangGraph" | "LangChain" | "DeepAgents";
  adapter: string;
  version: string;
  capabilities: string[];
  deployments: number;
  lastRunStatus: string;
  releasedAt: string;
};

export type Deployment = {
  id: string;
  agent: string;
  version: string;
  environment: string;
  desiredStatus: "active" | "paused" | "draining" | "stopped";
  runtimeStatus: "ready" | "degraded" | "warming_up";
  instances: number;
  runningRuns: number;
  queueBacklog: number;
  worker: string;
  heartbeatAt: string;
  executionProfile: string;
  modelGateway: string;
};

export type Run = {
  id: string;
  agent: string;
  framework: string;
  adapter: string;
  version: string;
  actor: string;
  status: "succeeded" | "failed" | "running" | "timeout";
  latencyMs: number;
  costUsd: number;
  startedAt: string;
  finishedAt?: string;
  trigger: "api" | "schedule" | "replay" | "batch" | "compatibility";
  deployment: string;
  traceId: string;
};

export type RuntimeEvent = {
  sequence: number;
  eventId: string;
  type: string;
  status: string;
  timestamp: string;
  summary: string;
};

export type Task = {
  id: string;
  runId: string;
  status: "leased" | "retrying" | "dead_letter" | "succeeded";
  attempt: number;
  queue: string;
  workerId: string;
  heartbeatAt: string;
  leaseUntil: string;
  fencingToken: number;
  retryCount: number;
  deadLetterReason?: string;
};

export type HumanTask = {
  id: string;
  source: string;
  risk: "medium" | "high" | "critical";
  status: "pending" | "approved" | "rejected";
  assignee: string;
  expiresAt: string;
};
