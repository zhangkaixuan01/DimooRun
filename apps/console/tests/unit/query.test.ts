import { describe, expect, it } from "vitest";

import { createQueryResource } from "../../src/api/query";
import {
  e2eOperator,
  e2eScope,
  makeAdminCollection,
  makeDashboardApi,
} from "../fixtures/api";

describe("console e2e API fixtures", () => {
  it("creates scoped dashboard API responses for deterministic workflow tests", () => {
    const api = makeDashboardApi();

    expect(e2eOperator.allowed_scopes[0]).toEqual(e2eScope);
    expect(api.deployments).toHaveLength(2);
    expect(api.runs.map((run) => run.status)).toEqual(["failed", "succeeded", "pending"]);
    expect(api.humanTasks.items).toHaveLength(2);
    expect(api.humanTasks.items.map((task) => task.status)).toEqual(["pending", "pending"]);
    expect(api.incidents.items[0]).toMatchObject({ status: "open", environment: "local" });
  });

  it("returns empty admin collections with request metadata", () => {
    expect(makeAdminCollection([])).toEqual({
      items: [],
      count: 0,
      request_id: "e2e-request",
    });
  });
});

describe("createQueryResource", () => {
  it("tracks loading, data, errors, retry, and reload", async () => {
    let calls = 0;
    const query = createQueryResource(async () => {
      calls += 1;
      if (calls === 1) throw new Error("first failure");
      return { ok: true, calls };
    });

    await query.reload();
    expect(query.error.value?.message).toBe("first failure");
    expect(query.data.value).toBeNull();
    expect(query.loading.value).toBe(false);

    await query.retry();
    expect(query.error.value).toBeNull();
    expect(query.data.value).toEqual({ ok: true, calls: 2 });
  });

  it("ignores stale responses and aborts the previous request", async () => {
    const aborted: boolean[] = [];
    const resolvers: Array<(value: string) => void> = [];
    const query = createQueryResource((signal) => {
      signal.addEventListener("abort", () => aborted.push(true));
      return new Promise<string>((resolve) => resolvers.push(resolve));
    });

    const first = query.reload();
    const second = query.reload();
    resolvers[1]("new");
    await second;
    resolvers[0]("old");
    await first;

    expect(aborted).toEqual([true]);
    expect(query.data.value).toBe("new");
  });
});
