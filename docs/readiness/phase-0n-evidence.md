# Phase 0N Evidence Checklist

Phase 0N covers the Scheduled and Batch Runtime workflow. The backend and
Console implementation are in place, local tests and direct browser proof
exist, and the remaining closeout gap is hosted CI/browser evidence on the
managed Chromium path.

## What Is Already Proven

- Local backend workflow coverage:
  `uv run pytest -q tests/api/test_scheduled_batch_runtime.py`
- Local backend type-check coverage:
  `uv run mypy apps/server/dimoo_run/api/admin/schedules.py apps/server/dimoo_run/api/admin/batches.py apps/server/dimoo_run/runtime/scheduled_runs.py tests/api/test_scheduled_batch_runtime.py`
- Local Console contract/build proof:
  `npm run test`
  `npm run build:e2e`
- Local dedicated browser proof:
  `npm run test:e2e:0n`
  `npx playwright test tests/e2e/scheduled-batch.spec.ts --project=chrome --workers=1 --output test-results-0n-direct`

These checks prove:

- schedule validation, pause/resume/manual trigger, and due-fire policy logic
  are covered locally;
- batch partial-failure, retry, cancel, and completion summaries are covered
  locally; and
- both the direct spec path and dedicated 0N wrapper are wired into the repo.

## Hosted CI Gap

The remaining closeout evidence for 0N is a successful hosted CI run that
publishes:

- `console-playwright-0n-report`
- `console-playwright-evidence-index`

Until a current hosted run publishes those artifacts from the same worktree,
0N stays conservative at `partial`.

## Hosted CI Backfill Template

Fill this section when a hosted run is available:

- Hosted run id: `<run-id>`
- Branch/ref: `<branch-or-tag>`
- Date checked: `<yyyy-mm-dd>`
- Published artifacts:
  - `console-playwright-0n-report`
  - `console-playwright-evidence-index`
- Outcome summary:
  - `<pass-or-fail summary>`
  - `<key browser workflow evidence>`
  - `<remaining follow-up if not fully closed>`

## Latest Local Result

Date checked: 2026-06-14

Status: `local-browser-proof-pass-hosted-pending`

Observed outcome:

- backend scheduled/batch workflow tests pass locally;
- targeted mypy coverage for the 0N implementation passes locally;
- Console contract/build proof passes locally; and
- `npm run test:e2e:0n` passes locally with 2 browser checks covering schedule
  preview, invalid timezone validation, pause/resume/manual trigger, batch
  creation, partial-failure drilldown, and queued-item cancellation.
- The dedicated local browser output path is
  `apps/console/test-results-0n`.

## Local Operator Notes

- Working directory for Console/browser commands: `apps/console`
- Hosted artifact names to cite after CI passes:
  `console-playwright-0n-report` and `console-playwright-evidence-index`
- The direct spec output path is `apps/console/test-results-0n-direct`
- Latest local browser command:
  `npm run test:e2e:0n`

## Scorecard Rows To Update

When hosted CI proof is available, update these rows in
`docs/readiness/scorecard.md` with the same hosted run id and artifact names:

- `Scheduled Run and Batch Run are first-class runtime task shapes with validation, state machines, cancellation, replay, audit, and browser coverage.`
- `Browser E2E tests cover core Console workflows.`
- `Milestone C: External GA`

## Closure Verdict

0N can move from `partial` to `complete` when all of the following are true:

1. The bounded 0N backend workflow suites stay green.
2. The dedicated `npm run test:e2e:0n` browser workflow stays green locally.
3. A current hosted CI run publishes `console-playwright-0n-report`.
4. The hosted run is traceable through `console-playwright-evidence-index`.
