# Production Console Live Deployment Flow

Date: 2026-06-01

## Goal

Make the Console core workflow production-oriented and live-only:

1. Register Agent.
2. Create AgentVersion.
3. Create/activate Deployment for an AgentVersion.
4. Submit tasks through Deployment, not Console mock data.
5. Inspect real Run, Task, Event, Attempt data returned by the backend.

## Current Gap

- Console still has a product-path `demoConsoleClient` backed by `mockData.ts`.
- Agents page can directly submit `/v1/agents/{agent_id}/tasks`, which is useful as a low-level API but is not the production deployment workflow.
- Deployments page controls deployments but cannot create one or submit work through one.
- Backend lacks `POST /v1/deployments/{deployment_id}/tasks`.
- Replay candidate versions are inferred from historical runs instead of loading real AgentVersion records.

## Backend Plan

1. Add tests proving:
   - `POST /v1/deployments/{deployment_id}/tasks` creates a queued task and run.
   - The created run is linked to the deployment id and deployment agent version.
   - Inactive deployments are rejected.
   - The endpoint appears in OpenAPI.
2. Add `DeploymentTaskCreate` and `DeploymentTaskCreateResponse`.
3. Add deployment task route requiring `agent:invoke`, tenant/project scope, and active deployment status.
4. Extend native runtime `create_task_run()` with optional `deployment_id` and persist it for in-memory and SQLAlchemy stores.

## Console Plan

1. Remove product-path mock mode from `consoleClient`; if API URL is absent, show offline state.
2. Add typed generated client methods:
   - `createDeployment`
   - `createDeploymentTask`
3. Add live client wrappers:
   - `consoleClient.createDeployment`
   - `consoleClient.createDeploymentTask`
4. Refactor Agents page to manage agents and versions only.
5. Refactor Deployments page into the production runtime entry:
   - create deployment from selected AgentVersion
   - control deployment desired status
   - submit JSON task through selected deployment
   - link to the created Run
6. Load replay candidate versions from the real AgentVersion API for the selected run.
7. Update contract tests so they fail if Console reintroduces mock product data.

## Verification

- Backend targeted tests for deployment tasks.
- Console contract tests.
- Console production build.
- Backend ruff on changed backend/test files.
