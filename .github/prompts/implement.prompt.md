---
description: "Full implementation workflow: understand → plan → implement → verify. Use for non-trivial tasks."
---

Follow this workflow strictly:

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
