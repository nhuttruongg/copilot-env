---
description: "Generate comprehensive tests using TDD approach: happy path, edge cases, errors."
---

Generate tests for the specified code. Follow TDD principles:

1. **Identify what to test**: Read the code, understand behavior, find edge cases
2. **Follow existing patterns**: Check existing tests for framework, style, utilities
3. **Use AAA pattern**: Arrange → Act → Assert

Include:
- ✅ **Happy path**: Normal usage with valid inputs
- ⚠️ **Edge cases**: Empty, null, boundary, special characters
- ❌ **Error cases**: Invalid inputs, failures, timeouts
- 🔗 **Integration**: With real dependencies (mock externals only)

Rules:
- Descriptive names: `should [behavior] when [condition]`
- One assertion per test when practical
- Test behavior, not implementation
- Use project's existing test framework and patterns
- Mock external dependencies only, not internal modules
