import { describe, expect, it } from "vitest";

import { createMutationAction } from "../../src/api/mutations";

describe("createMutationAction", () => {
  it("tracks busy state and triggers canonical reload after success", async () => {
    const events: string[] = [];
    const mutation = createMutationAction(
      async (payload: { id: number }, context) => {
        events.push(`audit:${context.auditReason}`);
        return { id: payload.id, status: "updated" };
      },
      {
        reload: async () => events.push("reload"),
      },
    );

    const result = await mutation.run({ id: 7 }, { auditReason: "operator approved" });

    expect(result).toEqual({ id: 7, status: "updated" });
    expect(mutation.busy.value).toBe(false);
    expect(mutation.error.value).toBeNull();
    expect(events).toEqual(["audit:operator approved", "reload"]);
  });

  it("normalizes conflict errors", async () => {
    const mutation = createMutationAction(async () => {
      throw { status: 409, message: "duplicate idempotency key", requestId: "req-1" };
    });

    await expect(mutation.run(undefined)).rejects.toMatchObject({
      errorCode: "resource_conflict",
      message: "duplicate idempotency key",
      requestId: "req-1",
    });
    expect(mutation.error.value?.errorCode).toBe("resource_conflict");
  });
});
