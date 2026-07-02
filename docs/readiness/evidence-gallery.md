# Evidence Gallery

This page indexes generated product evidence. It is not a marketing gallery; it
records what was captured, by which command, and which claim it supports.

| Evidence | Command | Claim Supported | Current Status |
|---|---|---|---|
| P0-A productized CLI | `uv run dimoorun publish examples/langgraph/support-agent && uv run dimoorun deploy support-agent --env local && uv run dimoorun run support-agent --env local --watch` | Fresh evaluator path can publish, deploy, run, and print Console deep links | local CLI proof |
| P0-A real native API CLI integration | `uv run pytest tests/cli/test_project_config_cli.py -q` | Productized publish, deploy, run, open, run detail, and run events work through the real FastAPI native API | local automated proof |
| P0-A demo seed | `uv run dimoorun demo seed --watch` | One command prepares example agent, deployment, and run evidence | local CLI proof |
| P0-B golden operator demo | `cd apps/console && npx playwright test tests/e2e/golden-operator-demo.spec.ts --project=chrome` | One browser path covers AgentVersion trust evidence, failed run, triage, replay, approval, promotion/rollback, and JSON audit evidence export | local browser proof |
| P0-B replay-to-rollback API chain | `uv run pytest tests/api/test_deployment_promotion.py::test_golden_operator_evidence_path_links_replay_quality_promotion_and_audit -q` | Replay comparison, dataset capture, quality gate preview, promote, rollback, and audit sink are connected through real API calls | local automated proof |
| P0-B CLI operator actions | `uv run pytest tests/cli/test_project_config_cli.py::test_cli_operator_evidence_commands_cover_triage_approval_and_rollback -q` | Failed run triage prints Console deep links and CLI next commands; approval and rollback commands call real API client methods | local automated proof |
| P0-B AgentVersion package trust evidence | `cd apps/console && npm test` | AgentVersion page exposes validation token, digest, signature/SBOM status, sandbox profile, secret refs, capabilities, and raw manifest evidence | local contract proof |
| 4-8w Integration Proof API | `uv run pytest tests/api/test_native_api.py::test_run_integration_evidence_is_written_through_real_api -q` | Real native API writes Langfuse trace link, OpenTelemetry exporter status, LiteLLM model routing, and failure evidence onto a Run | local automated proof |
| 4-8w Integration Proof Console | `cd apps/console && npx playwright test tests/e2e/integration-proof.spec.ts --project=chrome` | Run Detail displays integration evidence; Compatibility displays adapter certification matrix; AgentVersion trust evidence links to matrix and run evidence | local browser proof |
| 4-8w Integration Proof CLI | `uv run pytest tests/cli/test_project_config_cli.py::test_cli_operator_evidence_commands_cover_triage_approval_and_rollback -q` | `dimoorun run triage` prints the integration evidence deep link and integration evidence summary | local automated proof |
| 4-8w Adapter certification boundary | `cd apps/console && npm test` | Compatibility page records LangGraph, LangChain Agent, and DeepAgents support status for invoke, stream, resume, checkpoint, interrupt, cancel, idempotency, and error mapping | local contract proof |
| Dashboard next actions | `cd apps/console && npm test` | Dashboard exposes Publish, Deploy, Run, Inspect next actions | local contract proof |
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
