# Evidence Gallery

This page indexes generated product evidence. It is not a marketing gallery; it
records what was captured, by which command, and which claim it supports.

| Evidence | Command | Claim Supported | Current Status |
|---|---|---|---|
| Dashboard | `cd apps/console && npx playwright test tests/e2e/responsive-snapshots.spec.ts --project=chrome` | Console renders runtime overview | local screenshot generated |
| Agent detail | `cd apps/console && npx playwright test tests/e2e/responsive-snapshots.spec.ts --project=chrome` | Agent and version workflow is inspectable | local screenshot generated |
| Deployment workflow | `cd apps/console && npx playwright test tests/e2e/responsive-snapshots.spec.ts --project=chrome` | Deployment submission workflow is operable | local screenshot generated |
| Run workbench | `cd apps/console && npx playwright test tests/e2e/run-triage-replay.spec.ts --project=chrome` | Run triage and replay evidence are inspectable | local browser proof |
| Published surface route tester | `cd apps/console && npx playwright test tests/e2e/published-surfaces.spec.ts --project=chrome` | Route validation and request-log redaction work | local browser proof |
| Approval queue | `cd apps/console && npx playwright test tests/e2e/policy-approval.spec.ts --project=chrome` | Human decisions produce resume outcome evidence | local browser proof |
| Settings danger zone | `cd apps/console && npx playwright test tests/e2e/settings-platform-workbenches.spec.ts --project=chrome` | Dangerous platform actions require preflight and confirmation | local browser proof |
| Quickstart activation path | `uv run python scripts/compose_runtime_smoke.py` | Full local activation path works | local workflow artifact generated in CI as `compose-evidence-index` |

Hosted or public screenshot coverage is still incomplete unless a row above
links to a current generated artifact in CI or a maintained local report.
