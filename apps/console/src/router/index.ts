import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import AgentsPage from "../pages/agents/AgentsPage.vue";
import CompatibilityPage from "../pages/compatibility/CompatibilityPage.vue";
import DashboardPage from "../pages/dashboard/DashboardPage.vue";
import DeploymentsPage from "../pages/deployments/DeploymentsPage.vue";
import EventsPage from "../pages/events/EventsPage.vue";
import ApiKeysPage from "../pages/governance/ApiKeysPage.vue";
import HumanTasksPage from "../pages/governance/HumanTasksPage.vue";
import PoliciesPage from "../pages/governance/PoliciesPage.vue";
import PublishedSurfacesPage from "../pages/published/PublishedSurfacesPage.vue";
import ReplayPage from "../pages/replay/ReplayPage.vue";
import RunDetailPage from "../pages/runs/RunDetailPage.vue";
import RunsPage from "../pages/runs/RunsPage.vue";
import SettingsPage from "../pages/settings/SettingsPage.vue";
import TasksPage from "../pages/tasks/TasksPage.vue";

export const routes: RouteRecordRaw[] = [
  { path: "/", redirect: "/dashboard" },
  { path: "/dashboard", name: "dashboard", component: DashboardPage },
  { path: "/agents", name: "agents", component: AgentsPage },
  { path: "/deployments", name: "deployments", component: DeploymentsPage },
  { path: "/compatibility", name: "compatibility", component: CompatibilityPage },
  { path: "/published-surfaces", name: "published-surfaces", component: PublishedSurfacesPage },
  { path: "/runs", name: "runs", component: RunsPage },
  { path: "/runs/:runId", name: "run-detail", component: RunDetailPage, props: true },
  { path: "/tasks", name: "tasks", component: TasksPage },
  { path: "/events", name: "events", component: EventsPage },
  { path: "/replay", name: "replay", component: ReplayPage },
  { path: "/governance/human-tasks", name: "human-tasks", component: HumanTasksPage },
  { path: "/governance/policies", name: "policies", component: PoliciesPage },
  { path: "/governance/api-keys", name: "api-keys", component: ApiKeysPage },
  { path: "/settings", name: "settings", component: SettingsPage },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
