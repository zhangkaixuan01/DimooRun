export type StatusTone = "success" | "warning" | "danger" | "neutral" | "running" | "disabled";
export type ResourceId = number;

export type Agent = {
  id: ResourceId;
  name: string;
  description: string | null;
  status: string;
  createdAt: string | null;
  versionCount: number;
  deploymentCount: number;
};

export type AgentVersion = {
  id: ResourceId;
  agentId: ResourceId;
  version: string;
  packageUri: string;
  framework: string;
  adapter: string;
  entrypoint: string;
  capabilities: Record<string, unknown>;
  manifest: Record<string, unknown>;
  status: string;
};

export type Deployment = {
  id: ResourceId;
  agent: string;
  version: string;
  environment: string;
  desiredStatus: "active" | "paused" | "draining" | "stopped";
  runtimeStatus: "ready" | "degraded" | "warming_up";
  instances: number;
  config: Record<string, unknown>;
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
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  latencyMs: number | null;
  costUsd?: number;
  trigger: "api" | "schedule" | "replay" | "batch" | "compatibility";
  deployment: string;
  traceId: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
};

export type RuntimeEvent = {
  runId: ResourceId;
  sequence: number;
  eventId: string;
  type: string;
  status: string;
  timestamp?: string;
  summary: string;
  payload?: Record<string, unknown>;
};

export type RunAttempt = {
  id: ResourceId;
  runId: ResourceId;
  taskId: ResourceId | null;
  attemptNo: number;
  workerId: string | null;
  status: string;
  error: string | null;
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

export type TaskCreateResult = {
  runId: ResourceId;
  taskId: ResourceId;
  status: string;
  replayed: boolean;
};

export type HumanTask = {
  id: ResourceId;
  source: string;
  risk: "medium" | "high" | "critical";
  status: "pending" | "approved" | "rejected";
  assignee: string;
  expiresAt: string;
};
