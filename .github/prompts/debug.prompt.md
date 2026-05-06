---
description: "Systematic bug investigation using the Four Phases methodology. @debugger traces code flow via codegraph, forms hypotheses, finds root causes."
---

Investigate this bug using the Four Phases methodology:

## Phase 1: Root Cause Discovery
- Reproduce the problem (expected vs actual behavior)
- Use codegraph to trace the call chain and dependencies
- Form 2-3 ranked hypotheses

## Phase 2: Pattern Analysis
- Check memory for similar past issues: `memory.py recall "<bug keywords>"`
- Check recent git changes
- Look for common bug patterns (null, race condition, stale state)

## Phase 3: Hypothesis Testing
- Test most likely hypothesis first
- Trace code flow from entry to bug location
- Check data transformations at each step

## Phase 4: Fix & Prevent
- Identify root cause (not symptom)
- Propose minimal fix with side effect analysis
- Add a test that catches this bug
- Record learning if non-obvious

**Escalation:** If 3+ fixes fail, question the architecture — the bug may be a design flaw.

Debug the following issue:
