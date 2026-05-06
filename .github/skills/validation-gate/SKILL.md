---
name: validation-gate
description: "The Verification Iron Law procedure. No completion claims without fresh evidence. Used by @validator."
triggers:
  - "validate session"
  - "verification gate"
  - "final check"
---

# Validation Gate

## Iron Law

> **NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**
> If you haven't run the verification command in THIS message and captured its output, you CANNOT claim it passes.

This is not a guideline. It is an absolute rule. No exceptions.

## Gate Procedure

### Gate 1: Acceptance Criteria
For EVERY criterion in `plan.md`:
1. Identify the proving command.
2. Run it. Capture stdout + exit code.
3. ✅ only with evidence. ❌ with actual output if failed. ⚠️ UNVERIFIED if command cannot run.

### Gate 2: Test Suite
Run the project's full test suite:
```bash
pytest tests/ -v --tb=short 2>&1
```
Report: total / passed / failed / skipped. Every failure is a finding.

### Gate 3: Static Analysis
Run lint + type check (adapt to project):
```bash
python3 -m flake8 . --count --show-source --statistics 2>&1 || true
python3 -m mypy . 2>&1 || true
```

### Gate 4: Code Cleanliness
- Dead code (unused imports, unreachable branches)
- Leaked TODOs/FIXMEs (acceptable only if tracked in a task)
- Convention drift vs `project-context.md`
- For 🔴 files: line-by-line review, auto-invoke @security

### Gate 5: Cross-Task Consistency (multi-task sessions)
- Interfaces between tasks match (types, signatures, contracts)
- No duplicate implementations
- No conflicting assumptions

### Gate 6: Probe Tests
Generate 2-3 edge-case tests the implementers may have missed:
- Write them as actual test code
- Run them
- Report results (pass = good coverage, fail = finding)

## Verdict

| Verdict | When |
|---|---|
| **PASS** | All gates green. No critical findings. |
| **FAIL** | Any acceptance criterion ❌. Test suite failures. Critical security finding. |
| **NEEDS-REWORK [task-ids]** | Specific tasks need fixes; others are fine. |

## Report Format

Write to `sessions/<id>/validation.md` with:
- Verdict + rationale
- Per-criterion evidence table
- Test suite summary
- Static analysis findings
- Cleanliness findings
- Probe test results

## Red Flags (instant FAIL)
- ❌ Claiming "tests pass" without running them
- ❌ Skipping critical-path file review
- ❌ No probe tests generated
- ❌ Evidence from a previous session (must be fresh)
