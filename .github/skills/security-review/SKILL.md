---
name: security-review
description: "Security-focused code review following OWASP guidelines. Uses codegraph impact analysis to assess blast radius. Auto-invoked on critical-path files."
triggers:
  - "security audit"
  - "OWASP check"
  - "critical path review"
---

# Security Review

## Scope Detection

Identify critical-path files via codegraph:
```bash
python3 .github/tools/codegraph.py search "auth" --db .github/.cache/codegraph.db
python3 .github/tools/codegraph.py impact <critical-file> --db .github/.cache/codegraph.db
```

Files matching `auth/**`, `payments/**`, `crypto/**`, `security/**`, `migrations/**` get line-by-line review.

## Checklist

### Injection
- [ ] SQL injection: parameterized queries used?
- [ ] XSS: user input sanitized before rendering?
- [ ] Command injection: shell commands properly escaped?
- [ ] Path traversal: file paths validated?

### Authentication & Authorization
- [ ] Auth checks on all protected endpoints?
- [ ] Password hashing (bcrypt/argon2, not MD5/SHA)?
- [ ] Session management secure (httpOnly, secure, sameSite)?
- [ ] CSRF protection in place?

### Secrets & Data
- [ ] No hardcoded secrets, API keys, or passwords?
- [ ] Sensitive data encrypted at rest and in transit?
- [ ] PII properly handled (logging, storage)?
- [ ] .env files in .gitignore?

### Dependencies
- [ ] No known vulnerable dependencies?
- [ ] Lock files committed?
- [ ] Dependencies from trusted sources?

### Configuration
- [ ] Debug mode disabled in production?
- [ ] CORS properly configured?
- [ ] Error messages don't leak internals?
- [ ] Rate limiting on public endpoints?

## Severity Levels

- 🔴 **CRITICAL**: Exploitable now, data exposure risk
- 🟡 **HIGH**: Exploitable with some effort
- 🟢 **MEDIUM**: Defense-in-depth gap
- ⚪ **LOW**: Best practice deviation

## Output

```
## Security Review: [scope]

**Risk Level:** [CRITICAL/HIGH/MEDIUM/LOW]

### Findings
| # | Severity | Issue | Location | Remediation |
|---|----------|-------|----------|-------------|
| 1 | 🔴 | ... | file:line | ... |

### Recommendations
- [actionable next steps]
```
