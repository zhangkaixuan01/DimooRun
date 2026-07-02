# Developer Path

Goal: bring existing agent code into DimooRun without rewriting business logic.

## Path

1. Start from an existing LangGraph, LangChain Agent, or DeepAgents package.
2. Ensure the package has a manifest with runtime framework, adapter,
   entrypoint, capabilities, and required secret references.
3. Publish with `uv run dimoorun publish <agent-path>`.
4. Deploy with `uv run dimoorun deploy <agent-name> --env local`.
5. Submit work with `uv run dimoorun run <agent-name> --env local --watch`.

## Done

- Package validation returns a ready validation token.
- The created AgentVersion is `ready`.
- The Deployment is `active`.
- A run created from your package is visible in Console.
