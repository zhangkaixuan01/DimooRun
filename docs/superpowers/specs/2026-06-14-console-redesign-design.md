# DimooRun Console Operator Workbench Redesign

Date: 2026-06-14
Branch: `console-redesign-operator-workbench`
Status: Draft for review

## Goal

Redesign the entire `apps/console` frontend as an operator workbench for an
enterprise AI runtime control plane. The result should feel like a serious
daily-use operations console: dense enough for repeated work, calm enough for
long sessions, and explicit about runtime status, governance risk, scope, and
action feedback.

This is not a marketing page, command-center wallboard, prompt IDE, workflow
canvas, or low-code builder. The console is for operators, platform engineers,
governance reviewers, and developers who need to ship, inspect, replay, govern,
and recover agent runtime behavior.

## Approved Direction

Use the `Operator Workbench` direction:

- Persistent left navigation grouped by work plane.
- Sticky topbar with tenant, project, environment, API mode, search, refresh,
  theme, locale, operator, and logout controls.
- Flat, restrained visual system with clear borders, subtle surfaces, and
  minimal shadow.
- Compact typography and spacing, with no oversized dashboard/marketing
  treatment.
- Strong status semantics for runtime, governance, identity, cost, and settings.
- Full light and dark theme support, with light mode treated as the primary
  working surface.

## Non-Goals

- Do not replace Vue, Vite, Pinia, Vue Router, Naive UI, ECharts, or existing
  API contracts as part of the redesign.
- Do not introduce a landing page or hero section inside the console.
- Do not add large decorative gradients, bokeh/orb backgrounds, oversized
  cards, or theatrical dark-only dashboards.
- Do not change backend behavior, permissions, resource names, or route
  semantics unless needed to preserve existing UI contracts.
- Do not implement a drag-and-drop builder or visual agent workflow canvas.

## Frontend Bug Fix Policy

If frontend bugs are discovered while redesigning a touched area, fix them in
the same implementation stream when they are directly related to the console UI
or user workflow.

In scope:

- Broken or inconsistent loading, empty, error, disabled, offline, or permission
  states.
- Layout bugs, overflow, clipped text, broken wrapping, route-level horizontal
  scroll, and responsive regressions.
- Incorrect focus handling, inaccessible labels, keyboard traps, missing
  pointer/hover/focus feedback, and reduced-motion gaps.
- Stale UI state after create, edit, enable/disable, delete, retry, replay,
  approve, deny, or submit actions.
- i18n/locale issues where Chinese or English labels break navigation, tables,
  drawers, dialogs, or action bars.
- Chart, table, drawer, dialog, JSON editor, status badge, and shell behavior
  bugs uncovered while applying the shared patterns.

Out of scope unless explicitly approved:

- Backend API behavior changes.
- New product workflows or capabilities not already represented by current
  routes.
- Broad data-model changes, permission-model changes, or route contract changes.
- Large dependency changes whose only purpose is unrelated cleanup.

Every bug fix made during the redesign should be called out in the implementation
summary and covered by the closest practical verification: unit test, e2e test,
route smoke, screenshot inspection, or manual reproduction note.

## Design System

### Typography

Typography must be compact and utilitarian.

| Usage | Target size | Weight | Notes |
|---|---:|---:|---|
| Page title | 22-24px | 700-760 | No hero-scale headings in app pages. |
| Section/panel title | 14-16px | 700-760 | Keep dense control surfaces readable. |
| Body copy | 13-14px | 400-500 | Use line-height 1.45-1.6. |
| Table text | 12.5-13px | 400-600 | Keep numeric and status rows scannable. |
| Labels/kickers | 11-12px | 700-800 | No negative letter spacing. |
| Code/IDs/JSON | 12-13px | 400-600 | Use `--font-mono`; keep line-height >= 1.45. |
| Metric value | 22-24px | 740-780 | No 26px+ values unless explicitly approved during implementation review. |

Use system sans by default. Fira Sans / Fira Code from the UI/UX recommendation
may be adopted later only if bundled or loaded consistently; the redesign should
not depend on remote font loading.

### Color And Surface

Keep the existing semantic token strategy, but tune it for less visual noise:

- Primary accent: indigo-blue for selection, active nav, links, and primary
  commands.
- Success: green for healthy/approved/active states.
- Warning: amber for pending/degraded/retrying/paused states.
- Danger: red for failed/denied/destructive states.
- Running/info: blue/cyan for live execution, leasing, draining, and streaming.
- Disabled: neutral gray without relying only on strikethrough.

Light mode should use neutral page surfaces and visible borders. Dark mode
should be operational, not cinematic. Avoid dominant one-hue purple/blue themes;
indigo should be an accent, not the whole app.

### Token Contract

The redesign must be driven by shared tokens in `tokens.css` and `global.css`,
not ad hoc page-level colors or one-off spacing.

Required token groups:

- Page and layout: `--color-page`, `--color-page-grid`, shell/sidebar/topbar
  surface tokens.
- Surfaces: `--color-surface`, `--color-surface-muted`,
  `--color-surface-raised`.
- Borders: `--color-border`, `--color-border-strong`.
- Text: `--color-text`, `--color-text-muted`, `--color-text-soft`.
- Accent and status: `--color-accent`, `--color-accent-soft`,
  `--color-accent-quiet`, `--color-info`, `--color-success`,
  `--color-warning`, `--color-danger`, `--color-running`, plus matching soft
  status tokens.
- Shape and elevation: `--radius-sm`, `--radius-md`, `--shadow-panel`,
  `--shadow-popover`.
- Type: `--font-sans` and `--font-mono`.

Implementation rule: pages and page-scoped components may consume tokens, but
must not hard-code new brand colors, large shadows, custom gradients, or local
font scales unless the value is promoted back into the shared token contract.

### Shape, Density, And Motion

- Border radius: 6px for controls and badges, 8px for panels, never larger
  unless an existing Naive UI primitive requires it.
- Shadows: minimal. Use borders and background layers first; reserve popover
  shadow for drawers, menus, and overlays.
- Spacing: default page gap 16-18px, panel padding 14-16px, table cell padding
  9-11px.
- Hover states must not resize or shift layout.
- Motion duration: 150-220ms for normal transitions, up to 300ms only for drawer
  entrance/exit.
- Respect `prefers-reduced-motion`.

### Anti-Flamboyance Rules

These rules are hard constraints, not optional taste guidance:

- Do not use hero-scale typography, oversized metric cards, or large promotional
  page headers anywhere inside the console.
- Do not use decorative gradients, glowing borders, floating orbs, glassmorphism
  layers, bokeh backgrounds, or cinematic dark-mode treatments.
- Do not make dashboards look like presentation screens or command-center
  wallboards. Every page should remain usable for daily keyboard-and-mouse work.
- Do not use animation as decoration. Motion must only clarify navigation,
  loading, drawer state, or action feedback.
- Do not increase whitespace to create a luxury or landing-page feel. Preserve
  operator density and make hierarchy through labels, borders, grouping, and
  status semantics.
- Do not let any panel, chart, or table use font sizes that visually dominate
  page titles or primary workflow controls.
- A page fails visual review if the first viewport is dominated by decoration
  instead of controls, if a page title exceeds 24px, if metric values exceed
  24px without review approval, if cards consume unnecessary vertical space, or
  if charts read like a presentation screen rather than an operational tool.

## Information Architecture

The main navigation should group routes by the operator mental model, not by
implementation folder names.

| Group | Pages |
|---|---|
| Overview | Dashboard |
| Runtime | Agents, Package Registration, Deployments, Deployment Detail, Published Surfaces, Workers, Agent Instances, Capacity, Scheduled Runs, Batch Runs, Runs, Run Detail, Run Triage, Tasks |
| Observability | Events, Replay, Replay Comparison, Audit Logs, Artifacts, Datasets, Experiments, Quality Gate, Costs, Budgets, Evaluation Results, Feedback, Replay Jobs |
| Governance | Human Tasks, Policies, Model Gateways, Tools, Secrets, Catalog Items, Prompt Assets, Config Assets, Template Assets, asset details, asset diffs |
| Identity | Scopes, Operators, Operator Detail, Roles and Permissions, Machine Identities, Service Account Detail |
| Enterprise Ops | Backup and Restore, Webhook Subscriptions, Alert Rules, Incidents |
| Compatibility | Compatibility Explorer, request builder, migration report panels |
| Platform Settings | Platform Settings, Provider Status, Semantic Store Providers, Observability Exporters, Sandbox Policies, Container Pool Policies, Danger Zone, Settings |
| Public/Auth | Login |

Redirect-only routes should inherit the destination page design and should not
get separate visual treatment.

## Route Coverage Checklist

Every route in `apps/console/src/router/index.ts` must be assigned to a page
family and covered by the redesign. Redirect routes are verified by their target
routes.

| Path | Component / target | Page family | Pattern |
|---|---|---|---|
| `/` | `/dashboard` | Overview | Redirect |
| `/login` | `LoginPage` | Public/Auth | Auth form |
| `/dashboard` | `DashboardPage` | Overview | Runtime posture dashboard |
| `/agents` | `AgentsPage` | Runtime | List + actions |
| `/packages/register` | `PackageRegistrationPage` | Runtime | Registration workflow |
| `/deployments` | `DeploymentsPage` | Runtime | List + actions |
| `/deployments/:deploymentId` | `DeploymentDetailPage` | Runtime | Detail/workflow |
| `/compatibility` | `CompatibilityExplorerPage` | Compatibility | Explorer/workbench |
| `/published-surfaces` | `PublishedSurfacesPage` | Runtime | List/detail hybrid |
| `/published-surfaces/:surfaceId` | `PublishedSurfacesPage` | Runtime | Detail state |
| `/runtime/workers` | `WorkersPage` | Runtime | Capacity table |
| `/runtime/agent-instances` | `AgentInstancesPage` | Runtime | Instance table |
| `/runtime/capacity` | `CapacityPage` | Runtime | Capacity charts + tables |
| `/runtime/schedules` | `ScheduledRunsPage` | Runtime | Schedule table |
| `/runtime/batches` | `BatchRunsPage` | Runtime | Batch table |
| `/runs` | `RunsPage` | Runtime | Runs table |
| `/runs/:runId` | `RunDetailPage` | Runtime | Detail/evidence |
| `/runs/:runId/triage` | `RunTriagePage` | Runtime | Triage workbench |
| `/tasks` | `TasksPage` | Runtime | Task table |
| `/events` | `EventsPage` | Observability | Event stream |
| `/replay` | `ReplayPage` | Observability | Replay workflow |
| `/replay/compare` | `ReplayComparisonPage` | Observability | Comparison view |
| `/governance/human-tasks` | `HumanTasksPage` | Governance | Approval queue |
| `/governance/policies` | `PolicyWorkbenchPage` | Governance | Policy workbench |
| `/governance/api-keys` | `/identity/machine-identities` | Identity | Redirect |
| `/identity/operators` | `OperatorsPage` | Identity | Operator table |
| `/identity/operators/:operatorId` | `UserAccessDetailPage` | Identity | Detail/access |
| `/identity/scopes` | `IdentityScopePage` | Identity | Scope management |
| `/identity/tenants` | `/identity/scopes` | Identity | Redirect |
| `/identity/projects` | `/identity/scopes` | Identity | Redirect |
| `/identity/environments` | `/identity/scopes` | Identity | Redirect |
| `/identity/users` | `/identity/operators` | Identity | Redirect |
| `/identity/roles-permissions` | `RolePermissionMatrixPage` | Identity | Permission matrix |
| `/identity/roles` | `/identity/roles-permissions` | Identity | Redirect |
| `/identity/permissions` | `/identity/roles-permissions` | Identity | Redirect |
| `/identity/machine-identities` | `MachineIdentityPage` | Identity | Machine identity table |
| `/identity/service-accounts` | `/identity/machine-identities` | Identity | Redirect |
| `/identity/service-accounts/:serviceAccountId` | `ServiceAccountDetailPage` | Identity | Detail/access |
| `/governance/model-gateways` | `ModelGatewayWorkbenchPage` | Governance | Gateway workbench |
| `/governance/tools` | `ToolGatewayWorkbenchPage` | Governance | Gateway workbench |
| `/governance/secrets` | `SecretRotationPage` | Governance | Secret rotation |
| `/governance/catalog-items` | `CatalogPage` | Governance | Asset list |
| `/governance/catalog-items/:assetId` | `AssetDetailPage` | Governance | Asset detail |
| `/governance/catalog-items/:assetId/diff` | `AssetVersionDiffPage` | Governance | Asset diff |
| `/governance/prompt-assets` | `CatalogPage` | Governance | Asset list |
| `/governance/prompt-assets/:assetId` | `AssetDetailPage` | Governance | Asset detail |
| `/governance/prompt-assets/:assetId/diff` | `AssetVersionDiffPage` | Governance | Asset diff |
| `/governance/config-assets` | `CatalogPage` | Governance | Asset list |
| `/governance/config-assets/:assetId` | `AssetDetailPage` | Governance | Asset detail |
| `/governance/config-assets/:assetId/diff` | `AssetVersionDiffPage` | Governance | Asset diff |
| `/governance/template-assets` | `CatalogPage` | Governance | Asset list |
| `/governance/template-assets/:assetId` | `AssetDetailPage` | Governance | Asset detail |
| `/governance/template-assets/:assetId/diff` | `AssetVersionDiffPage` | Governance | Asset diff |
| `/observability/audit-logs` | `AdminCollectionPage` | Observability | Admin collection |
| `/observability/artifacts` | `AdminCollectionPage` | Observability | Admin collection |
| `/observability/evaluations` | `AdminCollectionPage` | Observability | Admin collection |
| `/observability/datasets` | `DatasetsPage` | Observability | Dataset table |
| `/observability/experiments` | `ExperimentsPage` | Observability | Experiment table |
| `/observability/quality-gate` | `QualityGatePage` | Observability | Quality workflow |
| `/observability/costs` | `CostsPage` | Observability | Cost dashboard/table |
| `/observability/budgets` | `BudgetsPage` | Observability | Budget dashboard/table |
| `/observability/replay-jobs` | `AdminCollectionPage` | Observability | Admin collection |
| `/observability/feedback` | `AdminCollectionPage` | Observability | Admin collection |
| `/ops/backup-plans` | `/ops/recovery` | Enterprise Ops | Redirect |
| `/ops/recovery` | `BackupRestorePage` | Enterprise Ops | Recovery workflow |
| `/published-surfaces/ingress-routes` | `/published-surfaces` | Runtime | Redirect |
| `/ops/restore-jobs` | `/ops/recovery` | Enterprise Ops | Redirect |
| `/ops/webhooks` | `AdminCollectionPage` | Enterprise Ops | Admin collection |
| `/ops/notifications` | `/ops/incidents` | Enterprise Ops | Redirect |
| `/ops/alerts` | `AdminCollectionPage` | Enterprise Ops | Admin collection |
| `/ops/incidents` | `IncidentTriagePage` | Enterprise Ops | Incident triage |
| `/settings/platform` | `PlatformSettingsPage` | Platform Settings | Settings form |
| `/settings/providers` | `ProviderStatusPage` | Platform Settings | Provider status |
| `/settings/danger-zone` | `DangerZonePage` | Platform Settings | Dangerous actions |
| `/settings/semantic-store` | `AdminCollectionPage` | Platform Settings | Admin collection |
| `/settings/observability-exporters` | `AdminCollectionPage` | Platform Settings | Admin collection |
| `/settings/sandbox-policies` | `AdminCollectionPage` | Platform Settings | Admin collection |
| `/settings/container-pool-policies` | `AdminCollectionPage` | Platform Settings | Admin collection |
| `/settings` | `SettingsPage` | Platform Settings | Settings index |

## Global Shell

### Sidebar

The sidebar remains the primary navigation for desktop and tablet:

- Width around 260-280px on desktop.
- Group headers stay compact and uppercase.
- Each nav item has a stable icon/glyph slot. Replace letter glyphs with a
  consistent icon set during implementation if an icon library is already
  accepted; otherwise keep text-safe glyphs but style them uniformly.
- Active item uses accent border/background and left-edge emphasis.
- Long groups must remain scrollable without hiding the brand.

For mobile:

- Collapse sidebar into a top navigation drawer or stacked compact nav region.
- Avoid horizontal overflow.
- Keep active group and current page visible after navigation.

### Topbar

The topbar is the operator context strip:

- Tenant, project, and environment selectors remain first-class controls.
- API mode must be visually prominent but not oversized.
- Global search may remain non-functional if it already is, but should be
  visually marked as search and not compete with primary actions.
- Live refresh should be a stateful toggle with clear paused/resumed labels.
- Theme and language controls should be icon-sized or compact text controls with
  accessible labels.
- Operator and logout controls stay at the far right on desktop and wrap cleanly
  on smaller widths.

### Content

All routed pages use the same page skeleton:

- `page-kicker`: work plane.
- `page-title`: route-specific title.
- `page-subtitle`: one sentence max, focused on the task.
- Header actions: primary workflow command, then secondary controls.
- Body: metrics, filters, tables, timelines, workbenches, drawers, and dialogs.

## Shared Component Patterns

### Panels

Panels should frame real tools or repeated content, not nest decorative cards.
Use:

- Header with title, optional status/controls.
- Body with form, chart, table, or summary.
- Footer only for form actions or pagination.

Do not put cards inside cards unless it is a modal/drawer or repeated item list.

### Tables

Tables are central to the product:

- Desktop: dense table with sticky header where useful, compact cells, clear
  row hover, and stable row action area.
- Mobile: either horizontal scroll or card-row layout, depending on data
  density. Existing `DataTable` card-row behavior should be normalized.
- Row actions should be grouped and never cause line-height jumps.
- IDs, versions, run IDs, trace IDs, and JSON previews use monospace.
- Empty, loading, error, and permission-denied states must be explicit.

### Forms And Drawers

- Use drawers for create/edit/detail flows where users need page context.
- Use dialogs for confirmations and destructive decisions.
- Required fields must be visible and labeled.
- Submit buttons show busy state, success/error state, and disabled state.
- JSON editors keep monospace 12-13px type and validation feedback close to the
  editor.

### Status And Risk

Status badges should be consistent across all pages:

- Include a small non-color cue such as dot, icon, or text label.
- Do not rely on color alone.
- Disabled/revoked/deleted should remain legible without looking like broken UI.
- Destructive actions require impact summaries, not only confirm text.

### Charts

Use ECharts consistently:

- Runtime trends: line or area chart with clear legends.
- Capacity/cost: time-series plus breakdown tables where needed.
- Forecast or comparison views: confidence/compare bands only when backed by
  data.
- Live or streaming visuals need pause/resume and reduced-motion handling.

## Page Coverage

### Dashboard

Purpose: current runtime posture at a glance.

Design:

- Compact metric row with 4-6 metrics.
- Runtime trend chart with clear axis/legend.
- Action summary, unhealthy deployments, and recent failures as scannable lists.
- No oversized hero cards.

### Runtime Pages

Covered pages:

- `AgentsPage`
- `PackageRegistrationPage`
- `DeploymentsPage`
- `DeploymentDetailPage`
- `PublishedSurfacesPage`
- `WorkersPage`
- `AgentInstancesPage`
- `CapacityPage`
- `ScheduledRunsPage`
- `BatchRunsPage`
- `RunsPage`
- `RunDetailPage`
- `RunTriagePage`
- `TasksPage`

Design:

- List pages use filter toolbar + table + row action drawer/detail route.
- Detail pages use a two-level layout: summary header, then tabs/sections for
  activity, config, attempts, events, artifacts, and actions.
- Workbench pages such as run triage use split layout: evidence left, decision
  or remediation controls right.
- Runtime operations must show scope, target, current status, action impact, and
  post-action feedback.

### Observability Pages

Covered pages:

- `EventsPage`
- `ReplayPage`
- `ReplayComparisonPage`
- `AdminCollectionPage` routes for Audit Logs, Artifacts, Evaluation Results,
  Feedback, Replay Jobs
- `DatasetsPage`
- `ExperimentsPage`
- `QualityGatePage`
- `CostsPage`
- `BudgetsPage`

Design:

- Events and audit logs prioritize time, actor/source, correlation ID, and
  severity.
- Replay flows use source run, candidate version, diff/compare, and result
  sections.
- Cost and budget pages use metric summaries, trend charts, and threshold
  tables.
- Quality/evaluation pages should show pass/fail state, dataset/experiment
  context, and evidence links.

### Governance Pages

Covered pages:

- `HumanTasksPage`
- `PolicyWorkbenchPage`
- `ModelGatewayWorkbenchPage`
- `ToolGatewayWorkbenchPage`
- `SecretRotationPage`
- `CatalogPage`
- `AssetDetailPage`
- `AssetVersionDiffPage`

Design:

- Governance pages should emphasize risk, approval state, policy effect, and
  auditability.
- Gateway workbenches should use test panels with request, route decision,
  policy result, and response sections.
- Asset pages use version timeline, metadata, current status, and diff views.
- Human task pages need queue, priority/status, assignee/context, and action
  confirmation.

### Identity Pages

Covered pages:

- `IdentityScopePage`
- `OperatorsPage`
- `UserAccessDetailPage`
- `RolePermissionMatrixPage`
- `MachineIdentityPage`
- `ServiceAccountDetailPage`
- `RolePermissionPage` if reintroduced or linked later

Design:

- Identity pages use matrix/table patterns with strong search and filters.
- Permission matrices need sticky row/column cues when dense.
- Detail pages show subject summary, scopes, roles, activity, and risk flags.
- Machine identities and service accounts highlight credential age, rotation
  state, scope, and revocation actions.

### Enterprise Ops Pages

Covered pages:

- `BackupRestorePage`
- `IncidentTriagePage`
- `AdminCollectionPage` routes for Webhook Subscriptions and Alert Rules

Design:

- Backup/restore shows plan health, last run, restore jobs, and destructive
  restore impact.
- Incidents use triage layout: severity, timeline, affected resources, linked
  runs/events, and response actions.
- Alerts and webhooks use standard admin table/drawer patterns with delivery or
  signal status emphasized.

### Compatibility Pages

Covered pages:

- `CompatibilityExplorerPage`
- `CompatibilityRequestBuilder`
- `MigrationReportPanel`
- `CompatibilityPage` if re-linked later

Design:

- Use a wizard-like but compact explorer: input/config, generated request,
  compatibility report, and next action.
- Keep generated code/request blocks readable with monospace and copy actions.
- Migration reports should separate blocking issues, warnings, and suggestions.

### Platform Settings Pages

Covered pages:

- `SettingsPage`
- `PlatformSettingsPage`
- `ProviderStatusPage`
- `DangerZonePage`
- `AdminCollectionPage` routes for Semantic Store Providers, Observability
  Exporters, Sandbox Policies, and Container Pool Policies

Design:

- Settings pages use sectioned forms with clear save/reset states.
- Provider status emphasizes health, latency/freshness, configuration coverage,
  and last checked time.
- Danger Zone uses high-friction confirmation, impact summaries, and no
  decorative red overload.
- Policy collection pages use admin table/drawer patterns with settings-specific
  field labels and validation.

### Admin Collection Pages

`AdminCollectionPage` is reused for many resource surfaces and should become a
first-class generic pattern:

- Standard page header from route props.
- Toolbar with search/filter, create action, and permission state.
- Data table with ID, name, status, scope, timestamps, metadata preview, and
  actions.
- Create drawer, detail drawer, edit JSON drawer, and delete confirmation share
  consistent spacing and action bars.
- Resource-specific field definitions stay compact and do not sprawl across the
  page.

Covered AdminCollection routes:

- Observability: Audit Logs, Artifacts, Evaluation Results, Feedback, Replay
  Jobs.
- Enterprise Ops: Webhook Subscriptions, Alert Rules.
- Platform Settings: Semantic Store Providers, Observability Exporters, Sandbox
  Policies, Container Pool Policies.

Because this component drives many pages, its redesign must be treated as a
template contract: fixing table density, drawer layout, JSON editing, mutation
feedback, permission-disabled actions, and destructive confirmation here counts
only if every route above remains readable with its real title, description,
resource path, and field set.

### Auth Page

Covered page:

- `LoginPage`

Design:

- Keep it simple and product-specific.
- No marketing hero.
- Show brand, runtime control plane subtitle, auth form, API mode/environment
  hint, and error state.
- Form controls must match console tokens.

## Interaction Requirements

- Every clickable element must have pointer cursor, visible hover, and
  focus-visible state.
- Keyboard users can navigate tables, buttons, drawer controls, dialogs, and
  primary route actions.
- Loading states appear for operations over 300ms.
- Submit and mutation buttons show busy state and prevent duplicate action.
- Error states show a concise summary plus technical details where useful.
- Empty states state what is missing and provide the next action when allowed.
- Offline/API-mock mode must be visibly distinct without blocking page layout.
- Mutation flows must preserve context: after create, edit, enable/disable, or
  delete, the user should see what changed without losing the current scope,
  filters, or route.

## Localization And Content Requirements

The console supports Chinese and English, so layout must be validated in both
`zh-CN` and `en-US`.

- Navigation labels, page titles, table headers, buttons, badges, drawer titles,
  and dialog action rows must not overlap at either locale.
- Long English labels must wrap or truncate intentionally without hiding the
  resource identity or action meaning.
- Chinese labels should not force extra vertical rhythm or oversized controls.
- Table columns may use responsive hiding, wrapping, or horizontal scroll, but
  the primary identifier, status, and row actions must remain discoverable.
- Avoid copy that explains the UI itself. On-screen text should name the
  workflow, state, resource, or action.

## Responsive Requirements

Test and design for:

- 375px mobile
- 768px tablet
- 1024px laptop
- 1440px desktop

Rules:

- No horizontal page scroll outside intentional table scroll regions.
- Tables either scroll inside `.table-wrap` or convert to card rows.
- Header actions wrap below title on narrow screens.
- Topbar controls wrap without overlapping.
- Drawers become near-full-width on mobile.

## Accessibility Requirements

- Preserve semantic headings and table scopes.
- All form inputs have labels.
- Icon-only controls must have accessible names.
- Status and risk cannot be communicated by color alone.
- Focus rings must be visible in light and dark mode.
- Contrast must target WCAG AA minimum; prefer stronger contrast for tables.
- Reduced motion users should not receive page entrance animation.

## Implementation Plan Shape

The implementation plan should be split by shared foundation first, then page
families:

1. Tokens and global CSS: typography, spacing, color tuning, focus, buttons,
   inputs, panels, tables, responsive rules.
2. Shell: sidebar, topbar, navigation grouping, mobile behavior, scope/API mode
   controls.
3. Shared components: `StatusBadge`, `DataTable`, `MetricCard`, `ApiState`,
   drawers, confirmations, timeline, charts, JSON editor.
4. Page family pass: Dashboard, Runtime, Observability, Governance, Identity,
   Enterprise Ops, Compatibility, Settings, Admin Collection, Auth.
5. Touched-area frontend bug fixes: fix UI defects discovered while applying the
   redesign, and record each fix with its verification method.
6. Visual and regression verification: unit/build checks plus Playwright
   responsive screenshots or targeted browser tests for representative routes.

## Verification

Before calling implementation complete:

- `npm run build` in `apps/console`.
- `npm run test:unit` in `apps/console`.
- Every non-redirect route in the Route Coverage Checklist must have at least a
  smoke-level render check, either automated or manually recorded during the
  implementation closeout.
- Representative Playwright screenshots or browser tests must cover at minimum:
  Dashboard, one Runtime list page, one Runtime detail/workbench page, one
  Observability page, one Governance workbench, one Identity matrix/detail page,
  one AdminCollection route, one Settings/Danger page, and Login.
- Manual or screenshot inspection for light/dark mode at 375px, 768px, 1024px,
  and 1440px.
- Manual or screenshot inspection for `zh-CN` and `en-US` on at least the shell,
  one dense table, one drawer form, and one dialog.
- Confirm no console page uses oversized hero typography, decorative backgrounds,
  nested cards, or layout-shifting hover states.
- Run an anti-flamboyance review across all page families: typography, spacing,
  color, motion, charts, and cards must read as an operator workbench, not a
  promotional site, luxury dashboard, or command-center demo.
- Include a bug-fix note in the closeout summary for every frontend defect fixed
  during the redesign, including the affected route/component and verification
  used.

## Implementation Decisions

- Do not add a new icon package in the design-doc phase. During implementation,
  first check whether the existing dependency set already provides suitable
  icons. If not, keep the current glyph slot but make sizing, accessible labels,
  and visual treatment consistent.
- Treat global search as a visual shell control unless an existing search API is
  already available. Do not invent backend search behavior as part of the UI
  redesign.
- Keep the existing GSAP page transition only if reduced-motion handling remains
  correct and the animation stays below 220ms. Otherwise replace it with a
  CSS-only transition or remove it.
