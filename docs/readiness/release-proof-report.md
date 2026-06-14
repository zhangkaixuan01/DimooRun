# Release Proof Report

This document is the canonical backfill template for hosted tagged release
evidence from `.github/workflows/release.yml`.

## Workflow Contract

- Trigger: Git tag push matching `v*` or manual `workflow_dispatch`
- Workflow: `.github/workflows/release.yml`
- Required hosted artifacts:
  - `release-evidence-index`
  - `release-sbom`
- Required hosted outcomes:
  - release verification job passed
  - SBOM generation, vulnerability scan, and provenance attestation passed
  - Python package publish step passed
  - TypeScript SDK publish step passed
  - GitHub release note publication passed

## Current State

Status: pending hosted tagged release proof.

Repository-local contract exists through `.github/workflows/release.yml`,
`scripts/release_check.py`, `scripts/check_openapi_diff.py`, SDK tests, and the
release workflow tests, but no successful tagged hosted run is recorded here
yet.

## Hosted CI Backfill Template

- Date:
- Git ref / tag:
- Workflow run id:
- Release URL:
- Python package version published:
- TypeScript SDK version published:
- `release-evidence-index` artifact:
- `release-sbom` artifact:
- Provenance result:
- Vulnerability scan result:
- Notes:

## Scorecard Rows To Update

When the hosted tagged release succeeds, update these rows in
`docs/readiness/scorecard.md` with the same run id and artifact names:

- `Phase 11: SDK, CLI, And Release Engineering`
- `Milestone C: External GA`
- `Release workflow builds, scans, signs or attests, and publishes artifacts.`
- `SDK, CLI, README, quickstart, examples, trust docs, and release workflow are coherent and versioned.`

## Closure Verdict

Do not mark this complete from local release-contract tests alone. Closure
requires one successful tagged hosted release run with the required artifacts
and published package evidence.
