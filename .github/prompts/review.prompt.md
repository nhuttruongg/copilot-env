---
description: "Review code changes for correctness, security, performance, and style. Provide actionable feedback."
---

Review the specified code. Check systematically:

1. **Correctness**: Logic errors, unhandled edge cases, async issues, regressions
2. **Security**: Injection risks, exposed secrets, auth gaps, 🔴 critical path files
3. **Performance**: N+1 queries, unnecessary renders, memory leaks
4. **Style**: Consistency with project conventions, over-engineering

Format as:

```
## Review

**Verdict:** APPROVED / NEEDS_REVISION
**Confidence:** High / Medium / Low

### 🔴 Critical (must fix)
- [issue] at [file:line]

### 🟡 Warning (should fix)
- [issue] at [file:line]

### 🟢 Minor
- [suggestion]

### ✅ What's Good
- [positive observation]
```

Be specific with file:line references. If the code is fine, say so briefly.
