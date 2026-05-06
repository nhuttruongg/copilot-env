---
description: "Force deep planning. Skip routing — go directly to @planner with code-graph envelopes and memory recall for thorough research and plan drafting."
---

Skip complexity routing and go directly to deep planning:

## Step 1: Gather Context
```bash
python3 .github/tools/codegraph.py envelope <relevant scope> --budget 2000 --db .github/.cache/codegraph.db
python3 .github/tools/memory.py recall "<task keywords>"
python3 .github/tools/memory.py read decisions --budget 1000
```

## Step 2: Research & Plan
Invoke `@planner` to produce a full plan with:
- Problem statement
- Subtask DAG with dependencies
- Risk register
- Testable acceptance criteria
- File-level scope per task

## Step 3: Present & Pause
Present the plan. **WAIT for user approval before any implementation begins.**

Plan the following task:
