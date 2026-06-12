# Comparisons

These comparisons are intended to help evaluators place DimooRun accurately.
They are not vendor scorecards and they intentionally avoid unverifiable
superiority claims.

## Versus A Plain LangGraph App

A plain LangGraph app gives you agent logic and graph execution. DimooRun adds a
runtime/control layer around that logic:

- package validation and version records
- deployment intent and runtime status
- task/run/attempt/event persistence
- audit, approval, replay, and operator workflows

### Evidence In Repository

- `examples/langgraph/support-agent/`
- `apps/server/dimoo_run/api/native/deployments.py`
- `apps/server/dimoo_run/worker/`
- `apps/console/src/pages/runs/`

## Versus LangGraph Platform-Style Compatibility

DimooRun includes compatibility surfaces so existing ecosystem workflows can be
mapped into its native runtime model. The goal is migration help and lower
adoption friction, not perfect one-to-one product equivalence.

### Evidence In Repository

- `apps/server/dimoo_run/api/compat/`
- `tests/compat/test_langgraph_compat_api.py`
- `apps/console/src/pages/compatibility/CompatibilityExplorerPage.vue`
- `tests/compatibility/test_golden_runtime_alignment.py`

## Versus Generic Workflow Engines

Generic workflow engines are good at orchestration. DimooRun is narrower: it is
specifically shaped around agent runtime evidence, deployment safety, policy,
approval, and compatibility needs.

### Evidence In Repository

- `docs/reference/concepts.md`
- `apps/server/dimoo_run/runtime/`
- `apps/server/dimoo_run/replay/`
- `apps/server/dimoo_run/policy/`

## Versus Model Gateways

Model gateways focus on provider routing, policies, budgets, and usage around
model calls. DimooRun can integrate those concerns, but its scope is broader:
it also owns deployments, runs, attempts, approvals, replay, and operator
surfaces.

### Evidence In Repository

- `apps/server/dimoo_run/model_gateway/`
- `apps/server/dimoo_run/tools/gateway.py`
- `tests/governance/test_governance_gateways.py`
- `apps/console/src/pages/governance/ModelGatewayWorkbenchPage.vue`

## Boundary

The right question is not "is DimooRun better than everything else?" The right
question is whether you need an adapter-first runtime control plane around
existing agent code instead of only a framework, only a workflow engine, or
only a gateway.
