# Phase 0M Evidence Checklist

Phase 0M covers the Cost, Budget, and Usage Attribution workflow. The backend
and Console implementation are in place, local tests and browser proof exist,
and the remaining closeout gap is hosted CI/browser evidence on the managed
Chromium path.

## What Is Already Proven

- Local backend workflow coverage:
  `uv run pytest -q tests/api/test_cost_usage_workflows.py`
- Local repository-wide regression proof that still includes 0M:
  `uv run pytest -q`
- Local backend lint/type proof:
  `uv run ruff check apps tests packages/sdk-python scripts migrations`
  `uv run mypy apps/server tests scripts`
- Local Console contract, build, and dedicated browser proof:
  `npm run test`
  `npm run build:e2e`
  `npm run test:e2e:0m`

These checks prove:

- cost summary, anomaly, and saved-view APIs work locally;
- persisted budget policy preview, enforcement, and notification delivery
  attempts are covered by backend regressions;
- the Console cost explorer and budgets workflow render the expected local
  interactions; and
- the dedicated 0M browser wrapper path is wired into the repository contract.

## Hosted CI Gap

The remaining closeout evidence for 0M is a successful hosted CI run that
publishes:

- `console-playwright-0m-report`
- `console-playwright-evidence-index`

Until a current hosted run publishes those artifacts from the same worktree,
0M stays conservative at `partial`.

## Hosted CI Backfill Template

Fill this section when a hosted run is available:

- Hosted run id: `<run-id>`
- Branch/ref: `<branch-or-tag>`
- Date checked: `<yyyy-mm-dd>`
- Published artifacts:
  - `console-playwright-0m-report`
  - `console-playwright-evidence-index`
- Outcome summary:
  - `<pass-or-fail summary>`
  - `<key browser workflow evidence>`
  - `<remaining follow-up if not fully closed>`

## Latest Local Result

Date checked: 2026-06-14

Status: `local-browser-proof-pass-hosted-pending`

Observed outcome:

- backend 0M workflow tests pass locally;
- global backend lint/type gates pass locally after the 0M changes;
- Console contract/build proof passes locally; and
- `npm run test:e2e:0m` passes locally with 5 browser checks covering cost
  breakdown, anomaly drilldown, saved views, budget impact preview, and blocked
  budget-policy updates.
- The dedicated local browser output path is
  `apps/console/test-results-0m`.

## Local Operator Notes

- Working directory for Console/browser commands: `apps/console`
- Hosted artifact names to cite after CI passes:
  `console-playwright-0m-report` and `console-playwright-evidence-index`
- Local browser fallback can still use
  `DIMOORUN_PLAYWRIGHT_CHROME` in `apps/console/.env.e2e.local`
- Latest local browser command:
  `npm run test:e2e:0m`

## Scorecard Rows To Update

When hosted CI proof is available, update these rows in
`docs/readiness/scorecard.md` with the same hosted run id and artifact names:

- `Cost and budget workflows explain usage by agent, deployment, run, provider, tenant, project, and environment, with anomaly and budget guardrails.`
- `Browser E2E tests cover core Console workflows.`
- `Milestone C: External GA`

## Closure Verdict

0M can move from `partial` to `complete` when all of the following are true:

1. The bounded 0M backend workflow suites stay green.
2. The dedicated `npm run test:e2e:0m` browser workflow stays green locally.
3. A current hosted CI run publishes `console-playwright-0m-report`.
4. The hosted run is traceable through `console-playwright-evidence-index`.
