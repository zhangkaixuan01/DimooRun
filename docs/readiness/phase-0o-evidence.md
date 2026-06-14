# Phase 0O Evidence Checklist

Phase 0O covers the Catalog and Versioned Asset Lifecycle workflow. The backend
and Console implementation are in place, local tests and browser proof exist,
and the remaining closeout gap is hosted CI/browser evidence on the managed
Chromium path.

## What Is Already Proven

- Local backend workflow coverage:
  `uv run pytest -q tests/api/test_catalog_asset_lifecycle.py`
- Local backend lint/type coverage:
  `uv run ruff check apps/server/dimoo_run/catalog/asset_lifecycle.py apps/server/dimoo_run/api/admin/catalog.py apps/server/dimoo_run/api/admin/assets.py tests/api/test_catalog_asset_lifecycle.py apps/server/dimoo_run/api/router.py`
  `uv run mypy apps/server/dimoo_run/catalog/asset_lifecycle.py apps/server/dimoo_run/api/admin/catalog.py apps/server/dimoo_run/api/admin/assets.py tests/api/test_catalog_asset_lifecycle.py`
- Local Console contract/build/browser proof:
  `npm run test`
  `npm run build`
  `npm run build:e2e`
  `npm run test:e2e:0o`
- Local manual/browser proof helper:
  `node apps/console/scripts/catalog-assets-browser-proof.mjs`

These checks prove:

- catalog, asset detail, diff, validate, approve, publish, deprecate, archive,
  and rollback flows are covered locally;
- the dedicated 0O browser wrapper is wired into the repository contract; and
- the manual proof helper still maps the workflow to explicit local steps.

## Hosted CI Gap

The remaining closeout evidence for 0O is a successful hosted CI run that
publishes:

- `console-playwright-0o-report`
- `console-playwright-evidence-index`

Until a current hosted run publishes those artifacts from the same worktree,
0O stays conservative at `partial`.

## Hosted CI Backfill Template

Fill this section when a hosted run is available:

- Hosted run id: `<run-id>`
- Branch/ref: `<branch-or-tag>`
- Date checked: `<yyyy-mm-dd>`
- Published artifacts:
  - `console-playwright-0o-report`
  - `console-playwright-evidence-index`
- Outcome summary:
  - `<pass-or-fail summary>`
  - `<key browser workflow evidence>`
  - `<remaining follow-up if not fully closed>`

## Latest Local Result

Date checked: 2026-06-14

Status: `local-browser-proof-pass-hosted-pending`

Observed outcome:

- backend asset lifecycle tests pass locally;
- targeted lint/type gates for the 0O implementation pass locally;
- Console contract/build proof passes locally; and
- `npm run test:e2e:0o` passes locally through the manual-browser proof helper
  and emits `apps/console/playwright-report-0o/index.html`.
- The local proof bundle currently includes 5 screenshots under
  `apps/console/test-results-0o`:
  create prompt asset, validation failure, prompt diff, lifecycle actions, and
  catalog item shapes.

## Local Operator Notes

- Working directory for Console/browser commands: `apps/console`
- Hosted artifact names to cite after CI passes:
  `console-playwright-0o-report` and `console-playwright-evidence-index`
- Manual helper path:
  `apps/console/scripts/catalog-assets-browser-proof.mjs`
- Latest local browser command:
  `npm run test:e2e:0o`

## Scorecard Rows To Update

When hosted CI proof is available, update these rows in
`docs/readiness/scorecard.md` with the same hosted run id and artifact names:

- `Catalog, Prompt, Config, and Template assets have version lifecycle, validation, dependency visibility, approval, rollback, and used-by impact.`
- `Browser E2E tests cover core Console workflows.`
- `Milestone C: External GA`

## Closure Verdict

0O can move from `partial` to `complete` when all of the following are true:

1. The bounded 0O backend workflow suites stay green.
2. The dedicated `npm run test:e2e:0o` browser workflow stays green locally.
3. A current hosted CI run publishes `console-playwright-0o-report`.
4. The hosted run is traceable through `console-playwright-evidence-index`.
