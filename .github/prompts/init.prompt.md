---
description: "One-shot project initialization. Runs bootstrap.sh, analyzes codebase as @scribe, writes project-context.md and checkpoint, seeds memory. Idempotent — safe to re-run."
---

Run the full initialization sequence **without pausing between steps**. Stop only on error.

## Step 1 — Bootstrap

```bash
bash .github/tools/bootstrap.sh
```

Capture output verbatim. If exit code ≠ 0, stop and report the error. Do not continue with a broken cache.

## Step 2 — Gather Codebase Facts

Run what exists; skip what doesn't:

```bash
# Project identity
cat README.md 2>/dev/null | head -60 || true
cat package.json 2>/dev/null || cat pyproject.toml 2>/dev/null || \
  cat Cargo.toml 2>/dev/null || cat go.mod 2>/dev/null || \
  cat pom.xml 2>/dev/null || true

# Directory structure
find . -maxdepth 2 \
  -not -path './.git/*' \
  -not -path './.github/.cache/*' \
  -not -path './node_modules/*' \
  -not -path './.venv/*' \
  -not -path './target/*' \
  -not -path './dist/*' \
  -not -path './build/*' \
  | sort | head -80

# Code graph (profile ≥ small only)
python3 .github/tools/codegraph.py stats \
  --db .github/.cache/codegraph.db --json 2>/dev/null || true
python3 .github/tools/codegraph.py module . \
  --db .github/.cache/codegraph.db 2>/dev/null | head -40 || true
```

## Step 3 — Write Project Context

Act as `@scribe`. Write `.github/.cache/project-context.md`.
Base every section on gathered facts — never guess. Use `_Not detected_` if absent.

Sections required: Profile · Tech Stack · Architecture · Directory Structure · Entry Points · Critical Path Files · Conventions · Commands · Recent Structural Changes (_None yet._)

## Step 4 — Seed Memory

**Checkpoint (always):**
```bash
python3 .github/tools/memory.py write checkpoint \
  "Initial setup complete. Profile: <profile>. Project: <name> — <one sentence>. Stack: <stack>. Graph: <built with N symbols / disabled>. No sessions yet."
```

**Glossary + learnings (skip for tiny):**
Extract at most 5 domain terms and 3 non-obvious constraints from README/docs:
```bash
python3 .github/tools/memory.py write glossary "TERM: definition"
python3 .github/tools/memory.py write learnings "insight"
```

**Verify:**
```bash
python3 .github/tools/memory.py status
```
All kinds must be `ok`. If over hard budget, run `/compact-memory`.

## Step 5 — Verify Checklist

| # | Check | How |
|:--:|-------|-----|
| 1 | `config.yaml` has real profile | `grep ^profile .github/config.yaml` |
| 2 | Cache dirs exist | `ls .github/.cache/memory/` |
| 3 | `codegraph.db` present (≥ small) | `ls -lh .github/.cache/codegraph.db` |
| 4 | `project-context.md` not placeholder | First heading has real project content |
| 5 | `checkpoint.md` not placeholder | `cat .github/.cache/memory/checkpoint.md` |
| 6 | Memory healthy | All kinds `ok` in `memory.py status` |

## Step 6 — Ready Report

```
╔══════════════════════════════════════════════════════╗
║  Copilot Agentic Environment — ACTIVE                ║
╚══════════════════════════════════════════════════════╝
Project:    <name>
Profile:    <profile>  (<N> files · <N> LoC)
Languages:  <list>
Graph:      <N symbols, N files  OR  disabled at tiny>
Memory:     <all ok  OR  issues>

── Routing ────────────────────────────────────────────
INSTANT   single file · ≤30 lines · no API change
STANDARD  1-3 files · new feature with tests
DEEP      multi-module · critical-path · refactor/migrate

── Daily ──────────────────────────────────────────────
New task  → describe it  (router auto-routes)
Complex   → /implement <task>
Bug       → /debug <symptom>
End day   → /end-session
Next day  → /resume
Status    → /status
```

**Environment active. Say `/implement [your first task]` or just describe what you need.**
