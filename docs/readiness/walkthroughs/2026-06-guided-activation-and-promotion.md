# Walkthrough: Guided Activation And Deployment Promotion

## Roles

- Platform operator
- Agent developer

## Workflow Scope

- Guided activation
- Deployment promotion

## Preconditions

- Repository dependencies installed locally
- Example agent package available under `examples/langgraph/support-agent`
- Console reachable and authenticated with the bootstrap operator
- Server, worker, database, Redis, and object storage path available through the local stack or direct service startup

## Walkthrough

1. Open the quickstart path and verify the selected tenant, project, and environment before changing any runtime resource.
2. Register the example agent package and confirm package validation returns a ready token instead of creating a draft version directly.
3. Create an AgentVersion with the validation token and confirm the version is `ready` rather than blocked by missing manifest or secret requirements.
4. Create a deployment, activate it, and submit a task so the operator can inspect one successful run before attempting deployment promotion.
5. Open the deployment promotion workflow and verify the impact preview shows candidate readiness, active runs, queued tasks, and rollback target.
6. Promote the candidate version only after the impact preview and audit reason are visible, then verify the deployment detail reflects the new version and retains rollback context.

## Evidence Produced

- Agent, AgentVersion, deployment, task, and run records
- Package validation token and readiness state
- Deployment promotion audit record and rollback target
- Browser workflow proof from the deployment promotion and package validation specs

## Friction Log

- The first-run path still spans quickstart docs, CLI/API commands, and multiple Console pages instead of one guided activation surface.
- Runtime dependency health is visible in several places, but there is still no single activation checklist that blocks the next step with one consolidated explanation.
- Deployment promotion gives impact preview and rollback context, but the product still depends on the operator knowing where to inspect the earlier package-validation evidence.

## Follow-Up Backlog Items

- Add a first-run activation workbench that links dependency health, package validation, ready-version state, deployment creation, and first successful run evidence.
- Add explicit cross-links from deployment promotion back to package validation and quality evidence so the operator does not have to reconstruct readiness manually.
- Add a saved activation progress view for platform operator and agent developer roles so the handoff between setup and promotion is auditable.
