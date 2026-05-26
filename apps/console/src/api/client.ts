import { agents, deployments, events, humanTasks, runs, tasks } from "./mockData";

export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};

function page<T>(items: T[]): CursorPage<T> {
  return { items, nextCursor: null };
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
  listTasks: () => page(tasks),
  listEvents: () => page(events),
  listHumanTasks: () => page(humanTasks),
};
