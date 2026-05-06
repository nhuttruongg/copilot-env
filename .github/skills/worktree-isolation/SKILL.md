---
name: worktree-isolation
description: "Use git worktrees for parallel task execution. Detect existing worktrees, create new ones, verify gitignore, handle submodules. Used by @router dispatch."
triggers:
  - "parallel tasks"
  - "worktree"
  - "multiple implementers"
---

# Worktree Isolation

Isolate parallel tasks into separate git worktrees so implementers don't conflict.

## When to Use

- Deep workflow with N≥2 parallelizable tasks
- `config.yaml` → `dispatch.worktree_isolation` is `auto` (default) or `true`
- Profile is `large` or `xlarge` (auto-enabled for ≥2 parallel)

## Procedure

### Step 0: Detect Existing Worktrees
```bash
git worktree list
```
If worktrees already exist from a prior session, consider reusing them.

### Step 1: Create Worktrees
For each parallel task:
```bash
# Create a branch for the task
git checkout -b task-<N>-<slug> HEAD

# Create worktree
git worktree add .worktrees/task-<N> task-<N>-<slug>
```

### Step 2: Verify Gitignore
Ensure `.worktrees/` is in `.gitignore`:
```bash
grep -q '.worktrees/' .gitignore || echo '.worktrees/' >> .gitignore
```

### Step 3: Submodule Guard
If the repo uses submodules:
```bash
git submodule status 2>/dev/null
```
If submodules exist, initialize them in each worktree:
```bash
cd .worktrees/task-<N> && git submodule update --init
```

### Step 4: Dispatch
Print instructions for the user:
```
## Parallel Dispatch

Open N Copilot Chat windows:

| Window | Directory | Branch | Task |
|:------:|-----------|--------|------|
| 1 | .worktrees/task-1 | task-1-<slug> | Task 1: <title> |
| 2 | .worktrees/task-2 | task-2-<slug> | Task 2: <title> |

In each window, paste the task brief from:
  sessions/<id>/tasks/N.md
```

### Step 5: Merge
After all tasks complete and pass validation:
```bash
# From main working directory
git merge task-1-<slug> --no-ff
git merge task-2-<slug> --no-ff

# Clean up
git worktree remove .worktrees/task-1
git worktree remove .worktrees/task-2
git branch -d task-1-<slug> task-2-<slug>
```

## Fallback

If `git worktree` is not available (old git version):
- Use directories: `.worktrees/task-N/` as plain copies
- Manual merge via diff/patch

## Configuration

```yaml
dispatch:
  worktree_isolation: auto   # auto | true | false
  worktree_dir: .worktrees   # directory name
  max_retries_per_subtask: 2
```
