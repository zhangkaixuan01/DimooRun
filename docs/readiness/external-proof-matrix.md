# Outstanding External Proof Matrix

This matrix is the single index of production-readiness evidence that still
depends on external hosted execution or a clean environment outside the current
repository-local proof.

## How To Use

When a hosted CI, integration, or release run succeeds, update the linked
backfill document first, then update `docs/readiness/scorecard.md` using the
same run id and artifact names.

## Open External Proof Items

| Proof area | Workflow / command | Required artifact(s) | Backfill document | Required scorecard row updates | Current state |
|---|---|---|---|---|---|
| Hosted browser proof for Phase 0M | `.github/workflows/ci.yml` / `npm run test:e2e:0m` | `console-playwright-0m-report`, `console-playwright-evidence-index` | `docs/readiness/phase-0m-evidence.md` | Phase 0M row; browser E2E DoD; Milestone C workflow evidence | Pending hosted managed-browser pass |
| Hosted browser proof for Phase 0N | `.github/workflows/ci.yml` / `npm run test:e2e:0n` | `console-playwright-0n-report`, `console-playwright-evidence-index` | `docs/readiness/phase-0n-evidence.md` | Phase 0N row; browser E2E DoD; Milestone C workflow evidence | Pending hosted managed-browser pass |
| Hosted browser proof for Phase 0O | `.github/workflows/ci.yml` / `npm run test:e2e:0o` | `console-playwright-0o-report`, `console-playwright-evidence-index` | `docs/readiness/phase-0o-evidence.md` | Phase 0O row; browser E2E DoD; Milestone C workflow evidence | Pending hosted managed-browser pass |
| Hosted Compose smoke proof | `.github/workflows/integration.yml` / `uv run python scripts/compose_runtime_smoke.py` | `compose-runtime-smoke`, `compose-runtime-smoke-index` | `docs/readiness/compose-smoke-report.md` | Phase 1 row; Phase 10 row; Compose smoke DoD; Milestone C exit criterion | Pending Docker-enabled hosted success |
| Hosted KinD smoke proof | `.github/workflows/integration.yml` / `uv run python scripts/helm_smoke.py --cluster-runtime kind` | `kind-smoke`, `kind-smoke-index` | `docs/readiness/kind-smoke-report.md` | Phase 10 row; Kubernetes smoke DoD; Milestone C exit criterion | Pending ephemeral-cluster hosted success |
| Hosted release proof | `.github/workflows/release.yml` / tagged release run | `release-evidence-index`, `release-sbom`, published packages, provenance outputs | `docs/readiness/release-proof-report.md` | Phase 11 row; release DoD; Milestone C release coherence | Pending successful tagged hosted release |
| Hosted all-phases CI proof | `.github/workflows/ci.yml` plus `.github/workflows/integration.yml` | current successful run ids and linked browser / smoke artifacts | `docs/readiness/all-phases-ci-proof.md` | “All phases have passing tests in CI” DoD; Milestone A/B/C confidence | Pending current worktree green hosted runs |

## Completion Transaction

Treat each external proof item as one update transaction:

1. Capture the hosted run id, date, ref, and artifact names.
2. Update the listed backfill document with the exact hosted result.
3. Update every scorecard row named in `Required scorecard row updates`.
4. Update `docs/readiness/scorecard.md` `## Hosted Evidence Backfill` so the
   row no longer says `Pending`.
5. If the proof changes milestone wording, keep the maturity guardrail text
   conservative unless every linked row is directly proven.

## Backfill Rule

Do not mark an item complete from wiring alone. Completion requires:

1. A concrete hosted or clean-environment run identifier.
2. The named artifact(s) listed above.
3. A linked backfill document updated with date, branch/ref, and outcome.
4. Matching updates in `docs/readiness/scorecard.md`.
