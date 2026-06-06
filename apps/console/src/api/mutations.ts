import { ref } from "vue";

import type { ConsoleApiError } from "./client";

export type MutationContext = {
  auditReason?: string;
};

export type MutationOptions = {
  reload?: () => Promise<unknown>;
};

export type MutationAction<TPayload, TResult> = {
  busy: ReturnType<typeof ref<boolean>>;
  error: ReturnType<typeof ref<ConsoleApiError | null>>;
  run: (payload: TPayload, context?: MutationContext) => Promise<TResult>;
};

export function createMutationAction<TPayload = void, TResult = unknown>(
  action: (payload: TPayload, context: MutationContext) => Promise<TResult>,
  options: MutationOptions = {},
): MutationAction<TPayload, TResult> {
  const busy = ref(false);
  const error = ref<ConsoleApiError | null>(null);

  async function run(payload: TPayload, context: MutationContext = {}): Promise<TResult> {
    busy.value = true;
    error.value = null;
    try {
      const result = await action(payload, context);
      await options.reload?.();
      return result;
    } catch (caught) {
      const normalized = normalizeMutationError(caught);
      error.value = normalized;
      throw normalized;
    } finally {
      busy.value = false;
    }
  }

  return { busy, error, run };
}

export function normalizeMutationError(error: unknown): ConsoleApiError {
  if (isRecord(error)) {
    const status = Number(error.status || 0);
    const errorCode = String(error.errorCode || error.error_code || "");
    return {
      errorCode: errorCode || (status === 409 ? "resource_conflict" : "mutation_failed"),
      message: String(error.message || "Mutation failed."),
      requestId: typeof error.requestId === "string"
        ? error.requestId
        : typeof error.request_id === "string"
          ? error.request_id
          : null,
      details: isRecord(error.details) ? error.details : null,
    };
  }
  if (error instanceof Error) {
    return {
      errorCode: "mutation_failed",
      message: error.message,
      requestId: null,
      details: null,
    };
  }
  return {
    errorCode: "mutation_failed",
    message: "Mutation failed.",
    requestId: null,
    details: null,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
