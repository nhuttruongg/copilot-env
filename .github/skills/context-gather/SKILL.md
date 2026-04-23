---
name: context-gather
description: "Gather relevant context before implementing a task. Finds related files, patterns, dependencies, and tests to ensure informed implementation."
---

# Context Gathering

Before implementing, gather context to avoid blind changes.

## Process

### 1. Find Related Files
- Search by name, imports, and content
- Identify: files to change, files with similar patterns, test files

### 2. Map Dependencies
- What does the target code import?
- What imports the target code? (blast radius)
- Shared utilities or types used?

### 3. Identify Patterns
- How are similar features implemented?
- Existing base classes, hooks, or utilities to reuse?
- Any relevant abstractions?

### 4. Check Tests
- Do tests exist for target code?
- Test patterns and utilities available?

### 5. Classify Risk
- 🟢 Additive: new files, no existing code affected
- 🟡 Existing Logic: modifying behavior, refactoring
- 🔴 Critical Path: auth, crypto, payments, deletions, migrations

## Output

```markdown
## Context: [task]

### Files to Modify
- [file — what needs to change]

### Blast Radius
- [file — affected by our changes]

### Patterns to Follow
- [file — shows how similar features are implemented]

### Existing Tests
- [test file — coverage status]

### Risk: 🟢/🟡/🔴
[brief justification]
```
