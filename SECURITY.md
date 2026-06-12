# Security Policy

## Reporting A Vulnerability

Do not file a public GitHub issue for a suspected live vulnerability before
private coordination.

Preferred path:

1. Open a private GitHub Security Advisory draft if that path is available.
2. Otherwise contact the maintainers privately before public disclosure.

Include:

- affected version or commit
- reproduction steps
- impact statement
- whether secrets, tenant isolation, or hosted exposure are involved

## What To Avoid In Reports

- do not paste live secrets
- do not post customer data
- do not publish exploit details before maintainers have time to respond

## Supported Scope

Security-sensitive areas include:

- authentication and sessions
- scope isolation
- package loading and worker execution
- secret, model gateway, and tool gateway paths
- audit and artifact evidence handling

## Response Expectations

Maintainers should:

- acknowledge receipt
- triage severity and exposure
- coordinate a fix or mitigation
- update public notes after private handling is complete

This document is a reporting baseline, not a guarantee of commercial support SLAs.
