---
name: risk-classification
description: "Classify files into risk tiers (🟢🟡🔴) based on path patterns, change type, and dependency count. Used by @planner and @validator."
triggers:
  - "classify risk"
  - "file risk level"
  - "critical path files"
---

# Risk Classification

Classify every file touched in a task into a risk tier.

## Risk Rubric

### 🟢 Additive (Low Risk)
- New files (no existing consumers)
- Test files (`**/test_*`, `**/*.test.*`, `**/*.spec.*`)
- Documentation (`**/*.md`, `**/docs/**`)
- Config files that don't affect runtime
- Fixtures, mocks, test utilities

### 🟡 Existing Logic (Medium Risk)
- Modifying existing business logic
- Changing function signatures
- Refactoring internal implementation
- Adding parameters to existing functions
- Files with 5-10 dependents (check via `codegraph.py impact`)

### 🔴 Critical Path (High Risk)
- Path matches: `**/auth/**`, `**/payments/**`, `**/crypto/**`, `**/security/**`, `**/migrations/**`
- Files with >10 dependents
- Core infrastructure (database connection, middleware, routing)
- Public API contracts (breaking changes)
- Files containing secrets handling, token generation, encryption

## Procedure

1. For each file, check path patterns first (instant classification for critical paths).
2. Run dependency check:
   ```bash
   python3 .github/tools/codegraph.py impact <file> --db .github/.cache/codegraph.db
   ```
3. Count dependents: 0-4 = 🟢, 5-10 = 🟡, >10 = 🔴.
4. Path-based 🔴 overrides dependency count (auth/** is always 🔴 regardless of dependents).

## Escalation Rules

| Risk | Review Required | Security Audit | Validator Mandatory |
|:----:|:---:|:---:|:---:|
| 🟢 | Standard | No | No (optional) |
| 🟡 | Enhanced | No | Profile ≥ medium |
| 🔴 | Thorough + @security | Yes (auto) | Always |
