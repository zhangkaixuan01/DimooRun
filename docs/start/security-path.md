# Security Path

Goal: evaluate package trust, secret handling, policy enforcement, approvals,
and audit evidence.

## Path

1. Review [Trust And Security](../TRUST_AND_SECURITY.md).
2. Publish an example package and inspect validation evidence.
3. Inspect AgentVersion manifest, capabilities, secret references, and runtime
   constraints.
4. Review policies, human tasks, model gateway, tool gateway, and secret
   rotation pages.
5. Inspect audit logs for package, deployment, task, policy, approval, and
   dangerous settings actions.

## Done

- Raw secrets are not required in package manifests, run inputs, or screenshots.
- High-risk actions have policy decisions, approval state, or audit reasons.
- You know which evidence is local proof and which production-grade proof is
  still incomplete.
