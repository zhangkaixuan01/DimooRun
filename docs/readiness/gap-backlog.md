# Readiness Gap Backlog

This backlog records known gaps that should not block the immediate OpenAPI
contract fix, but should remain visible before making stronger production or GA
claims.

## Fixed In Current Pass

- OpenAPI schema drift: `openapi/dimoorun.openapi.json` was out of date and
  caused `scripts/check_openapi_diff.py` plus release-contract tests to fail.
  The schema has been regenerated from the current FastAPI app.

## Remaining Hard Gaps

- API workflow test runtime is too heavy for quick local verification. Single
  API test files pass, but the full `tests/api` suite timed out in the current
  local environment and needs profiling, splitting, or timeout-budget work.
- Hosted/default-browser proof remains incomplete. Local browser and workflow
  proof exists, but the public evidence path is not enough for external
  production-grade claims.
- Clean hosted Compose and ephemeral Kubernetes smoke evidence still need
  closure. Compose, Docker, Helm, and KinD contracts exist, but the evidence
  boundary is still partial.
- Helm production defaults need tightening. Chart values still leave several
  resource blocks empty and require environment-specific hardening before use as
  production defaults.
- Release and external trust proof are incomplete. Release workflows include
  package, image, SBOM, scan, and provenance steps, but externally verifiable
  evidence is not yet maintained as a completed readiness artifact.
- TypeScript SDK publication metadata needs review. `packages/sdk-js` currently
  declares `UNLICENSED`, which is a blocker for clean public adoption unless
  that is an intentional policy.
- The `extensions` domain table is still explicitly marked as placeholder-level
  metadata and should not be represented as a hardened product surface yet.

## Remaining Product Gaps

- Some Console pages are broad route/product surfaces rather than fully proven
  operator workflows. Treat unverified workflows as partial even when the page
  exists.
- Generated screenshot evidence is local and not maintained as a public,
  current gallery artifact.
- First-user activation still needs a cleaner, externally repeatable proof path
  that starts from a fresh checkout and ends with run evidence in Console.
- Trust and security documentation is present, but external certification,
  hosted trust verification, and managed-service support guarantees are not.

## Claim Boundary

Until these items are closed, keep the project claim at:

```text
Production-shaped foundation: yes.
External production-grade platform: not yet.
```
