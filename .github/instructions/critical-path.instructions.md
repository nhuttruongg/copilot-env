---
applyTo: "**/auth/**,**/payments/**,**/crypto/**,**/security/**"
---

# Critical Path Instructions

Files in `auth/`, `payments/`, `crypto/`, or `security/` are **🔴 Critical Path**.

## Mandatory Rules
- **Always route as DEEP complexity** regardless of change size
- **Always invoke @security for review** — no exceptions
- **@validator is mandatory** after implementation
- Line-by-line review of all changes (no bulk approvals)

## Code Requirements
- No hardcoded secrets, tokens, keys, or passwords
- All secrets loaded from environment variables or secure vault
- Parameterized queries for all database operations
- Input validation on all user-facing inputs
- Output encoding/escaping for all rendered content
- Use standard cryptographic libraries (no custom crypto)
- Proper error handling that doesn't leak internal details

## Authentication
- Verify auth checks on every protected endpoint
- Ensure session tokens are cryptographically random
- Implement proper token rotation and refresh
- Logout must invalidate server-side session state
- Rate limiting on all authentication endpoints

## Payments
- Idempotency keys for all financial transactions
- Double-entry verification where applicable
- Audit logging for all payment operations
- PCI compliance considerations documented

## Testing
- Security-specific test cases required (not just functional tests)
- Test for common attack vectors (injection, bypass, escalation)
- Test error paths (invalid tokens, expired sessions, malformed input)
