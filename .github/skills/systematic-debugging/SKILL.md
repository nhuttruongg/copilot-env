---
name: systematic-debugging
description: "Four Phases debugging methodology: Root Cause Discovery → Pattern Analysis → Hypothesis Testing → Fix & Prevent. Escalation after 3 failed fixes. Used by @debugger."
triggers:
  - "debug this"
  - "find the bug"
  - "something is broken"
---

# Systematic Debugging — Four Phases

## Iron Law

> After 3+ failed fixes, question the architecture. The bug may be a design flaw, not a code mistake.

## Phase 1: Root Cause Discovery

1. **Define the bug precisely**: expected behavior vs actual behavior.
2. **Reproduce**: find minimal reproduction steps. If you can't reproduce, you can't fix.
3. **Trace the call chain** via codegraph:
   ```bash
   python3 .github/tools/codegraph.py callers <function> --db .github/.cache/codegraph.db
   python3 .github/tools/codegraph.py callees <function> --db .github/.cache/codegraph.db
   ```
4. **Form 2-3 ranked hypotheses** based on the trace.

## Phase 2: Pattern Analysis

1. **Check memory for similar past bugs**:
   ```bash
   python3 .github/tools/memory.py recall "<bug keywords>"
   ```
2. **Check recent changes**: `git log --oneline -10`
3. **Common bug patterns checklist**:
   - Null / undefined / None where not expected
   - Type mismatch (string where int expected)
   - Race condition / timing issue
   - Stale state / cache invalidation
   - Off-by-one / boundary condition
   - Wrong assumption about library behavior
   - Environment difference (dev vs prod)

## Phase 3: Hypothesis Testing

1. **Test most likely hypothesis first.**
2. **Trace data at each transformation step** — print/log intermediate values.
3. **Use bisection** when the error location is unclear:
   - Binary search through the call chain
   - Check data integrity at each midpoint
4. **Verify with a test case** that reproduces the bug.

## Phase 4: Fix & Prevent

1. **Minimal fix** — change only what's necessary to fix the root cause.
2. **Side effect analysis** — what else could this fix affect?
   ```bash
   python3 .github/tools/codegraph.py impact <fixed-file> --db .github/.cache/codegraph.db
   ```
3. **Write a regression test** that catches this exact bug.
4. **Record the learning** if non-obvious:
   ```bash
   python3 .github/tools/memory.py write learnings "<insight about this bug pattern>"
   ```

## Escalation

If the bug persists after 3 fix attempts:
- Stop fixing symptoms.
- Step back and analyze the design.
- The bug may require an architectural change, not a code patch.
- Present the situation to the user with:
  - What was tried
  - Why each attempt failed
  - The architectural concern
  - Proposed redesign (if applicable)

## Red Flags
- ❌ Guessing the fix without reproducing the bug
- ❌ Fixing a symptom without finding root cause
- ❌ Making changes without understanding the call chain
- ❌ Not writing a regression test after fixing
