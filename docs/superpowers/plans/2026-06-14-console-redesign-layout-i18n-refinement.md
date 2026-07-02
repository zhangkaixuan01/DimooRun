# Console Redesign Layout And I18n Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the console redesign so layout, forms, and Chinese coverage improve beyond visual skin changes.

**Architecture:** Apply shared layout and form typography fixes in global CSS first, then update high-traffic workflow pages that still hardcode English. Add tests that catch bold form controls and visible untranslated English in Chinese mode.

**Tech Stack:** Vue 3, Vite, Vitest, Playwright, CSS tokens.

---

### Task 1: Form Typography Baseline

**Files:**
- Modify: `apps/console/src/styles/global.css`
- Test: `apps/console/tests/e2e/route-coverage.spec.ts`

- [x] Set `input`, `select`, `textarea`, `.input`, `.select`, and `.textarea` to `font-weight: 400` so controls never inherit bold labels.
- [x] Keep labels readable with restrained `font-weight: 600`, not 700/800.
- [x] Add e2e assertions for representative form controls in Chinese mode.

### Task 2: Layout Density And Reading Order

**Files:**
- Modify: `apps/console/src/styles/global.css`
- Modify: `apps/console/src/pages/dashboard/DashboardPage.vue`
- Modify: selected workflow pages that use two-column form/list/detail layouts.

- [x] Add shared layout helpers for primary/secondary work areas.
- [x] Reduce card-like repetition and improve scan order on the dashboard.
- [x] Make list/detail/form grids collapse earlier and preserve usable reading order.

### Task 3: Chinese Coverage

**Files:**
- Modify: `apps/console/src/i18n/messages.ts`
- Modify: `apps/console/src/pages/catalog/*.vue`
- Modify: `apps/console/src/pages/compatibility/*.vue`
- Modify: `apps/console/src/pages/runtime/*.vue`
- Modify: `apps/console/src/pages/settings/*.vue`

- [x] Replace visible hardcoded English headings, labels, buttons, empty states, and common placeholders with `t(...)`.
- [x] Keep protocol values and API enum values unchanged where they are data values.
- [x] Add route coverage checks for untranslated visible English in Chinese locale on representative pages.

### Task 4: Verification

**Files:**
- Test: `apps/console/tests/e2e/route-coverage.spec.ts`

- [x] Run `npm run test:unit`.
- [x] Run `npm run build`.
- [x] Run `npm run test:e2e`.
- [x] Inspect representative screenshots after the layout pass.
