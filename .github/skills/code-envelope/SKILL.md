---
name: code-envelope
description: "Build token-budgeted context envelopes using codegraph.py envelope. Provides the right amount of context for a symbol or file without exceeding budget."
triggers:
  - "get context for"
  - "build envelope"
  - "codegraph envelope"
---

# Code Envelope

Build a token-budgeted context packet for a symbol or file using the code graph.

## What an Envelope Contains

For a **symbol**:
- Signature + docstring + body (truncated if needed)
- Direct callers (with file:line and signature)
- Direct callees
- Sibling symbols in the same file
- Related test files
- Dependency notes (imports used)

For a **file**:
- Top N symbols with signatures
- Import list
- Dependents (who imports this file)
- Related test files

## Usage

```bash
# Symbol envelope
python3 .github/tools/codegraph.py envelope <symbol_name> --budget 2000 --db .github/.cache/codegraph.db

# File envelope
python3 .github/tools/codegraph.py envelope <file_path> --budget 2000 --db .github/.cache/codegraph.db
```

Default budget: 2000 tokens (configurable in `config.yaml` → `codegraph.budgets.envelope_default_tokens`).

## Budget Allocation

The envelope allocates its token budget approximately:
- 40% — target symbol/file body
- 25% — callers/callees
- 20% — sibling context
- 15% — dependency notes + test references

If the target body alone exceeds the budget, it's truncated with `[... truncated]`.

## Profile Behavior

| Profile | Envelope Behavior |
|---|---|
| `tiny` | Unavailable. Read files directly. |
| `small` | Partial: symbols + deps only (no callers/callees). |
| `medium+` | Full envelope with all sections. |

## When to Use

- `@planner`: before writing a plan, get envelopes for all files in scope
- `@implementer`: at the start of a task, get envelopes for target symbols
- `@reviewer`: to understand the blast radius of changes
- `@explorer`: to explain how a symbol fits in the architecture
