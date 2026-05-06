---
description: "Default entry point. @router auto-classifies complexity (INSTANT/STANDARD/DEEP) and routes accordingly. For DEEP tasks, triggers full pipeline with planning, parallel implementation, and validation."
---

Follow this workflow strictly:

## Step 0: Route (auto)
Invoke `@router` to classify complexity:
- Load checkpoint: `python3 .github/tools/memory.py read checkpoint --budget 1500`
- Check graph freshness: `python3 .github/tools/codegraph.py why-stale --db .github/.cache/codegraph.db`
- Recall context: `python3 .github/tools/memory.py recall "<task keywords>"`
- Classify → INSTANT / STANDARD / DEEP

**INSTANT:** Skip to Step 3 — implement directly.
**STANDARD:** Steps 1-5 below.
**DEEP:** Full pipeline — @planner → task-batch → N×@implementer → @reviewer (×2) → @validator.

## Step 1: Understand
- Read all relevant files before making changes
- Identify existing patterns, conventions, and utilities
- List all files that will be affected
- Classify risk: 🟢 Additive / 🟡 Existing Logic / 🔴 Critical Path

## Step 2: Plan (if more than a simple fix)
Before writing code, briefly outline:
- What changes are needed and where
- What existing patterns to follow
- Any potential risks or side effects

## Step 3: Implement
- Follow existing conventions strictly
- Make minimal, focused changes
- TDD when test infrastructure exists: failing test → implement → verify
- Do not refactor unrelated code
- Do not add abstractions the task doesn't need

## Step 4: Verify
- Run tests if they exist
- Check for regressions
- Review your own changes for correctness and security

## Step 5: Summary
Report what was done:
- Files changed and why
- Tests added/modified
- Any follow-up needed

Now implement the following task:
