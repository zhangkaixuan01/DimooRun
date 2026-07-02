# Migration Report: compatibility-basic

- Source: `examples\compatibility\langgraph-basic\source`
- source type: langgraph
- Entrypoint: `agent:build_graph`
- config: langgraph.json
- env file: .env
- Graphs:
  - support -> agent:build_graph
- Dependencies: langgraph>=1.0.0, langchain-core>=1.0.0
- checkpoint backend: not detected
- store backend: not detected
- Warnings: checkpoint migration is best-effort
- Compatibility warnings: none