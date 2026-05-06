---
name: tiered-routing
description: "Classification heuristics for INSTANT/STANDARD/DEEP routing. Used by @router."
triggers:
  - "classify complexity"
  - "routing decision"
  - "how complex is this task"
---

# Tiered Routing

Heuristics for classifying task complexity into INSTANT, STANDARD, or DEEP.

## Classification Signals

### INSTANT (implement directly, no ceremony)
All of these must be true:
- Single file affected
- ≤30 lines of change
- No public symbol changes (no API surface change)
- Not in critical path (`auth/**`, `payments/**`, `crypto/**`, `security/**`)
- Not a new feature (just a fix, tweak, or small addition)

### STANDARD (scope → implement → review)
Any of these:
- New feature with tests required
- 2-3 files affected
- Adds or modifies public API
- User didn't say "refactor", "redesign", "architecture", "migrate"

### DEEP (full pipeline: plan → batch → implement → validate)
Any of these:
- `codegraph.py impact <file>` returns >10 dependents
- Touches critical-path files (`auth/**`, `payments/**`, `crypto/**`, `security/**`, `migrations/**`)
- ≥3 distinct modules in scope
- User says "refactor", "redesign", "architecture", "migrate", "rewrite"
- Requires new architectural patterns not in existing codebase
- Cross-cutting change (affects multiple layers)

### UNCLEAR
- User intent is ambiguous
- Action: ask **one** clarifying question. Never confabulate intent.

## Profile Modifiers

| Profile | Modifier |
|---|---|
| `tiny` | Bias toward INSTANT. DEEP only on explicit user request. |
| `small` | Bias toward STANDARD. DEEP only with clear signals. |
| `medium` | Normal classification. |
| `large` / `xlarge` | Bias toward DEEP for anything touching ≥2 modules. |

## Decision Process

```
1. Check critical-path patterns → 🔴 DEEP (short-circuit)
2. Check user keywords (refactor, migrate, etc.) → DEEP
3. Count affected modules (codegraph impact) → ≥3 = DEEP
4. Count affected files → 1 file ≤30 lines = INSTANT
5. Default → STANDARD
6. Apply profile modifier
```

## Output

After classification, report:
```
🎯 Route: INSTANT / STANDARD / DEEP
📝 Reason: [one-line justification]
📊 Signals: [what triggered this classification]
```
