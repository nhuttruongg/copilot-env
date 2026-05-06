---
description: "Force memory compaction. @scribe compacts memory kinds that are over their soft budget by folding hot→warm→cold tiers."
---

Force memory compaction:

## 1. Check Status
```bash
python3 .github/tools/memory.py status
```

## 2. Compact Over-Budget Kinds
For each kind over its soft budget, invoke `@scribe` to compact:

```bash
python3 .github/tools/memory.py compact <kind> --target <soft_budget>
```

This produces `_compact_request.md`. Read it, produce a compressed summary preserving key facts, then:

```bash
python3 .github/tools/memory.py write-summary <kind> /path/to/summary.md
```

## Rules
- **decisions**: NEVER compact. Skip.
- **checkpoint**: Re-summarize to current state only.
- **sessions**: Hot → warm (paragraph) → cold (digest).
- **learnings**: Deduplicate, merge similar, keep actionable insights.
- **glossary**: Deduplicate terms, latest definition wins.

## 3. Verify
```bash
python3 .github/tools/memory.py status
```
Confirm all kinds are within soft budget.
