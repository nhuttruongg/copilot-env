---
description: "Print project status: graph stats, memory budgets, session list, profile, and active features. Shell-only — no LLM analysis needed."
---

Print the current project status:

## Profile & Config
```bash
cat .github/config.yaml | head -5
```

## Graph Stats
```bash
python3 .github/tools/codegraph.py stats --db .github/.cache/codegraph.db --json 2>/dev/null || echo "Graph not built (tiny profile or /init not run)"
```

## Graph Freshness
```bash
python3 .github/tools/codegraph.py why-stale --db .github/.cache/codegraph.db 2>/dev/null || true
```

## Memory Budgets
```bash
python3 .github/tools/memory.py status
```

## Sessions
```bash
python3 .github/tools/session.py list
```

## Checkpoint
```bash
python3 .github/tools/memory.py read checkpoint --budget 500
```

Display all results in a concise summary.
