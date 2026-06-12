export type JsonObject = Record<string, unknown>;

export type RunStatus =
  | "pending"
  | "running"
  | "interrupted"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "timeout";

export interface PackageValidationResult extends JsonObject {
  ready?: boolean;
  validation_token?: string | null;
}

export interface AgentCreateRequest {
  name: string;
  description?: string | null;
}

export interface AgentVersionCreateRequest {
  version: string;
  package_uri: string;
  framework: string;
  adapter: string;
  entrypoint: string;
  capabilities?: JsonObject;
  manifest?: JsonObject;
  status?: string;
}

export interface DeploymentCreateRequest {
  agent_id: number;
  agent_version_id: number;
  environment: string;
  desired_status?: string;
  replicas?: number;
  config?: JsonObject;
}

export interface TaskSubmitRequest {
  input: JsonObject;
  thread_id?: string | null;
}

export interface DimooRunClientOptions {
  apiKey: string;
  baseUrl: string;
  tenantId?: number;
  projectId?: number;
  environment?: string;
  actorId?: string;
  fetch?: typeof fetch;
}
