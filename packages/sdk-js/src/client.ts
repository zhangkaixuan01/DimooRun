import {
  AgentCreateRequest,
  AgentVersionCreateRequest,
  DeploymentCreateRequest,
  DimooRunClientOptions,
  JsonObject,
  PackageValidationResult,
  TaskSubmitRequest,
} from "./types";

export class DimooRunAPIError extends Error {
  readonly errorCode: string;
  readonly requestId: string | null;
  readonly details: JsonObject;

  constructor(params: {
    errorCode: string;
    message: string;
    requestId: string | null;
    details: JsonObject;
  }) {
    super(params.message);
    this.name = "DimooRunAPIError";
    this.errorCode = params.errorCode;
    this.requestId = params.requestId;
    this.details = params.details;
  }
}

export class DimooRunClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly tenantId?: number;
  private readonly projectId?: number;
  private readonly environment?: string;
  private readonly actorId?: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: DimooRunClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.tenantId = options.tenantId;
    this.projectId = options.projectId;
    this.environment = options.environment;
    this.actorId = options.actorId;
    this.fetchImpl = options.fetch ?? fetch;
  }

  validatePackage(params: {
    packageUri: string;
    framework: string;
    adapter: string;
    entrypoint: string;
    manifest?: JsonObject;
    requiredSecretRefs?: string[];
  }): Promise<PackageValidationResult> {
    return this.request("POST", "/v1/packages/validate", {
      package_uri: params.packageUri,
      framework: params.framework,
      adapter: params.adapter,
      entrypoint: params.entrypoint,
      manifest: params.manifest ?? {},
      required_secret_refs: params.requiredSecretRefs ?? [],
    });
  }

  createAgent(payload: AgentCreateRequest): Promise<JsonObject> {
    return this.request("POST", "/v1/agents", payload);
  }

  createAgentVersion(agentId: number, payload: AgentVersionCreateRequest): Promise<JsonObject> {
    return this.request("POST", `/v1/agents/${agentId}/versions`, {
      capabilities: {},
      manifest: {},
      status: "draft",
      ...payload,
    });
  }

  createDeployment(payload: DeploymentCreateRequest): Promise<JsonObject> {
    return this.request("POST", "/v1/deployments", {
      desired_status: "draft",
      replicas: 1,
      config: {},
      ...payload,
    });
  }

  createRun(agentId: number, payload: TaskSubmitRequest, idempotencyKey?: string): Promise<JsonObject> {
    return this.request("POST", `/v1/agents/${agentId}/tasks`, payload, idempotencyKey);
  }

  submitDeploymentTask(
    deploymentId: number,
    payload: TaskSubmitRequest,
    idempotencyKey?: string,
  ): Promise<JsonObject> {
    return this.request(
      "POST",
      `/v1/deployments/${deploymentId}/tasks`,
      payload,
      idempotencyKey,
    );
  }

  getRun(runId: number): Promise<JsonObject> {
    return this.request("GET", `/v1/runs/${runId}`);
  }

  listRunEvents(runId: number): Promise<JsonObject[]> {
    return this.request("GET", `/v1/runs/${runId}/events`, undefined, undefined, true);
  }

  replayRun(runId: number, agentVersionId?: number): Promise<JsonObject> {
    return this.request("POST", `/v1/runs/${runId}/replay`, {
      ...(agentVersionId === undefined ? {} : { agent_version_id: agentVersionId }),
    });
  }

  getTask(taskId: number): Promise<JsonObject> {
    return this.request("GET", `/v1/tasks/${taskId}`);
  }

  private async request(
    method: string,
    path: string,
    payload?: JsonObject,
    idempotencyKey?: string,
    expectList = false,
  ): Promise<JsonObject | JsonObject[]> {
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method,
      headers: this.headers(idempotencyKey),
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
    const raw = await response.json();
    if (!response.ok) {
      const details = isRecord(raw.details) ? raw.details : {};
      throw new DimooRunAPIError({
        errorCode: String(raw.error_code ?? "unknown"),
        message: String(raw.message ?? response.statusText),
        requestId: typeof raw.request_id === "string" ? raw.request_id : null,
        details,
      });
    }
    if (expectList) {
      if (!Array.isArray(raw)) {
        throw new DimooRunAPIError({
          errorCode: "invalid_response",
          message: "Expected a JSON array response.",
          requestId: null,
          details: {},
        });
      }
      return raw.map(ensureRecord);
    }
    return ensureRecord(raw);
  }

  private headers(idempotencyKey?: string): HeadersInit {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.apiKey}`,
      "Content-Type": "application/json",
      "X-Request-Id": `req_sdk_${crypto.randomUUID().replace(/-/g, "")}`,
    };
    if (this.tenantId !== undefined) headers["X-Tenant-Id"] = String(this.tenantId);
    if (this.projectId !== undefined) headers["X-Project-Id"] = String(this.projectId);
    if (this.environment !== undefined) headers["X-Environment"] = this.environment;
    if (this.actorId !== undefined) headers["X-Actor-Id"] = this.actorId;
    if (idempotencyKey !== undefined) headers["Idempotency-Key"] = idempotencyKey;
    return headers;
  }
}

function isRecord(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function ensureRecord(value: unknown): JsonObject {
  if (!isRecord(value)) {
    throw new DimooRunAPIError({
      errorCode: "invalid_response",
      message: "Expected a JSON object response.",
      requestId: null,
      details: {},
    });
  }
  return value;
}
