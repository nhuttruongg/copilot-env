---
description: "End the current session. @scribe updates checkpoint, compacts memory if over budget, updates project-context.md, archives old sessions, suggests commit message."
---

End the current session and preserve state:

Invoke `@scribe` to perform session wrap-up:

## 1. Session Summary
- Read session log and consolidate into a summary
- Write summary to sessions memory

## 2. Checkpoint Update
- Overwrite `checkpoint.md` with current project state
- Include: what was accomplished, work in progress, unresolved items

## 3. Project Context
- Update `project-context.md` if structural changes occurred this session

## 4. Memory Maintenance
```bash
python3 .github/tools/memory.py status
```
- Compact any kinds over soft budget

## 5. Code Graph
```bash
python3 .github/tools/codegraph.py update --root . --db .github/.cache/codegraph.db
```

## 6. Archive
```bash
python3 .github/tools/session.py archive --days 7
```

## 7. Commit Suggestion
- Suggest a conventional commit message for the session's changes
