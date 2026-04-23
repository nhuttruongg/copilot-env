---
applyTo: "**/*.test.*,**/*.spec.*,**/__tests__/**"
---

# Testing Instructions

- Use descriptive test names: `should [expected behavior] when [condition]`
- Follow Arrange-Act-Assert (AAA) pattern
- One assertion per test when possible
- Test behavior, not implementation
- Use test fixtures and factories for test data
- Do not test private/internal methods directly
- Mock external dependencies (APIs, databases), not internal modules
- Include tests for: happy path, edge cases, error handling, boundary values
- Keep tests independent — no shared mutable state between tests
- Use `beforeEach`/`setUp` for common setup, not copy-paste
