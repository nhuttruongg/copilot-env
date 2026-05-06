---
name: memory-compaction
description: "How to fold memory tiers: hot→warm→cold. Preserves key facts while meeting token budgets. Used by @scribe."
triggers:
  - "compact memory"
  - "memory over budget"
  - "fold memory tiers"
---

# Memory Compaction

Compress memory entries to fit within token budgets while preserving key facts.

## Tier Model

| Tier | Content | Style |
|---|---|---|
| **HOT** | Most recent N entries | Verbatim (unchanged) |
| **WARM** | Older entries | One paragraph per entry |
| **COLD** | Everything older | Single rolling digest |

## Compaction Procedure

### Step 1: Get Status
```bash
python3 .github/tools/memory.py status
```
Identify which kinds are over their soft budget.

### Step 2: Generate Request
```bash
python3 .github/tools/memory.py compact <kind> --target <soft_budget>
```
This writes `_compact_request.md` with:
- Current entries to fold
- Target token count
- Instructions for summarization

### Step 3: Produce Summary
Read `_compact_request.md`. Compress according to kind rules:

| Kind | Compaction Rules |
|---|---|
| **checkpoint** | Overwrite with current-state-only snapshot. No history. |
| **sessions** | Move oldest hot entries → warm (1 paragraph each). Move oldest warm → cold (merge into rolling digest). Newest stay hot. |
| **learnings** | Deduplicate similar entries. Merge related insights. Keep the actionable takeaway, drop narrative. |
| **glossary** | Deduplicate terms. Latest definition wins on conflicts. Remove obsolete terms. |
| **decisions** | **NEVER COMPACT.** Decisions are permanent records. Skip. |

### Step 4: Write Back
Write the compressed summary to a temp file, then:
```bash
python3 .github/tools/memory.py write-summary <kind> /path/to/summary.md
```
This atomically rotates tiers and verifies sizes.

### Step 5: Verify
```bash
python3 .github/tools/memory.py status
```
If still over budget, repeat Steps 2-4 (max 2 rounds).

## Preservation Rules
- **Never discard**: architectural decisions, domain definitions, critical security findings
- **Always preserve**: the actionable insight (what to do), not the narrative (how we discovered it)
- **Deduplication**: when two entries say the same thing, keep the more specific one
- **Recency bias**: when forced to choose, preserve newer entries over older ones
