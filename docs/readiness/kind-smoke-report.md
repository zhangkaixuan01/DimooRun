# KinD Smoke Report

This report records the current local and hosted-evidence contract for the Helm
/ KinD smoke path. It is not yet a hosted pass report.

## Command

Working directory: repository root.

```bash
uv run python scripts/helm_smoke.py --cluster-runtime kind
```

Supporting toolchain checks:

Working directory: repository root.

```bash
helm version
kubectl version --client
kind version
```

## Result

Status: `contract-defined-hosted-proof-pending`

Date checked: 2026-06-14

The repository now defines a deterministic KinD smoke contract through
`scripts/helm_smoke.py` and `.github/workflows/integration.yml`. The smoke path
validates live-smoke overrides, seeds external secret references, installs the
chart with application replicas forced to `0`, and collects hosted diagnostics.
This improves auditability, but it is still not a claim that a current hosted
ephemeral-cluster run has passed.

Latest hosted observation:

- `integration.yml` run `27475315682`
- Date checked: `2026-06-14`
- Commit SHA: `2f1fbc1d4deacbb514b3dfbf90ad1662086fc6e2`
- Hosted result: KinD smoke job passed and logged
  `values`, `templates`, `migration-job`, `networkpolicy`, `pdb`,
  `servicemonitor`, `cluster-create`, `namespace-create`,
  `seed-postgres-secret`, `seed-redis-secret`, `seed-object-store-secret`,
  `helm-template`, `helm-install`, `release-status`, and `resources-present`.
- Hosted artifact published: `kind-smoke`

This hosted run is useful evidence that the committed KinD smoke contract
worked on GitHub-hosted runners for that SHA. It is not yet the final closeout
for the current worktree because the current uncommitted workflow/docs chain
expects the matching `kind-smoke-index` artifact to be part of the evidence
set.

## Evidence

Static and repository-local proof:

Working directory: repository root.

```bash
uv run python scripts/helm_smoke.py
```

Hosted integration evidence now has stable artifact names for citation:

- diagnostics artifact: `kind-smoke`
- evidence index artifact: `kind-smoke-index`

The evidence index points back to `integration.yml`, the hosted smoke command,
and the expected diagnostic files:

- `kind-resources.txt`
- `kind-policies.txt`
- `kind-helm-status.txt`

## Next Action

Run the hosted Integration workflow and inspect the current `kind-smoke` plus
`kind-smoke-index` artifacts.

If the run passes, update this report and `scorecard.md` with the hosted run
identifier and exact artifact names. If it fails, keep the first failing
cluster diagnostic in this report instead of overstating completion.

## Hosted CI Backfill Template

Fill this section when a hosted integration run is available:

- Hosted run id: `<run-id>`
- Branch/ref: `<branch-or-tag>`
- Date checked: `<yyyy-mm-dd>`
- Published artifacts:
  - `kind-smoke`
  - `kind-smoke-index`
- Outcome summary:
  - `<pass-or-fail summary>`
  - `<key cluster/resource evidence>`
  - `<remaining follow-up if not fully closed>`

## Scorecard Rows To Update

When hosted integration proof is available, update these rows in
`docs/readiness/scorecard.md` with the same hosted run id and artifact names:

- `Phase 10: Deployment And Operations Hardening`
- `Kubernetes smoke passes in an ephemeral cluster.`
- `Milestone C: External GA`
