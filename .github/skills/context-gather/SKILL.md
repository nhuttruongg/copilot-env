---
name: context-gather
description: "Gather relevant context using codegraph envelopes and memory recall before implementing a task. Finds related files, patterns, dependencies, and tests."
triggers:
  - "gather context"
  - "before implementing"
  - "understand the scope"
---

# Context Gathering

Before implementing, gather context to avoid blind changes.

## Process

### 1. Find Related Files
- Get codegraph envelope for the target scope:
  ```bash
  python3 .github/tools/codegraph.py envelope <target> --budget 2000 --db .github/.cache/codegraph.db
  ```
- Search by name, imports, and content
- Identify: files to change, files with similar patterns, test files

### 2. Map Dependencies
- What does the target code import?
  ```bash
  python3 .github/tools/codegraph.py deps <file> --db .github/.cache/codegraph.db
  ```
- What imports the target code? (blast radius)
  ```bash
  python3 .github/tools/codegraph.py impact <file> --db .github/.cache/codegraph.db
  ```
- Shared utilities or types used?

### 3. Recall Prior Knowledge
```bash
python3 .github/tools/memory.py recall "<task keywords>"
python3 .github/tools/memory.py read decisions --budget 500
```
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
