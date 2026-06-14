import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import AgentsPage from "../pages/agents/AgentsPage.vue";
import CompatibilityExplorerPage from "../pages/compatibility/CompatibilityExplorerPage.vue";
import DashboardPage from "../pages/dashboard/DashboardPage.vue";
import DeploymentDetailPage from "../pages/deployments/DeploymentDetailPage.vue";
import DeploymentsPage from "../pages/deployments/DeploymentsPage.vue";
import EventsPage from "../pages/events/EventsPage.vue";
import HumanTasksPage from "../pages/governance/HumanTasksPage.vue";
import ModelGatewayWorkbenchPage from "../pages/governance/ModelGatewayWorkbenchPage.vue";
import SecretRotationPage from "../pages/governance/SecretRotationPage.vue";
import ToolGatewayWorkbenchPage from "../pages/governance/ToolGatewayWorkbenchPage.vue";
import AdminCollectionPage from "../pages/admin/AdminCollectionPage.vue";
import LoginPage from "../pages/auth/LoginPage.vue";
import AssetDetailPage from "../pages/catalog/AssetDetailPage.vue";
import AssetVersionDiffPage from "../pages/catalog/AssetVersionDiffPage.vue";
import CatalogPage from "../pages/catalog/CatalogPage.vue";
import IdentityScopePage from "../pages/identity/IdentityScopePage.vue";
import IncidentTriagePage from "../pages/incidents/IncidentTriagePage.vue";
import MachineIdentityPage from "../pages/identity/MachineIdentityPage.vue";
import OperatorsPage from "../pages/identity/OperatorsPage.vue";
import RolePermissionMatrixPage from "../pages/identity/RolePermissionMatrixPage.vue";
import ServiceAccountDetailPage from "../pages/identity/ServiceAccountDetailPage.vue";
import UserAccessDetailPage from "../pages/identity/UserAccessDetailPage.vue";
import BudgetsPage from "../pages/observability/BudgetsPage.vue";
import CostsPage from "../pages/observability/CostsPage.vue";
import BackupRestorePage from "../pages/ops/BackupRestorePage.vue";
import PackageRegistrationPage from "../pages/packages/PackageRegistrationPage.vue";
import PolicyWorkbenchPage from "../pages/policies/PolicyWorkbenchPage.vue";
import PublishedSurfacesPage from "../pages/published/PublishedSurfacesPage.vue";
import DatasetsPage from "../pages/quality/DatasetsPage.vue";
import ExperimentsPage from "../pages/quality/ExperimentsPage.vue";
import QualityGatePage from "../pages/quality/QualityGatePage.vue";
import ReplayPage from "../pages/replay/ReplayPage.vue";
import ReplayComparisonPage from "../pages/replay/ReplayComparisonPage.vue";
import AgentInstancesPage from "../pages/runtime/AgentInstancesPage.vue";
import BatchRunsPage from "../pages/runtime/BatchRunsPage.vue";
import CapacityPage from "../pages/runtime/CapacityPage.vue";
import ScheduledRunsPage from "../pages/runtime/ScheduledRunsPage.vue";
import WorkersPage from "../pages/runtime/WorkersPage.vue";
import RunDetailPage from "../pages/runs/RunDetailPage.vue";
import RunTriagePage from "../pages/runs/RunTriagePage.vue";
import RunsPage from "../pages/runs/RunsPage.vue";
import DangerZonePage from "../pages/settings/DangerZonePage.vue";
import PlatformSettingsPage from "../pages/settings/PlatformSettingsPage.vue";
import ProviderStatusPage from "../pages/settings/ProviderStatusPage.vue";
import SettingsPage from "../pages/settings/SettingsPage.vue";
import TasksPage from "../pages/tasks/TasksPage.vue";
import { useAuthStore } from "../stores/auth";

export const routes: RouteRecordRaw[] = [
  { path: "/", redirect: "/dashboard" },
  { path: "/login", name: "login", component: LoginPage, meta: { public: true } },
  { path: "/dashboard", name: "dashboard", component: DashboardPage },
  { path: "/agents", name: "agents", component: AgentsPage },
  { path: "/packages/register", name: "package-registration", component: PackageRegistrationPage },
  { path: "/deployments", name: "deployments", component: DeploymentsPage },
  { path: "/deployments/:deploymentId", name: "deployment-detail", component: DeploymentDetailPage, props: true },
  { path: "/compatibility", name: "compatibility", component: CompatibilityExplorerPage },
  { path: "/published-surfaces", name: "published-surfaces", component: PublishedSurfacesPage },
  { path: "/published-surfaces/:surfaceId", name: "published-surface-detail", component: PublishedSurfacesPage, props: true },
  { path: "/runtime/workers", name: "runtime-workers", component: WorkersPage },
  { path: "/runtime/agent-instances", name: "runtime-agent-instances", component: AgentInstancesPage },
  { path: "/runtime/capacity", name: "runtime-capacity", component: CapacityPage },
  { path: "/runtime/schedules", name: "runtime-schedules", component: ScheduledRunsPage },
  { path: "/runtime/batches", name: "runtime-batches", component: BatchRunsPage },
  { path: "/runs", name: "runs", component: RunsPage },
  { path: "/runs/:runId", name: "run-detail", component: RunDetailPage, props: true },
  { path: "/runs/:runId/triage", name: "run-triage", component: RunTriagePage, props: true },
  { path: "/tasks", name: "tasks", component: TasksPage },
  { path: "/events", name: "events", component: EventsPage },
  { path: "/replay", name: "replay", component: ReplayPage },
  { path: "/replay/compare", name: "replay-comparison", component: ReplayComparisonPage },
  { path: "/governance/human-tasks", name: "human-tasks", component: HumanTasksPage },
  { path: "/governance/policies", name: "policies", component: PolicyWorkbenchPage },
  { path: "/governance/api-keys", redirect: "/identity/machine-identities" },
  {
    path: "/identity/operators",
    name: "operators",
    component: OperatorsPage,
  },
  {
    path: "/identity/operators/:operatorId",
    name: "operator-detail",
    component: UserAccessDetailPage,
    props: true,
  },
  {
    path: "/identity/scopes",
    name: "identity-scopes",
    component: IdentityScopePage,
  },
  { path: "/identity/tenants", redirect: "/identity/scopes" },
  { path: "/identity/projects", redirect: "/identity/scopes" },
  { path: "/identity/environments", redirect: "/identity/scopes" },
  { path: "/identity/users", redirect: "/identity/operators" },
  {
    path: "/identity/roles-permissions",
    name: "roles-permissions",
    component: RolePermissionMatrixPage,
  },
  { path: "/identity/roles", redirect: "/identity/roles-permissions" },
  { path: "/identity/permissions", redirect: "/identity/roles-permissions" },
  {
    path: "/identity/machine-identities",
    name: "machine-identities",
    component: MachineIdentityPage,
  },
  {
    path: "/identity/service-accounts/:serviceAccountId",
    name: "service-account-detail",
    component: ServiceAccountDetailPage,
    props: true,
  },
  { path: "/identity/service-accounts", redirect: "/identity/machine-identities" },
  {
    path: "/governance/model-gateways",
    name: "model-gateways",
    component: ModelGatewayWorkbenchPage,
  },
  {
    path: "/governance/tools",
    name: "tools",
    component: ToolGatewayWorkbenchPage,
  },
  {
    path: "/governance/secrets",
    name: "secrets",
    component: SecretRotationPage,
  },
  {
    path: "/governance/catalog-items",
    name: "catalog-items",
    component: CatalogPage,
    props: {
      kind: "catalog",
      title: "Catalog Items",
      description: "Reusable runtime catalog entries exposed to teams.",
      detailRouteName: "catalog-item-detail",
    },
  },
  {
    path: "/governance/catalog-items/:assetId",
    name: "catalog-item-detail",
    component: AssetDetailPage,
    props: (route) => ({
      kind: "catalog",
      assetId: Number(route.params.assetId),
      listRouteName: "catalog-items",
      detailRouteName: "catalog-item-detail",
      diffRouteName: "catalog-item-diff",
    }),
  },
  {
    path: "/governance/catalog-items/:assetId/diff",
    name: "catalog-item-diff",
    component: AssetVersionDiffPage,
    props: (route) => ({
      kind: "catalog",
      assetId: Number(route.params.assetId),
      detailRouteName: "catalog-item-detail",
    }),
  },
  {
    path: "/governance/prompt-assets",
    name: "prompt-assets",
    component: CatalogPage,
    props: {
      kind: "prompt",
      title: "Prompt Assets",
      description: "Prompt assets available to agents and evaluations.",
      detailRouteName: "prompt-asset-detail",
    },
  },
  {
    path: "/governance/prompt-assets/:assetId",
    name: "prompt-asset-detail",
    component: AssetDetailPage,
    props: (route) => ({
      kind: "prompt",
      assetId: Number(route.params.assetId),
      listRouteName: "prompt-assets",
      detailRouteName: "prompt-asset-detail",
      diffRouteName: "prompt-asset-diff",
    }),
  },
  {
    path: "/governance/prompt-assets/:assetId/diff",
    name: "prompt-asset-diff",
    component: AssetVersionDiffPage,
    props: (route) => ({
      kind: "prompt",
      assetId: Number(route.params.assetId),
      detailRouteName: "prompt-asset-detail",
    }),
  },
  {
    path: "/governance/config-assets",
    name: "config-assets",
    component: CatalogPage,
    props: {
      kind: "config",
      title: "Config Assets",
      description: "Config assets and rollout state.",
      detailRouteName: "config-asset-detail",
    },
  },
  {
    path: "/governance/config-assets/:assetId",
    name: "config-asset-detail",
    component: AssetDetailPage,
    props: (route) => ({
      kind: "config",
      assetId: Number(route.params.assetId),
      listRouteName: "config-assets",
      detailRouteName: "config-asset-detail",
      diffRouteName: "config-asset-diff",
    }),
  },
  {
    path: "/governance/config-assets/:assetId/diff",
    name: "config-asset-diff",
    component: AssetVersionDiffPage,
    props: (route) => ({
      kind: "config",
      assetId: Number(route.params.assetId),
      detailRouteName: "config-asset-detail",
    }),
  },
  {
    path: "/governance/template-assets",
    name: "template-assets",
    component: CatalogPage,
    props: {
      kind: "template",
      title: "Template Assets",
      description: "Template assets for reusable runtime surfaces.",
      detailRouteName: "template-asset-detail",
    },
  },
  {
    path: "/governance/template-assets/:assetId",
    name: "template-asset-detail",
    component: AssetDetailPage,
    props: (route) => ({
      kind: "template",
      assetId: Number(route.params.assetId),
      listRouteName: "template-assets",
      detailRouteName: "template-asset-detail",
      diffRouteName: "template-asset-diff",
    }),
  },
  {
    path: "/governance/template-assets/:assetId/diff",
    name: "template-asset-diff",
    component: AssetVersionDiffPage,
    props: (route) => ({
      kind: "template",
      assetId: Number(route.params.assetId),
      detailRouteName: "template-asset-detail",
    }),
  },
  {
    path: "/observability/audit-logs",
    name: "audit-logs",
    component: AdminCollectionPage,
    props: { title: "Audit Logs", kicker: "Observability", description: "Security and governance audit facts.", resourcePath: "/v1/audit-logs", seedName: "audit-log" },
  },
  {
    path: "/observability/artifacts",
    name: "artifacts-admin",
    component: AdminCollectionPage,
    props: { title: "Artifacts", kicker: "Observability", description: "Run artifacts and controlled download metadata.", resourcePath: "/v1/artifacts", seedName: "artifact" },
  },
  {
    path: "/observability/evaluations",
    name: "evaluation-results",
    component: AdminCollectionPage,
    props: { title: "Evaluation Results", kicker: "Observability", description: "Evaluation outputs linked to datasets and experiments.", resourcePath: "/v1/evaluations/results", seedName: "evaluation" },
  },
  {
    path: "/observability/datasets",
    name: "datasets",
    component: DatasetsPage,
  },
  {
    path: "/observability/experiments",
    name: "experiments",
    component: ExperimentsPage,
  },
  { path: "/observability/quality-gate", name: "quality-gate", component: QualityGatePage },
  { path: "/observability/costs", name: "costs", component: CostsPage },
  { path: "/observability/budgets", name: "budgets", component: BudgetsPage },
  {
    path: "/observability/replay-jobs",
    name: "replay-jobs",
    component: AdminCollectionPage,
    props: { title: "Replay Jobs", kicker: "Observability", description: "Replay jobs created from source runs.", resourcePath: "/v1/replay-jobs", seedName: "replay-job" },
  },
  {
    path: "/observability/feedback",
    name: "feedback",
    component: AdminCollectionPage,
    props: { title: "Feedback", kicker: "Observability", description: "Human and product feedback attached to runs.", resourcePath: "/v1/feedback", seedName: "feedback" },
  },
  {
    path: "/ops/backup-plans",
    redirect: "/ops/recovery",
  },
  { path: "/ops/recovery", name: "backup-restore", component: BackupRestorePage },
  { path: "/published-surfaces/ingress-routes", redirect: "/published-surfaces" },
  {
    path: "/ops/restore-jobs",
    redirect: "/ops/recovery",
  },
  {
    path: "/ops/webhooks",
    name: "webhooks",
    component: AdminCollectionPage,
    props: { title: "Webhook Subscriptions", kicker: "Enterprise Ops", description: "Outbound webhook subscriptions and delivery state.", resourcePath: "/v1/webhooks/subscriptions", seedName: "webhook" },
  },
  {
    path: "/ops/notifications",
    redirect: "/ops/incidents",
  },
  {
    path: "/ops/alerts",
    name: "alerts",
    component: AdminCollectionPage,
    props: { title: "Alert Rules", kicker: "Enterprise Ops", description: "Alert rules and notification routing.", resourcePath: "/v1/alerts/rules", seedName: "alert" },
  },
  {
    path: "/ops/incidents",
    name: "incidents",
    component: IncidentTriagePage,
  },
  {
    path: "/settings/platform",
    name: "platform-settings",
    component: PlatformSettingsPage,
  },
  {
    path: "/settings/providers",
    name: "provider-status",
    component: ProviderStatusPage,
  },
  {
    path: "/settings/danger-zone",
    name: "danger-zone",
    component: DangerZonePage,
  },
  {
    path: "/settings/semantic-store",
    name: "semantic-store",
    component: AdminCollectionPage,
    props: { title: "Semantic Store Providers", kicker: "Settings", description: "Semantic memory provider configuration.", resourcePath: "/v1/semantic-store/providers", seedName: "semantic-store" },
  },
  {
    path: "/settings/observability-exporters",
    name: "observability-exporters",
    component: AdminCollectionPage,
    props: { title: "Observability Exporters", kicker: "Settings", description: "Exporter destinations for traces, metrics, and events.", resourcePath: "/v1/observability/exporters", seedName: "exporter" },
  },
  {
    path: "/settings/sandbox-policies",
    name: "sandbox-policies",
    component: AdminCollectionPage,
    props: { title: "Sandbox Policies", kicker: "Settings", description: "Sandbox execution policy view.", resourcePath: "/v1/sandbox/policies", seedName: "sandbox-policy" },
  },
  {
    path: "/settings/container-pool-policies",
    name: "container-pool-policies",
    component: AdminCollectionPage,
    props: { title: "Container Pool Policies", kicker: "Settings", description: "Container pool policy and capacity view.", resourcePath: "/v1/container-pool/policies", seedName: "container-policy" },
  },
  { path: "/settings", name: "settings", component: SettingsPage },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (auth.token && !auth.operator) {
    await auth.hydrateSession();
  }
  if (to.meta.public) {
    return auth.isAuthenticated && to.path === "/login" ? "/dashboard" : true;
  }
  if (!auth.isAuthenticated) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }
  return true;
});
