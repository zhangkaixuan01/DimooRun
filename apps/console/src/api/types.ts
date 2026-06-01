export type StatusTone = "success" | "warning" | "danger" | "neutral" | "running" | "disabled";
export type ResourceId = number;

export type Agent = {
  id: ResourceId;
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
  id: ResourceId;
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
  id: ResourceId;
  agent: string;
  framework: string;
  adapter: string;
  version: string;
  actor: string;
  status: "succeeded" | "failed" | "running" | "timeout" | "cancelled";
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
  id: ResourceId;
  runId: ResourceId;
  status: "queued" | "leased" | "running" | "retrying" | "dead_letter" | "succeeded" | "cancelled";
  attempt: number;
  queue: string;
  workerId: string;
  heartbeatAt: string;
  leaseUntil: string;
  fencingToken: number;
  retryCount: number;
  deadLetterReason?: string;
  partitionKey?: string;
  resourceClass?: string;
  quotaBlockingReason?: {
    errorCode: string;
    scope: string;
    limit: number;
    current: number;
  };
};

export type HumanTask = {
  id: ResourceId;
  source: string;
  risk: "medium" | "high" | "critical";
  status: "pending" | "approved" | "rejected";
  assignee: string;
  expiresAt: string;
};
