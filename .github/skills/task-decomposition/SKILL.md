---
name: task-decomposition
description: "Break a complex task into a subtask DAG with dependencies, risk levels, file ownership, and parallelization hints. Used by @planner."
triggers:
  - "plan with subtasks"
  - "decompose into tasks"
  - "break down this work"
---

# Task Decomposition

Break a complex task into a parallelizable subtask DAG.

## Algorithm

### Step 1: Identify Boundaries
Use codegraph to find module boundaries:
```bash
python3 .github/tools/codegraph.py module <path> --db .github/.cache/codegraph.db
python3 .github/tools/codegraph.py impact <file> --db .github/.cache/codegraph.db
```

Group changes by module. One module = one task (default). Split further only if a single module change is too large (>200 lines).

### Step 2: Establish Dependencies
For each task pair (A, B), check:
- Does A create an interface B consumes? → B depends on A.
- Does A modify a file B reads? → B depends on A.
- No shared files? → A and B are parallelizable.

### Step 3: Assign Risk
Use the `risk-classification` skill to tag each task:
- 🟢 Additive (new files, tests)
- 🟡 Existing logic (modify behavior)
- 🔴 Critical path (auth, crypto, payments, migrations)

### Step 4: Write Task Briefs
Each task brief must be **self-contained**:
- Objective (1 paragraph)
- Files in scope (with modify/create/delete)
- Files NOT to touch (owned by other tasks)
- Codegraph envelope for context
- Acceptance criteria (testable by a command)
- Prior decisions/learnings (from memory recall)

### Step 5: Produce DAG Table

```markdown
| Task | Title | Depends On | Risk | Parallel Group | Files |
|:----:|-------|:----------:|:----:|:--------------:|-------|
| 1 | [title] | — | 🟢 | A | [files] |
| 2 | [title] | 1 | 🟡 | B | [files] |
| 3 | [title] | 1 | 🟢 | B | [files] |
| 4 | [title] | 2, 3 | 🔴 | C | [files] |

Parallel groups: A runs first, then B (tasks 2+3 in parallel), then C.
```

## Rules
- **Maximum 8 tasks.** If more, combine smaller ones.
- **No shared files between parallel tasks.** If unavoidable, serialize them.
- **Every task has acceptance criteria** that @validator can verify with a command.
- **Critical-path tasks** are never parallelized with each other.
