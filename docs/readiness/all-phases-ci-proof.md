# All-Phases CI Proof

This document is the canonical backfill template for the cross-workflow hosted
CI evidence required to support the scorecard claim that all phases have
passing tests in CI.

## Workflow Contract

- Primary workflows:
  - `.github/workflows/ci.yml`
  - `.github/workflows/integration.yml`
- Both workflows are now manually triggerable through `workflow_dispatch`, so
  hosted proof can be refreshed for the current branch without requiring a new
  dummy push.
- Repository helper:
  - `uv run python scripts/hosted_proof_status.py`
  - This reports the current SHA, dirty worktree state, manual-trigger support,
    and the latest `ci.yml` / `integration.yml` / `release.yml` runs.
- Required hosted evidence:
  - one current successful `ci.yml` run for the same worktree/ref
  - one current successful `integration.yml` run for the same worktree/ref
  - linked artifact indexes for browser and environment smoke evidence
- Required artifact names referenced by the current scorecard:
  - `console-playwright-evidence-index`
  - `compose-runtime-smoke-index`
  - `kind-smoke-index`

## Current State

Status: pending current same-worktree hosted CI proof.

The repository contains local phase proof, stable artifact names, and workflow
wiring, but there is not yet one recorded pair of current hosted `ci.yml` and
`integration.yml` runs that closes the scorecard claim from the same ref.

Latest hosted observation:

- `integration.yml` run `27475315682` succeeded on `2026-06-13` for
  `2f1fbc1d4deacbb514b3dfbf90ad1662086fc6e2`.
- Matching `ci.yml` run `27475315693` failed on `2026-06-13` for the same SHA.
- The failing job was `Console`, and the blocking test was
  `apps/console/tests/e2e/policy-approval.spec.ts`, which expected
  `decision: deny -> deny` while the page actually rendered
  `decision: - -> deny`.
- The current worktree now fixes that local browser assertion mismatch, and a
  full local rerun of `apps/console` `npm run test:e2e` passes with 71 browser
  tests on `2026-06-14`.
- The current worktree also hardens the axe-based accessibility tests by
  scoping them to the relevant region and marking them slow for CI-parallel
  execution.
- `uv run python scripts/hosted_proof_status.py` now reports the current
  closeout blockers explicitly as `worktree_dirty` and
  `ci_latest_run_not_success`.
- The same local verification window on `2026-06-14` also reconfirmed the
  remaining Milestone C browser gaps for the current worktree:
  `npm run test:e2e:0m`, `npm run test:e2e:0n`, and `npm run test:e2e:0o`
  all pass locally, while hosted managed-browser artifacts for those phases are
  still pending.
- A fresh hosted CI rerun is still required before this proof can be closed.

## Hosted CI Backfill Template

- Date:
- Git ref / branch:
- Commit SHA:
- `ci.yml` run id:
- `integration.yml` run id:
- `console-playwright-evidence-index` artifact:
- `compose-runtime-smoke-index` artifact:
- `kind-smoke-index` artifact:
- Covered phase/browser notes:
- Covered compose/kind notes:
- Notes:

## Scorecard Rows To Update

When the hosted runs succeed for the same worktree/ref, update these rows in
`docs/readiness/scorecard.md` with the exact run ids and artifact names:

- `All phases have passing tests in CI.`
- `Milestone A: Internal Alpha`
- `Milestone B: Production Beta`
- `Milestone C: External GA`

## Closure Verdict

Do not mark this complete from local tests or workflow wiring alone. Closure
requires current successful hosted `ci.yml` and `integration.yml` runs from the
same ref, with the named evidence-index artifacts recorded here.
