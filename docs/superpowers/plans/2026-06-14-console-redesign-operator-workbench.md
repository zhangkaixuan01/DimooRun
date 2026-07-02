# Console Operator Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the DimooRun Console redesign described in `docs/superpowers/specs/2026-06-14-console-redesign-design.md` across the full routed frontend.

**Architecture:** Start with the shared visual contract so route pages inherit the workbench design without page-by-page reinvention. Then update shell and reusable components, apply page-family fixes where shared primitives are insufficient, and finish with route-level smoke and visual verification.

**Tech Stack:** Vue 3, Vite, TypeScript, Pinia, Vue Router, Naive UI, ECharts, Vitest, Playwright.

---

## File Structure

- Modify `apps/console/src/styles/tokens.css`: shared light/dark token contract for page, surface, text, accent, status, radius, shadow, and fonts.
- Modify `apps/console/src/styles/global.css`: global typography, page skeleton, panel, table, button, input, responsive, focus, and reduced-motion rules.
- Modify `apps/console/src/layouts/AppShell.vue`: operator workbench shell, navigation grouping, compact sidebar, topbar controls, reduced-motion-safe route transition, responsive behavior.
- Modify `apps/console/src/components/StatusBadge.vue`: consistent status sizing, non-color cue, disabled styling.
- Modify `apps/console/src/components/DataTable.vue`: dense desktop table, mobile card-row behavior, row focus/selection fixes, token usage.
- Modify `apps/console/src/components/MetricCard.vue`: restrained metric typography and surface treatment.
- Modify `apps/console/src/components/AppDrawer.vue`, `DangerConfirmDialog.vue`, `ConfirmImpactDialog.vue`, `ApiState.vue`, `InlineApiError.vue`, `JsonSchemaEditor.vue`, `RuntimeTrendChart.vue`, `RunCostBreakdown.vue`, `EventTimeline.vue` as needed for spacing, focus, loading, and no-flamboyance consistency.
- Modify representative page files only where shared primitives cannot satisfy the spec: Dashboard, runtime detail/workbench pages, AdminCollectionPage, LoginPage, Settings/Danger, Identity matrix/detail, Governance workbenches, Compatibility explorer.
- Add or modify tests under `apps/console/tests/unit`, `apps/console/tests/e2e`, and `apps/console/tests/fixtures` for route smoke, shell interaction, responsive/i18n checks, and bug fixes found during implementation.

## Task 1: Test The Design Contract

**Files:**
- Modify: `apps/console/tests/e2e/workflow-shell.spec.ts`
- Modify: `apps/console/tests/e2e/responsive-snapshots.spec.ts`
- Optional create: `apps/console/tests/e2e/route-coverage.spec.ts`

- [ ] **Step 1: Add failing route/design smoke tests**

Add tests that verify every non-redirect route renders an app page, shell controls remain usable, and representative pages avoid oversized typography.

```ts
test("all non-redirect console routes render without horizontal page overflow", async ({ page }) => {
  for (const path of NON_REDIRECT_ROUTES) {
    await page.goto(path);
    await expect(page.locator(".page, form").first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(overflow, path).toBe(false);
  }
});

test("workbench typography stays restrained", async ({ page }) => {
  await page.goto("/dashboard");
  const titleSize = await page.locator(".page-title").first().evaluate((node) => Number.parseFloat(getComputedStyle(node).fontSize));
  expect(titleSize).toBeLessThanOrEqual(24);
});
```

- [ ] **Step 2: Run tests to verify current failures**

Run: `npm run test:e2e -- --grep "all non-redirect|workbench typography"` from `apps/console` if supported, or `npx playwright test tests/e2e/route-coverage.spec.ts --project=chrome`.

Expected: at least one failure from existing overflow, typography, route coverage, or missing test file behavior.

- [ ] **Step 3: Keep tests focused**

If the full all-route test is too slow, keep it as a smoke test with basic render/overflow checks only. Move visual detail checks to representative routes.

## Task 2: Tokens And Global CSS

**Files:**
- Modify: `apps/console/src/styles/tokens.css`
- Modify: `apps/console/src/styles/global.css`

- [ ] **Step 1: Write token/global CSS tests or route assertions first**

Use the e2e tests from Task 1 to assert page title size, no page overflow, button focus, and table containment.

- [ ] **Step 2: Implement token contract**

Tune the existing token groups without introducing page-local colors:

```css
:root,
[data-theme="light"] {
  --font-sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  --radius-sm: 6px;
  --radius-md: 8px;
  --shadow-panel: 0 1px 2px oklch(20% 0.035 257 / 5%);
  --shadow-popover: 0 18px 44px oklch(20% 0.035 257 / 14%);
}
```

- [ ] **Step 3: Implement global component contract**

Set page title, panels, buttons, inputs, table, toolbar, responsive, and reduced-motion rules so all pages inherit restrained density.

- [ ] **Step 4: Verify**

Run: `npm run build` and targeted e2e smoke after Task 3 shell work.

## Task 3: App Shell

**Files:**
- Modify: `apps/console/src/layouts/AppShell.vue`
- Test: `apps/console/tests/e2e/workflow-shell.spec.ts`

- [ ] **Step 1: Add/extend shell tests first**

Assert scope controls wrap, theme/locale buttons remain accessible, and active navigation is visible.

- [ ] **Step 2: Refactor shell markup and navigation**

Keep current route groups but tune sidebar, topbar, brand, nav glyph, search, refresh, theme, locale, operator, and logout controls.

- [ ] **Step 3: Replace unsafe page animation**

Keep GSAP only if `prefers-reduced-motion` is respected and animation remains below 220ms; otherwise skip animation for reduced-motion users.

- [ ] **Step 4: Verify**

Run: `npm run test:unit` and targeted Playwright shell tests.

## Task 4: Core Components

**Files:**
- Modify: `apps/console/src/components/StatusBadge.vue`
- Modify: `apps/console/src/components/DataTable.vue`
- Modify: `apps/console/src/components/MetricCard.vue`
- Modify: `apps/console/src/components/ApiState.vue`
- Modify: `apps/console/src/components/AppDrawer.vue`
- Modify: `apps/console/src/components/DangerConfirmDialog.vue`
- Modify: `apps/console/src/components/ConfirmImpactDialog.vue`
- Modify: `apps/console/src/components/InlineApiError.vue`
- Modify: `apps/console/src/components/JsonSchemaEditor.vue`
- Modify: chart/timeline components as needed.

- [ ] **Step 1: Add focused component or route tests first**

Use existing route pages to test selected row, drawer open/close, danger dialog focus, table mobile behavior, and status badge visibility.

- [ ] **Step 2: Implement core visual and interaction fixes**

Apply token-based styling, compact typography, stable hover states, disabled states, explicit loading/error/empty states, and accessible labels.

- [ ] **Step 3: Record touched-area bug fixes**

For each actual frontend bug found, add a note to the implementation closeout and add the nearest practical verification.

- [ ] **Step 4: Verify**

Run: `npm run test:unit`; run representative e2e specs that cover these components.

## Task 5: Page-Family Pass

**Files:**
- Modify page files under `apps/console/src/pages/**` as needed.
- Test: existing e2e specs under `apps/console/tests/e2e/**`.

- [ ] **Step 1: Runtime pages**

Normalize list/detail/workbench structure for Agents, Packages, Deployments, Published Surfaces, Workers, Agent Instances, Capacity, Schedules, Batches, Runs, Run Detail, Run Triage, and Tasks.

- [ ] **Step 2: Observability pages**

Normalize Events, Replay, Replay Comparison, Audit Logs, Artifacts, Datasets, Experiments, Quality Gate, Costs, Budgets, Evaluations, Feedback, and Replay Jobs.

- [ ] **Step 3: Governance pages**

Normalize Human Tasks, Policy Workbench, Model Gateway, Tool Gateway, Secrets, Catalog/Prompt/Config/Template assets, asset details, and diffs.

- [ ] **Step 4: Identity pages**

Normalize Scopes, Operators, Operator Detail, Role Permission Matrix, Machine Identities, and Service Account Detail.

- [ ] **Step 5: Enterprise Ops, Compatibility, Settings, Auth**

Normalize Backup/Restore, Incidents, Webhooks, Alerts, Compatibility Explorer, Settings, Provider Status, Danger Zone, AdminCollection settings routes, and Login.

- [ ] **Step 6: Verify each page family**

Run the existing focused e2e command for each family where available.

## Task 6: Full Verification And Closeout

**Files:**
- Modify or create closeout notes only if needed.

- [ ] **Step 1: Build**

Run from `apps/console`: `npm run build`.

- [ ] **Step 2: Unit tests**

Run from `apps/console`: `npm run test:unit`.

- [ ] **Step 3: E2E representative route set**

Run representative Playwright tests covering shell, dashboard, runtime, observability, governance, identity, admin collection, settings/danger, login, responsive, and i18n.

- [ ] **Step 4: Full route smoke**

Run the route coverage smoke for every non-redirect route.

- [ ] **Step 5: Anti-flamboyance audit**

Inspect rendered pages or screenshots for typography, spacing, color, motion, charts, and cards. Fail the closeout if any page reads like a promotional site, luxury dashboard, or command-center demo.

- [ ] **Step 6: Report bug fixes**

List every frontend defect fixed during implementation with route/component and verification.

## Self-Review

- Spec coverage: tasks cover tokens/global CSS, shell, shared components, all page families, all route smoke, localization, responsive, accessibility, anti-flamboyance, and frontend bug-fix policy.
- Placeholder scan: this plan contains no TBD/TODO placeholders.
- Type consistency: tests and implementation reference existing Vue/Vite/Playwright structure and current route/component names.
