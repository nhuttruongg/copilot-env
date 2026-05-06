---
name: session-checkpoint
description: "What to write at session end: checkpoint content, project-context updates, session archive. Used by @scribe."
triggers:
  - "end session"
  - "write checkpoint"
  - "session wrap-up"
---

# Session Checkpoint

What @scribe writes at the end of every session.

## Checkpoint Content (`checkpoint.md`)

The checkpoint is an **overwrite** (not append). It captures the project state RIGHT NOW:

```markdown
## <ISO timestamp>

### Current State
[1-2 sentences: what the project is doing / where work stands]

### This Session
- [What was accomplished]
- [Key changes: files modified, features added/fixed]

### In Progress
- [Unfinished work, if any]
- [Task IDs still open]

### Blockers
- [Anything blocking progress]

### Key Decisions Made
- [DEC-NNN references if new decisions this session]

### Next Steps
- [What to do next session]
```

## Procedure

### Step 1: Summarize Session
Read `sessions/<current>/log.md` and consolidate.

### Step 2: Update Checkpoint
```bash
python3 .github/tools/memory.py write checkpoint "<checkpoint content>"
```

### Step 3: Update Project Context (if structural changes)
Rewrite `.github/.cache/project-context.md` if:
- New directories or modules were created
- Dependencies were added/removed
- Architecture changed
- Build/test commands changed

### Step 4: Check Memory Health
```bash
python3 .github/tools/memory.py status
```
If any kind over soft budget → invoke `memory-compaction` skill.

### Step 5: Update Code Graph
```bash
python3 .github/tools/codegraph.py update --root . --db .github/.cache/codegraph.db
```

### Step 6: Archive Stale Sessions
```bash
python3 .github/tools/session.py archive --days 7
```

### Step 7: Suggest Commit Message
Based on session changes, suggest a conventional commit:
```
feat: <description>    # for new features
fix: <description>     # for bug fixes
refactor: <description> # for refactors
```
