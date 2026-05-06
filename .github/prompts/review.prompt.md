---
description: "Review code changes. For single tasks: combined correctness + quality check. For multi-task sessions: invoke @validator for cross-task consistency and verification gate."
---

Review the specified code. For multi-task sessions, use `/validate` instead.

Check blast radius first:
```bash
python3 .github/tools/codegraph.py impact <changed-file> --db .github/.cache/codegraph.db
```

Then check systematically:

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
