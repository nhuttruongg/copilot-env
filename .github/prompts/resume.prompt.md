---
description: "Resume a prior session. Load checkpoint and session context, check graph freshness, continue where you left off."
---

Resume a prior session:

## 1. Load Checkpoint
```bash
python3 .github/tools/memory.py read checkpoint --budget 1500
```

## 2. List Sessions
```bash
python3 .github/tools/session.py list
```

## 3. Resume Session
```bash
python3 .github/tools/session.py resume <session-id>
```
This prints the session log and any open tasks/results.

## 4. Check Graph Freshness
```bash
python3 .github/tools/codegraph.py why-stale --db .github/.cache/codegraph.db
```
Update if >5% stale.

## 5. Continue
Review the checkpoint and session state, then continue the work. If tasks remain, pick up from the next unfinished one.

Resume session:
