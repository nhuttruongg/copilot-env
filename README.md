# Copilot Agentic Environment

A drop-in `.github/` template that turns GitHub Copilot Chat into a full multi-agent development system — with persistent memory, a code graph, and adaptive scaling from 5-file scripts to 1TB monorepos.

## Quickstart (3 steps)

```bash
# 1. Copy into your project
cp -r .github /path/to/your-project/

# 2. Open Copilot Chat in Agent mode, type:
/init

# 3. Start working
/implement [describe your task]
```

That's it. `/init` detects your project size, builds the code graph, and seeds memory. Then describe any task — the router handles routing automatically.

---

## What you get

| Feature | What it does |
|---------|-------------|
| **Auto-routing** | Tasks are classified (INSTANT / STANDARD / DEEP) and dispatched to the right agent — no manual workflow selection |
| **Persistent memory** | Checkpoint, decisions, learnings, glossary — survive across sessions; budgeted + auto-compacted |
| **Code graph** | `codegraph.py` — symbol lookup, callers/callees, dependency blast-radius, context envelopes. SQLite, no external service |
| **Adaptive profiles** | `tiny` (< 50 files) to `xlarge` (> 50k files) — same commands, different machinery underneath |
| **TDD + verification** | Iron Law baked in: no completion claim without fresh test evidence |

---

## Agents

| Agent | Use when |
|-------|----------|
| `@router` | **Default** — paste any task |
| `@planner` | Force deep planning before coding (Opus) |
| `@architect` | Greenfield design or large-scale refactors (Opus) |
| `@implementer` | TDD code execution for one task |
| `@reviewer` | Two-stage review: spec-compliance → code-quality |
| `@validator` | Final verification gate (Opus) |
| `@explorer` | Understand code structure and data flow |
| `@cartographer` | Quick symbol/dependency lookups (Haiku) |
| `@scribe` | Memory, checkpoint, session wrap-up |
| `@debugger` | Bug investigation via Four Phases |
| `@security` | Critical-path security audit (Opus) |

At `tiny` profile, `@explorer`/`@cartographer` fall back to grep/find (no graph installed).

---

## Commands

| Command | Purpose |
|---------|---------|
| `/init` | First-run setup — idempotent, safe to re-run |
| `/implement [task]` | **Start here** for any coding task |
| `/plan [task]` | Force deep planning (skips routing) |
| `/validate [session]` | Verification gate after parallel work |
| `/debug [symptom]` | Systematic bug investigation |
| `/review` | Code review with severity findings |
| `/test` | Generate tests for existing code |
| `/security-review` | Audit critical-path files |
| `/explain [code]` | Understand how something works |
| `/refactor [scope]` | Behavior-preserving refactor |
| `/end-session` | Save checkpoint + compact memory + suggest commit |
| `/resume` | Pick up where you left off |
| `/status` | Graph stats + memory budgets + session list |
| `/recall [topic]` | Search project memory |
| `/graph [query]` | Query the code graph directly |
| `/compact-memory` | Force memory compaction |

---

## Adaptive profiles

`/init` detects your project size and activates the right feature set:

| Profile | Files | LoC | Code graph | Agents |
|---------|-------|-----|------------|--------|
| `tiny` | < 50 | < 2k | off (grep/find) | core 4 |
| `small` | < 500 | < 20k | symbols-only | + planner, scribe |
| `medium` | < 5k | < 200k | full | + validator, cartographer |
| `large` | < 50k | < 2M | full | all |
| `xlarge` | ≥ 50k | ≥ 2M | full + partial-scan | all |

Override any feature in `.github/config.yaml`:

```yaml
profile: small
features:
  code_graph: full        # override: full graph on a small project
  validator_gate: mandatory
```

---

## Daily workflow

```
Start of day  →  /resume           (loads checkpoint + last session)
New task      →  /implement [task]  (just describe it — routing is automatic)
Bug           →  /debug [symptom]
End of day    →  /end-session       (saves state, updates graph, suggests commit)
```

## Deep task workflow (DEEP routing)

```
1. /implement [complex task]
   → @planner writes plan.md with subtask DAG
   → PAUSE: review and approve

2. @router dispatches tasks/1.md … tasks/N.md
   → Open N Copilot windows, paste each brief
   → @implementer executes with TDD, @reviewer checks each

3. /validate [session-id]
   → @validator runs Iron Law: tests + lint + cross-task consistency
   → PAUSE: review validation report

4. On PASS: @scribe updates checkpoint, suggests commit
```

---

## Requirements

- Python 3.10+
- git
- GitHub Copilot Chat with Agent mode enabled

The bootstrap script creates an isolated `.venv` inside `.github/.cache/` — your system Python is untouched.

---

## How it works

```
.github/
├── agents/          11 agents (router, planner, implementer, validator, ...)
├── prompts/         16 slash commands (/init, /implement, /debug, ...)
├── skills/          13 reusable procedures (tdd, validation-gate, ...)
├── instructions/    Path-scoped style guides (auto-applied by Copilot)
├── tools/           Python tools (codegraph.py, memory.py, session.py, bootstrap.sh)
└── .cache/          Generated cache — gitignored
    ├── codegraph.db     SQLite code graph (symbols, refs, deps)
    ├── memory/          Layered memory with auto-compaction
    └── sessions/        Per-session work logs
```

All state lives in `.github/.cache/`, which is gitignored. Wipe it to start fresh:

```bash
rm -rf .github/.cache/
/init
```
