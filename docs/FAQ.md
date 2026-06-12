# FAQ

## What Is DimooRun?

DimooRun is an adapter-first runtime control plane for AI agents. It wraps
existing agent code with runtime APIs, deployment controls, governance, replay,
observability, and operator workflows.

## Is DimooRun A New Agent Framework?

No. The product is intentionally positioned around existing agent code rather
than as a replacement framework.

## Is It Ready For External Production Use?

Not yet. Use [Current Maturity](readiness/current-maturity.md) and
[Production Readiness Scorecard](readiness/scorecard.md) before making that
claim.

## Which Frameworks Does It Support Today?

Current first-class direction is:

- LangGraph
- LangChain Agent
- DeepAgents

Support quality depends on the adapter path and the surrounding workflow proof.

## Do I Need Docker To Evaluate It?

For the full local happy path, yes. Some tests and docs can be read without
Docker, but the most realistic evaluator flow uses the Compose stack.

## Does It Handle Secrets And Governance?

It has meaningful secret, model gateway, tool gateway, policy, and approval
foundations. That is different from saying every production governance workflow
is fully proven in hosted environments.

## Why Are There Numeric IDs In The APIs?

Internal managed resources use numeric IDs as the source of truth. External
protocol identifiers such as request IDs, trace IDs, and object URIs stay as
strings.

## How Should I Contribute?

Start with [CONTRIBUTING.md](../CONTRIBUTING.md), then inspect the
[Roadmap](ROADMAP.md) and the production-grade gap-closure plan.
