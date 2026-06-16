# Compatibility Support Matrix

Compatibility APIs let LangGraph-shaped clients enter DimooRun without bypassing native governance.

| Surface | Status | Native Evidence | Notes |
|---|---|---|---|
| assistants | supported | Agent and AgentVersion mapping | Can bind to an existing deployment when provided |
| threads | supported | checkpoint_thread_id mapping | Scoped by tenant and project |
| runs | supported | Run and Task mapping | Native runtime state remains source of truth |
| stream events | supported | ReplayBuffer event ids | Event and update modes are supported |
| Last-Event-ID replay | supported | replayed event list | Expired replay returns `stream_replay_expired` |
| cancel | supported | Run, Task, and audit update | Uses native cancellation semantics |
| join | supported | Run terminal status and audit update | Does not execute external hosted LangGraph infrastructure |
| hosted deployments | manual migration required | native Deployment workflow | Use DimooRun deployments instead |
| LangGraph Platform managed services | manual migration required | migration report remediation | Hosted platform settings require review |
