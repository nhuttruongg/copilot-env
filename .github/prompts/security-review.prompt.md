---
description: "Critical-path security audit. @security performs line-by-line review of auth, crypto, payments, and security-sensitive code with OWASP-based checklist."
---

Run a security audit on the specified code:

Invoke `@security` to perform a critical-path audit:

1. **Scope identification** — identify all files matching `auth/**`, `payments/**`, `crypto/**`, `security/**`, `migrations/**`
2. **Line-by-line review** of critical-path files
3. **OWASP checklist** — authentication, injection, secrets, cryptography, data protection
4. **Migration safety** — reversibility, data loss, permission escalation
5. **Findings report** with severity, impact, and specific fix for each issue

Every finding must include:
- Severity: 🔴 Critical / 🟡 Warning
- File and line reference
- Impact description
- Specific remediation

Review the following:
