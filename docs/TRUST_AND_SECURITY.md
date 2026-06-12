# Trust And Security

DimooRun's trust posture is based on evidence in this repository, not on
marketing language. The short version is: security-shaped and governance-aware,
but not yet externally certified or fully hosted-proof.

## Security Posture

Current strengths:

- production startup guards fail closed on unsafe defaults
- runtime governance covers secrets, model gateway, tool gateway, and approval
  paths
- audit, event, and artifact evidence are first-class runtime outputs
- release workflow includes SBOM and provenance steps

Current limits:

- hosted smoke and hosted trust verification are incomplete
- example agents are deterministic evaluation packages, not production apps
- some operator workflows still need more end-to-end hardening proof

## Security Reporting

Follow [SECURITY.md](../SECURITY.md) for disclosure expectations. Do not open a
public bug report for a live vulnerability before private coordination.

## Dependency And Supply Chain Checks

Repository evidence today includes:

- `uv run ruff check ...`
- `uv run mypy ...`
- `uv run pytest -q`
- release checks via `scripts/release_check.py`
- OpenAPI drift checks via `scripts/check_openapi_diff.py`
- SBOM generation and provenance attestation in `.github/workflows/release.yml`

These checks improve confidence, but they are not a substitute for hosted
operations review.

## Data Retention And Redaction

Trust assumptions for operator evidence:

- request logs and artifacts should be reviewed as sensitive operational data
- secrets must not be copied into screenshots, issue reports, or public demos
- runtime evidence should preserve identifiers and decisions without exposing
  hidden secret values
- screenshots and demos should prefer deterministic fixtures over real customer data

## Secret Handling Model

The current product direction is:

- packages declare required secret references
- runtime services resolve secrets through governed secret providers
- operators should pass references, not raw secret material, through product workflows
- local development can use simplified providers, but production claims require
  stronger backing services and controls

## Audit And Approval Model

Trust in DimooRun depends on being able to answer:

- who changed deployment state
- which policy denied or required approval
- which run/version/deployment handled the request
- what evidence exists for replay, incident, or restore actions

That is why audit and approval behavior is part of the product boundary rather
than an optional add-on.

## Production Safety Defaults

Before calling an environment safe for serious use, expect at least:

- non-dev runtime mode
- durable SQLAlchemy runtime store
- non-default object store credentials
- explicit secret provider configuration
- explicit CORS configuration
- governed model/tool/secret paths where relevant

## Related Documents

- [Threat Model](THREAT_MODEL.md)
- [Operations Runbook](OPERATIONS_RUNBOOK.md)
- [Current Maturity](readiness/current-maturity.md)
- [Security Policy](../SECURITY.md)
