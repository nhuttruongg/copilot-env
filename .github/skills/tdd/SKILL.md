---
name: tdd
description: "Test-Driven Development workflow. Write failing tests first, implement minimal code, verify. Use when implementing features that need test coverage."
---

# TDD Workflow

## Cycle

1. **Red** — Write a failing test that defines the expected behavior
2. **Green** — Write the minimum code to make the test pass
3. **Refactor** — Clean up while keeping tests green

## Rules

- One test at a time. Don't batch.
- Test behavior, not implementation details.
- Each test should have one clear assertion.
- Name tests descriptively: `should [behavior] when [condition]`

## Test Structure (AAA)

```
Arrange — set up test data and dependencies
Act     — execute the function/method under test
Assert  — verify the expected outcome
```

## What to Test

1. **Happy path** — normal usage with valid inputs
2. **Edge cases** — empty, null, boundary values, special characters
3. **Error cases** — invalid inputs, failures, timeouts
4. **Integration** — how it works with real dependencies

## What NOT to Test

- Private implementation details
- Framework/library internals
- Simple getters/setters with no logic
- Third-party code

## Verification Checklist

- [ ] All new tests pass
- [ ] Existing tests still pass (no regressions)
- [ ] Edge cases covered
- [ ] Error scenarios covered
- [ ] Linter/formatter passes
