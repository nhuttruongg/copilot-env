# Copilot Agentic Orchestration — Design Spec

**Date:** 2026-05-05
**Status:** Approved for implementation planning
**Target:** GitHub Copilot Chat (Agent mode)
**Scope:** Enhance the global `.github/` template so a single `cp -r .github` + one `/init` prompt activates a full multi-agent system capable of handling 1TB codebases and complex multi-phase tasks.

---

## 1. Goals and Non-Goals

### Goals

1. **Scale both directions.** Handle very large codebases (~1TB / ~5M files) without exhausting agent context, *and* stay lightweight on tiny/small projects where heavy machinery would be overkill. A 5-file script must not pay the cost of the 1TB design.
2. Decompose complex tasks into a parallelizable DAG, dispatch to focused implementers, and merge through a powerful validator gate.
3. Persist project understanding across sessions via a layered memory system with bounded size and auto-compaction.
4. Match model tier to task complexity (Haiku → Sonnet → Opus) with explicit cost discipline (default planning model is Opus 4.6, not 4.7).
5. Enforce TDD, systematic debugging, and verification-before-completion as hard rules — inherited from the superpowers plugin.
6. Stay pure-Copilot — no external API keys required, no out-of-band LLM calls. All summarization happens in the active chat by passing the active model a request file.
7. Be portable — drop the `.github/` folder into any project and run `/init` once. No global state, no account-level changes.

### Non-Goals

- Cross-platform support (Cursor, Codex, etc.). This release targets Copilot only. AGENTS.md retained as a courtesy, not a primary surface.
- True wall-clock parallel LLM execution. "Parallel" means N independent task briefs the user runs in N Copilot windows, not N concurrent subprocess agents.
- A managed indexing service. Code graph is a single Python script + SQLite file in `.github/.cache/`.
- Replacing Copilot's `@workspace` or any built-in command. The system layers on top.

---

## 2. Architecture Overview

Three layers, strict downward-only reads.

```
┌──────────────────────────────────────────────────────────────────────┐
│ LAYER 3 — ORCHESTRATION (agents, prompts, skills)                    │
│   @router → decompose → @planner → task-batch → N×@implementer       │
│           → @validator (gate) → merge                                │
└──────────────┬───────────────────────────────────────────────────────┘
               │ reads: graph queries, session memory
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ LAYER 2 — KNOWLEDGE (.github/.cache/)                                │
│   codegraph.db (SQLite)   ← code graph: symbols, refs, deps, impact  │
│   project-context.md      ← living project map (auto-updated)        │
│   sessions/<id>/          ← per-session: plan, tasks, results, log   │
│   memory/                 ← layered checkpoint, decisions, learnings │
└──────────────┬───────────────────────────────────────────────────────┘
               │ produced/maintained by
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ LAYER 1 — TOOLS (.github/tools/, shell-invokable)                    │
│   codegraph.py    scan | update | find | refs | deps | impact | ...  │
│   memory.py       write | read | search | recall | status | compact  │
│   session.py      start | log | save | end | resume                  │
│   bootstrap.sh    one-shot init: scan + write project-context        │
└──────────────────────────────────────────────────────────────────────┘
```

### Data flow for a deep-complexity task

1. User invokes `/implement <task>` → activates `@router`.
2. `@router` runs `memory.py read checkpoint`, `codegraph.py why-stale`, `memory.py recall <keywords>`. Classifies complexity.
3. If DEEP: delegates to `@planner` (Opus 4.6) which writes `sessions/<id>/plan.md` (problem statement, subtask DAG, risk register, acceptance criteria).
4. **PAUSE 1** — user reviews and approves the plan.
5. `@router` writes `sessions/<id>/tasks/{1..N}.md` — one self-contained brief per subtask.
6. User opens N Copilot windows (optionally in N git worktrees), each pastes its brief → `@implementer` (Sonnet 4.6) executes one task with TDD discipline.
7. Per task: `@reviewer` runs spec-compliance review, then code-quality review. Failures loop back to implementer.
8. When all tasks complete: user runs `/validate <session-id>` → `@validator` (Opus 4.6) runs the global verification gate (tests, lint, type-check, code cleanliness, cross-task consistency, probe tests for uncovered edges).
9. **PAUSE 2** — user reviews validation report.
10. On PASS: `@scribe` (Sonnet 4.6) updates `checkpoint.md`, `project-context.md`, runs `codegraph.py update`, runs memory compaction if budgets exceeded, suggests commit message.
11. On FAIL: `@router` re-issues briefs for failed subtasks only; back to step 6.

Mandatory pauses are **only** Phase 1 (plan) and Phase 4 (validation). All else is continuous to avoid wasting the user's attention.

---

## 2.5. Adaptive Profiles — scaling down as well as up

The system targets a 1TB codebase ceiling but must not impose that overhead on a 50-file script. `/init` detects project size and writes a **profile** to `config.yaml`; tools and agents check the profile and gate features accordingly. Same `/implement`, `/explain`, agent personalities — different machinery underneath.

### Five profiles

| Profile | LoC | Files | Trigger |
|---|---|---|---|
| **tiny** | < 2k | < 50 | Throwaway scripts, exploration |
| **small** | 2k – 20k | 50 – 500 | Single app, single team |
| **medium** | 20k – 200k | 500 – 5k | Real product, single repo |
| **large** | 200k – 2M | 5k – 50k | Big monorepo or mature codebase |
| **xlarge** | > 2M | > 50k | Massive monorepo (the 1TB case) |

Detection runs in `bootstrap.sh`:
```bash
files=$(git ls-files 2>/dev/null | wc -l)
loc=$(git ls-files | xargs -r wc -l 2>/dev/null | tail -1 | awk '{print $1}')
# pick profile by thresholds; write to .github/config.yaml
```

If outside a git repo, fall back to `find . -type f` filtered by ignore patterns. If `loc` cannot be computed (binary-heavy repo), file count alone decides.

### Feature activation matrix

| Feature | tiny | small | medium | large | xlarge |
|---|---|---|---|---|---|
| **Code graph** | off (grep/find only) | symbols-only (no refs/calls) | full | full | full + partial-scan |
| **Tree-sitter parsers** | none installed | only languages detected | tier1 set | tier1 set | tier1 + opt-in tier2 |
| **Memory kinds active** | checkpoint only | + learnings + glossary | all | all | all + per-session forced compact |
| **Compaction** | off | on-demand only | auto on session-end | auto | auto + forced |
| **Agents available** | router, implementer, debugger, reviewer | + planner, scribe, explorer | + validator, cartographer, security | all | all + architect bias |
| **Default routing bias** | INSTANT — implement directly | STANDARD | STANDARD; DEEP for complex | DEEP for complex | DEEP unless trivial |
| **Multi-task decomposition** | never | only on explicit user request | for DEEP tasks | for DEEP tasks | DEEP + ≥2 modules ⇒ always decompose |
| **Validator gate (`/validate`)** | optional | optional | mandatory after DEEP | mandatory | mandatory |
| **Worktree isolation** | off | off | off | auto for ≥2 parallel | always for ≥2 parallel |
| **Bootstrap deps installed** | none (stdlib only) | tree-sitter-language-pack | tier1 parsers + sqlite-utils | tier1 + sqlite-utils | tier1 + sqlite-utils + git-tooling |
| **`/init` wall-clock budget** | < 1 s | < 30 s | < 5 min | < 15 min | 15 – 60 min |
| **`.github/.cache/` size budget** | < 10 KB | < 5 MB | < 100 MB | < 1 GB | unbounded |

### Tool behavior by profile

- **`codegraph.py`** reads `config.yaml profile` on first call.
  - `tiny`: returns a stub message — "graph disabled at this profile; agents should use grep/find"; `find`/`refs`/`envelope` exit cleanly with a fallback hint.
  - `small`: builds and queries `symbols` and `files` tables only; `refs`/`callers`/`callees` return "not indexed at this profile".
  - `medium+`: full schema, full features.
- **`memory.py`** is always lightweight; it works identically on every profile, but the active kinds differ.
- **Agents** include a profile-check at the top of their prompts. Steps that don't apply at the active profile are skipped (e.g., `@implementer` skips the "fetch codegraph envelope" step on `tiny` and reads files directly).
- **Skills** reference the profile when a step is profile-conditional; otherwise they're identical across profiles.

### Per-feature overrides

`profile` sets defaults; users can override individual features in `config.yaml` without abandoning the profile:

```yaml
profile: small
features:
  code_graph: full          # override: full graph even on small project
  validator_gate: mandatory # override: always require validator
```

This handles edge cases (a small project with critical-path code wants the full validator; a medium repo with mostly-generated code wants graph off).

### Upgrade and downgrade

- **Upgrade**: `/status` prints current profile and warns when LoC/file-count crosses the next threshold. `/upgrade-tier` runs the next tier's setup (additional deps, full scan, activate gated features). Idempotent.
- **Downgrade**: edit `config.yaml`, run `/upgrade-tier --to=<lower>`. Tool prompts before deleting cache content that the lower tier doesn't need.

### Why a profile, not just feature flags

Feature flags alone force the user to understand the whole system before deciding which to enable. A profile is a single dial that activates a *coherent* feature set known to work together. Per-feature overrides remain available for the rare case where defaults don't fit.

### Acceptance for adaptive design

- A 5-file Python script: `/init` completes in < 1 s, installs no Python deps, `.github/.cache/` is < 10 KB, `/implement` works without any code-graph queries.
- A 20k-LoC Next.js app: `/init` installs only the TS+TSX parser, scan completes in < 30 s, decomposition not triggered automatically.
- A 200k-LoC monorepo: full system active, validator mandatory after DEEP tasks.
- The 1TB case: all features + xlarge defaults.

---

## 3. Layer 1 — Tools

All tools are pure Python (memory.py, codegraph.py, session.py) plus one shell script (bootstrap.sh). They run inside a project-local virtualenv at `.github/.cache/.venv` to avoid polluting the user's Python environment.

### 3.1 codegraph.py

**Purpose:** Build and query a persistent code graph using tree-sitter parsers and SQLite storage. Replaces re-reading the codebase.

**SQLite schema:**

```sql
CREATE TABLE files (
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE,
  lang TEXT,
  sha256 TEXT,
  mtime REAL,
  line_count INTEGER,
  parse_error INTEGER DEFAULT 0
);
CREATE TABLE symbols (
  id INTEGER PRIMARY KEY,
  file_id INTEGER REFERENCES files(id),
  name TEXT,
  qualified_name TEXT,
  kind TEXT,            -- func | class | method | var | type | const
  start_line INTEGER,
  end_line INTEGER,
  signature TEXT,
  docstring TEXT,
  visibility TEXT       -- public | private | internal
);
CREATE TABLE imports (
  id INTEGER PRIMARY KEY,
  from_file_id INTEGER REFERENCES files(id),
  to_module TEXT,
  imported TEXT,
  alias TEXT,
  line INTEGER
);
CREATE TABLE calls (
  id INTEGER PRIMARY KEY,
  caller_symbol_id INTEGER REFERENCES symbols(id),
  callee_name TEXT,
  callee_symbol_id INTEGER REFERENCES symbols(id), -- nullable, resolved best-effort
  line INTEGER
);
CREATE TABLE refs (
  id INTEGER PRIMARY KEY,
  symbol_id INTEGER REFERENCES symbols(id),
  file_id INTEGER REFERENCES files(id),
  line INTEGER,
  kind TEXT             -- read | write | type-annotation
);
CREATE VIRTUAL TABLE symbols_fts USING fts5(name, qualified_name, signature, docstring, content='symbols');
CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_files_path ON files(path);
CREATE INDEX idx_imports_to ON imports(to_module);
CREATE INDEX idx_calls_callee ON calls(callee_name);
```

**CLI surface:**

```
codegraph.py scan [--root .] [--exclude PATTERN]
codegraph.py update                                 # incremental on git diff or mtime
codegraph.py find <name> [--kind=func] [--lang=py]
codegraph.py refs <symbol-id|name>
codegraph.py callers <symbol>
codegraph.py callees <symbol>
codegraph.py deps <file>                            # imports of file
codegraph.py impact <file> [--depth=2]              # reverse deps (blast radius)
codegraph.py module <path>
codegraph.py search "<query>" [--limit=20]         # FTS over name+sig+docstring
codegraph.py envelope <symbol|file> [--budget=2000] # build context envelope (the killer command)
codegraph.py stats
codegraph.py why-stale [--check-git]
```

**The `envelope` command** is the primary way agents fetch context. Given a symbol or file and a token budget, it returns markdown containing: the symbol's signature + docstring + body (truncated if needed), direct callers (with file:line and signature), direct callees, sibling symbols, related test files, dependency notes. Token-budgeted to a target size — never exceeds the budget.

**Languages:**
- Tier 1 (bundled, tested): Python, JavaScript, TypeScript, TSX, Go, Java, Rust, C, C++.
- Tier 2 (opt-in via `config.yaml`): Ruby, PHP, Kotlin, Swift, Scala, C#, Elixir, Lua, Bash, SQL.

Parsers come from `tree-sitter-language-pack` (single dependency, ~50 languages bundled).

**Performance targets (1TB monorepo):**

| Operation | Target |
|---|---|
| Full scan, 1TB / ~5M files | 15–30 min using multiprocessing pool, 5k-row SQLite batches, default exclusions for `.git`, `node_modules`, `dist`, `build`, `.venv`, `target`, `vendor` |
| Incremental update | < 30s for typical commit, via `git diff HEAD@{last_scan}` with mtime fallback |
| `find` / `refs` / `callers` | < 100ms (indexed lookups) |
| `impact` depth 3 | < 500ms (recursive CTE on `imports`) |
| `envelope` | < 500ms |

**Failure modes:**
- Tree-sitter parse error → record `parse_error=1`, continue, surface in `stats`.
- SQLite WAL lock contention → 5s retry with backoff; reads use immutable snapshots.
- Stale graph (>5% files mtime newer than scan) → `why-stale` warns; `@router` runs `update` automatically at session start.
- Symbol resolution ambiguity → use fully-qualified `module.Class` ids; `find` returns all matches with disambiguation context.

**Configuration** (`.github/config.yaml`):

```yaml
codegraph:
  exclude:
    - "**/node_modules/**"
    - "**/.venv/**"
    - "**/dist/**"
    - "**/build/**"
    - "**/target/**"
    - "**/.git/**"
    - "**/vendor/**"
  languages:
    tier1: [python, javascript, typescript, tsx, go, java, rust, c, cpp]
    tier2: []
  budgets:
    envelope_default_tokens: 2000
    impact_max_depth: 3
  scan:
    workers: auto
    batch_size: 5000
```

### 3.2 memory.py

**Purpose:** Read/write interface for layered memory with auto-compaction. Agents never write memory files directly; they go through this CLI which enforces budgets and triggers compaction.

**Memory kinds and budgets:**

| Kind | Purpose | Soft budget | Hard budget | Compaction policy |
|---|---|---|---|---|
| `checkpoint` | Current project state, overwritten each session-end | 2k tok | 4k tok | Re-summarize, no history kept |
| `sessions` | Per-session work log | 8k hot | 16k hot | Hot → warm → cold tier rotation |
| `decisions` | Architectural decisions (DEC-NNN), one file per decision | ∞ | ∞ | Never compacted, dedupe only |
| `glossary` | Domain terms learned | 4k | 8k | Dedupe + cold-fold older defs |
| `learnings` | Non-obvious gotchas, fixes, patterns | 4k | 8k | Dedupe + cold-fold |

Tokens approximated as `chars / 4` (no tokenizer dependency). Override per-project in `.github/config.yaml`.

**Layered storage** (per kind, where applicable):
- **HOT** — most recent N entries, verbatim.
- **WARM** — older entries, each compressed to one paragraph.
- **COLD** — everything older, folded into a single rolling digest.

**CLI surface:**

```
memory.py write <kind> <content>
memory.py read <kind> [--budget=N]              # hot first, then warm, then cold, up to budget
memory.py search "<query>" [--kind=...]         # FTS over all tiers
memory.py recall "<topic>"                      # ranked retrieval across decisions+learnings+glossary
memory.py status                                 # report size vs budget per kind, exit nonzero if over hard
memory.py compact <kind> [--target=N]            # produce compaction prompt for active agent
memory.py write-summary <kind> <file>            # @scribe writes summary back, tool rotates tiers atomically
memory.py forget <id>                            # explicit delete
```

**Auto-compaction flow** (no API key needed):

```
1. Trigger fires (session end | session start over budget | /compact-memory)
2. memory.py status reports kind X over soft budget
3. memory.py compact X --target 2k
   → writes .github/.cache/memory/_compact_request.md with chunks to fold + instructions
4. Active agent (or @scribe — Sonnet 4.6) reads _compact_request.md, produces summary
   in-chat using whatever model is loaded, then runs:
   memory.py write-summary X /path/to/output.md
5. Tool atomically rotates: oldest hot → warm, oldest warm → cold; verifies new sizes
   under budget; deletes the request file
6. If still over after one round, queue another
```

**Token-budgeted reads** — `memory.py read sessions --budget 2000` returns hot entries until ~70% of budget, warm until ~90%, then cold digest. Always fits.

**File layout** under `.github/.cache/memory/`:

```
memory/
├─ checkpoint.md
├─ decisions/
│  ├─ DEC-001-auth-strategy.md
│  └─ DEC-002-graph-schema.md
├─ sessions/
│  ├─ 2026-05-05-1430.md      # hot
│  ├─ 2026-05-04-0900.md      # hot
│  ├─ _warm.md                 # paragraph-per-entry summaries
│  └─ _cold.md                 # rolling all-time digest
├─ glossary.md
├─ learnings.md
└─ _compact_request.md         # transient
```

**Compaction model:** Sonnet 4.6 (chosen for summary quality over speed).

### 3.3 session.py

**Purpose:** Manage session lifecycle and the `sessions/<id>/` directory.

```
session.py start [--label=<short-label>]    # creates sessions/<YYYY-MM-DD-HHMM-label>/
session.py log <event-type> <message>       # append to sessions/<id>/log.md
session.py save                              # snapshot current state
session.py end [--archive-after-days=7]      # invoke @scribe path
session.py resume <id>                       # load prior session into context
session.py list [--since=DATE]
session.py archive [--days=7]                # move stale sessions to cold storage
```

### 3.4 bootstrap.sh

One-shot environment setup. Idempotent — re-running detects existing cache and prompts to refresh vs preserve. Bash cannot invoke chat agents; bootstrap.sh prepares the environment and runs the scan, then the `/init` prompt continues by activating `@scribe` in chat to write project-context.md and seed glossary.

```
bootstrap.sh
  → python -m venv .github/.cache/.venv
  → pip install tree-sitter-language-pack sqlite-utils
  → mkdir -p .github/.cache/{memory/{decisions,sessions},logs}
  → touch placeholder memory files
  → codegraph.py scan
  → report graph stats and ready status; exit 0
# control returns to Copilot chat — /init then activates @scribe
```

---

## 4. Layer 2 — Knowledge

### 4.1 `.github/.cache/` directory layout

```
.github/.cache/                         # gitignored
├─ codegraph.db                         # SQLite store
├─ codegraph.json                       # human-readable summary (stats, exclusions, languages)
├─ memory/                               # see §3.2
├─ sessions/
│  └─ <YYYY-MM-DD-HHMM-label>/
│     ├─ plan.md                        # @planner output: DAG, risks, acceptance criteria
│     ├─ tasks/
│     │  ├─ 1-<slug>.md                 # @router-generated brief
│     │  └─ 2-<slug>.md
│     ├─ results/
│     │  ├─ 1.done.md                   # @implementer report (status code + diff summary)
│     │  └─ 2.done.md
│     ├─ reviews/
│     │  ├─ 1-spec.md                   # @reviewer spec-compliance result
│     │  ├─ 1-quality.md                # @reviewer code-quality result
│     │  └─ ...
│     ├─ validation.md                  # @validator final report
│     └─ log.md                         # session event log
├─ logs/
└─ .venv/                                # isolated Python env
```

### 4.2 `project-context.md`

A living project map written by `@scribe` at `/init` and updated at `/end-session` when structural changes occur. Contains: tech stack, architecture pattern, directory map, entry points, conventions, testing setup, build commands, and a "Recent structural changes" tail (last 5 entries).

### 4.3 Task brief format (`sessions/<id>/tasks/N.md`)

```markdown
---
task_id: 2
session_id: 2026-05-05-1430
agent: implementer
model_tier: standard          # claude-sonnet-4-6
depends_on: [1]
blocks: [4, 5]
risk: 🟡
---

# Task 2 — <one-line title>

## Objective
<one paragraph>

## Files in scope
- src/auth/session.py             (modify)
- tests/auth/test_session.py      (extend)

## DO NOT touch
- src/auth/login.py, src/auth/logout.py — owned by Task 1
- src/db/migrations/**            — owned by Task 3

## Code-graph context envelope
<<< auto-generated by `codegraph.py envelope auth.refresh_session --budget 1500` >>>

## Acceptance criteria (testable)
1. `test_refresh_rotates_token` — after refresh, old RT is rejected
2. `test_refresh_idempotency_within_grace` — concurrent refreshes within 5s use same new RT
3. Lint + type-check pass
4. No new public symbols added

## Notes from prior decisions (auto-recalled)
- DEC-001: tokens stored as bcrypt hash, never plaintext
- Learning 2026-04-12: oauth library quirk with leeway parameter

## Discipline reminders
- TDD: NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST. Watch each test fail
  for the expected reason before implementing.
- On completion, write status code (DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED)
  to results/2.done.md.
```

---

## 5. Layer 3 — Orchestration

### 5.1 Routing decision

`@router` is the entry point for `/implement`. It runs the following at session start:

```
memory.py read checkpoint --budget 1500
codegraph.py why-stale && (codegraph.py update if needed)
memory.py recall "<keywords from request>"
```

Then classifies:

| Signal | Classification |
|---|---|
| Single file, ≤30 lines, no public symbol changes | INSTANT |
| New feature with tests required | STANDARD minimum |
| `codegraph impact <file>` returns >10 dependents | DEEP |
| Touches `auth/**`, `payments/**`, `crypto/**`, `security/**`, `migrations/**` | DEEP (always) |
| ≥3 distinct modules in scope | DEEP |
| User says "refactor", "redesign", "architecture", "migrate" | DEEP |
| User intent unclear | UNCLEAR — one clarifying question, never confabulate |

Routes:
- INSTANT → implement directly (Sonnet, no ceremony).
- STANDARD → `/implement` workflow: scope → implement → review (Sonnet).
- DEEP → full pipeline (`@planner` → task-batch → N×`@implementer` → `@validator`).

### 5.2 Deep workflow — phase-by-phase

**Phase 1: Plan** (sequential, gated)
- `@planner` (Opus 4.6) reads codegraph envelopes for scope, `memory.py recall` for prior decisions.
- Writes `plan.md`: problem statement, success criteria, subtask DAG, risk register, acceptance tests.
- **PAUSE — user approves.**

**Phase 2: Dispatch**
- `@router` writes `tasks/{1..N}.md` from plan.
- Prints dispatch table: which tasks parallelizable, which serial; suggested worktree commands if `dispatch.worktree_isolation: true` and N≥2.

**Phase 3: Parallel implementation**
- User opens N Copilot windows.
- Each window: `@implementer` (Sonnet 4.6) executes one brief with TDD discipline (Iron Law in §5.4).
- Implementer reports one of: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED`.
- Per task, two-stage review:
  1. `@reviewer` in spec-compliance mode — does code match brief? extras? gaps?
  2. `@reviewer` in code-quality mode — convention drift, dead code, test smells.
- Failures loop back to implementer; re-review after fix.

**Phase 4: Validation gate** (the powerful agent)
- User runs `/validate <session-id>` → `@validator` (Opus 4.6).
- Validator inherits the **Iron Law from `verification-before-completion`** verbatim:
  > NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE. If you haven't run the verification command in this message, you cannot claim it passes.
- Procedure:
  1. Read `plan.md` and all `results/*.done.md`.
  2. For each acceptance criterion, run the proving command in this session, capture stdout/exit code, mark ✅ only with that evidence.
  3. Run full test suite, lint, type-check; capture each output.
  4. Code-cleanliness audit: dead code, unused imports, leaked TODOs, convention drift vs `project-context.md`. 🔴 critical-path files reviewed line-by-line; auto-invoke `@security` if touched.
  5. Cross-task consistency: interfaces between tasks match.
  6. Generate probe tests for uncovered edge cases; run them.
  7. Write `validation.md` with verification log + verdict (`PASS` | `FAIL` | `NEEDS-REWORK <task-ids>`).
- **PAUSE — user reviews validation report.**

**Phase 5: Merge & checkpoint**
- On PASS: `@scribe` updates `checkpoint.md`, `project-context.md`; runs `codegraph.py update`; runs memory compaction if any kind over soft budget; suggests conventional commit message; archives session.
- On FAIL/NEEDS-REWORK: `@router` re-issues briefs for failed subtasks only; back to Phase 3. Convergence guarantee: max 2 retries per subtask, then escalate to user.

### 5.3 Convergence guarantees

- **Max retries per subtask:** 2. After that, validator escalates with diagnosis; human decides rescope vs accept partial.
- **Plan immutability after Phase 1 approval.** Implementers don't pivot mid-flight; if discovery contradicts plan, write `BLOCKED.md` and re-run `@planner` with that input.
- **Session timeout.** Sessions older than 7 days auto-archive; require explicit `session.py resume` to revive.

### 5.4 Inherited disciplines (from superpowers)

These rules are baked into agent prompts and skill files, not optional.

| Discipline | Source skill | Inherited by |
|---|---|---|
| **Verification Iron Law** — no completion claims without fresh evidence | `verification-before-completion` | `@validator`, `validation-gate` skill |
| **TDD Iron Law** — no production code without a failing test first; watch it fail for the expected reason | `test-driven-development` | `@implementer`, `tdd` skill |
| **Systematic debugging Four Phases** — root cause → pattern → hypothesis → fix; 3+ failed fixes ⇒ question architecture | `systematic-debugging` | `@debugger`, `systematic-debugging` skill |
| **Parallel dispatch principles** — one agent per independent domain, self-contained briefs, specific output format, no shared state | `dispatching-parallel-agents` | task-batch in Phase 2 |
| **Two-stage per-task review** — spec compliance first, then code quality | `subagent-driven-development` | `@reviewer` (called twice with different modes) |
| **Continuous execution between gates** — no "should I continue?" prompts | `subagent-driven-development` | `@router` Phase 3 loop |
| **Worktree isolation** — detect existing → native tool → fallback to `.worktrees/`; submodule guard; gitignore verification | `using-git-worktrees` | new `worktree-isolation` skill, dispatch table |
| **Receiving review** — verify before agreeing, no performative agreement | `receiving-code-review` | `@implementer` when `@reviewer` pushes back |

### 5.5 Pause discipline

Mandatory pauses are **only** Phase 1 (plan approval) and Phase 4 (validation report). Phase 2, 3, 5 run continuously. Rationale: rework cost is asymmetric only at those two points (a wrong plan wastes hours; a missed validation issue ships bugs); other phases are mechanical.

---

## 6. Agents

11 agents. Each has frontmatter declaring model, tier, and skills it inherits.

| Agent | Model | Tier | Role | Status |
|---|---|---|---|---|
| `@router` | claude-sonnet-4-6 | std | Entry point. Classify, route, decompose, dispatch. | new (extends `@conductor`) |
| `@planner` | claude-opus-4-6 | think | Deep research + plan with DAG and risk register. | enhanced |
| `@architect` | claude-opus-4-6 | think | Greenfield design / large refactors. | new |
| `@implementer` | claude-sonnet-4-6 | std | TDD execution within one task brief. Strict scope guard. | enhanced |
| `@debugger` | claude-sonnet-4-6 | std | Reproduce → bisect (codegraph) → root cause → fix. | enhanced |
| `@reviewer` | claude-sonnet-4-6 | std | Two-stage per-task review (spec, then quality). | enhanced |
| `@validator` | claude-opus-4-6 | think | **Final gate** — verification Iron Law, cross-task audit, probe tests. | new |
| `@explorer` | claude-haiku-4-5 | fast | Code understanding via codegraph (no full reads). | enhanced |
| `@cartographer` | claude-haiku-4-5 | fast | Code-graph queries on demand for any agent. | new |
| `@scribe` | claude-sonnet-4-6 | std | Memory compaction, checkpoint, project-context. | new |
| `@security` | claude-opus-4-6 | think | 🔴 critical-path audit. Auto-invoked by validator on auth/crypto/payments. | new |

### Model fallbacks

If an Anthropic model is temporarily unavailable in Copilot, agents document a fallback:

- Fast tier: GPT-4.1
- Standard tier: GPT-5.3-Codex (or Sonnet 4.5)
- Thinking tier: GPT-5.5

The agent works correctly on the fallback model — no behavior depends on Anthropic-specific capabilities.

### Routing for cost discipline

- Default planner is Opus 4.6 (confirmed user preference; Opus 4.7 reserved for explicit `@planner-deep` invocation).
- `@cartographer` and `@explorer` deliberately use Haiku 4.5 to make graph queries cheap — they're called frequently.
- `@scribe` runs Sonnet 4.6 for compaction quality.
- Fallback list documented per-agent.

---

## 7. Prompts (slash commands)

16 prompts. Each lives at `.github/prompts/<name>.prompt.md`.

| Prompt | Calls | Purpose |
|---|---|---|
| `/init` | bootstrap.sh + `@scribe` | One-shot: scan, build graph, write project-context. Replaces `INIT-PROMPT.md`. |
| `/implement` | `@router` (auto-routes by complexity) | Default entry point. |
| `/plan` | `@planner` directly | Skip routing, force deep planning. |
| `/validate <session>` | `@validator` | Run final gate on a completed session. |
| `/explain` | `@explorer` | Code understanding via graph. |
| `/debug` | `@debugger` | Bug investigation, Four Phases. |
| `/refactor` | `@planner` → `@implementer`×N → `@validator` | Large refactor pipeline. |
| `/review` | `@reviewer` (single-task) or `@validator` (multi-task) | Quality check. |
| `/test` | `@implementer` in TDD-only mode | Generate tests for existing code. |
| `/security-review` | `@security` | Critical-path audit. |
| `/end-session` | `@scribe` | Update checkpoint, compact memory, archive session. |
| `/resume [session-id]` | `@router` with prior session loaded | Pick up where left off. |
| `/compact-memory` | `@scribe` | Force memory compaction. |
| `/recall <topic>` | `memory.py recall` (no LLM) | Quick search across memory. |
| `/graph <query>` | `codegraph.py` (no LLM) | Quick code-graph query. |
| `/status` | shell-only | Print graph stats, memory budgets, session list. |

---

## 8. Skills

13 skills under `.github/skills/<name>/SKILL.md`. Skills are reusable procedures invoked from inside agents, not directly by user. Each follows the superpowers SKILL.md format (frontmatter with specific trigger description; "Iron Law" or "Gate Function" if applicable; red flags; ✅/❌ examples).

| Skill | Used by | Purpose | Status |
|---|---|---|---|
| `codebase-scan` | bootstrap.sh, `/init` | Initial full scan + project-context generation | enhanced |
| `context-gather` | `@router`, `@planner` | Build context envelope for a task using codegraph | enhanced |
| `tdd` | `@implementer` | Red-Green-Refactor with watched-fail Iron Law | enhanced (verbatim from superpowers) |
| `security-review` | `@security`, `@validator` | Critical-path audit checklist | enhanced |
| `task-decomposition` | `@planner` | Break task into DAG; the algorithm | new |
| `risk-classification` | `@planner`, `@validator` | 🟢🟡🔴 file risk rubric | new |
| `validation-gate` | `@validator` | Verification Iron Law procedure | new |
| `memory-compaction` | `@scribe` | How to fold hot→warm→cold | new |
| `code-envelope` | `@cartographer`, `@planner` | Build token-budgeted envelopes | new |
| `session-checkpoint` | `@scribe` | What to write at session end | new |
| `tiered-routing` | `@router` | Classification heuristics | new |
| `systematic-debugging` | `@debugger` | Four Phases (verbatim from superpowers) | new |
| `worktree-isolation` | `@router` dispatch | Step 0 detect → native → `.worktrees/` fallback | new |

---

## 9. Path-scoped instructions

7 instruction files under `.github/instructions/`. Existing four kept as-is, three new added.

| File | Glob | Purpose | Status |
|---|---|---|---|
| `python.instructions.md` | `**/*.py` | Python style and idioms | kept |
| `typescript.instructions.md` | `**/*.{ts,tsx}` | TS style | kept |
| `react.instructions.md` | `**/*.{tsx,jsx}` | React patterns | kept |
| `testing.instructions.md` | `**/*.{test,spec}.*` | Testing conventions | kept |
| `monorepo.instructions.md` | `**/{packages,apps,services}/**` | Workspace-aware scope-narrowing | new |
| `migration.instructions.md` | `**/migrations/**` | Auto-flag 🔴, require `@security` | new |
| `critical-path.instructions.md` | `**/{auth,payments,crypto,security}/**` | Force `@security` involvement | new |

---

## 10. Init bootstrap and session lifecycle

### 10.1 `/init` — first-run only

A single user-pasteable prompt activates `@router`, which runs:

1. `bootstrap.sh`:
   - **detect profile** (file count, LoC, languages, monorepo markers); write `profile: <tier>` to `.github/config.yaml`.
   - **profile-conditional venv & deps**: `tiny` skips venv entirely (stdlib only); `small` installs tree-sitter only for detected languages; `medium+` installs the full tier1 parser pack + `sqlite-utils`.
   - `mkdir -p .github/.cache/{memory/{decisions,sessions},logs}`
   - touch placeholder memory files for the kinds active at this profile.
2. `codegraph.py scan` — behavior depends on profile:
   - `tiny` → no-op stub (graph disabled).
   - `small` → symbols-only scan into `codegraph.db`.
   - `medium+` → full scan with workers/batch settings from `config.yaml`.
3. `@scribe` (Sonnet 4.6) writes:
   - `.github/project-context.md` (profile reflected in tech-stack section).
   - `.github/.cache/memory/checkpoint.md` (initial state snapshot).
   - `.github/.cache/memory/glossary.md` (seeded from README/docs) — only if profile ≥ small.
4. Reports: detected profile, graph stats (or "disabled at tiny"), languages found, exclusions used, active feature set, ready status.

Idempotent — re-running detects existing cache and offers to refresh vs preserve. If profile detection produces a different tier than what's in `config.yaml`, prompt before changing.

### 10.2 Session lifecycle

**Session start (any new chat):**
- `@router` activates by default (recommend setting it as VS Code default chat mode).
- Auto: `memory.py status`, `codegraph.py why-stale`, optional `codegraph.py update`.
- Reads `checkpoint.md --budget 1500`.
- Greets with current state: "Last session ended mid-rework on Task 2; resume?"

**Mid-session:**
- Any agent can call `memory.py write learnings|glossary|decisions ...`
- `codegraph.py update` runs after any non-trivial set of edits (cheap).
- Session log appended to `sessions/<id>/log.md`.

**Session end (`/end-session`):**
- `@scribe` consolidates `sessions/<id>/log.md` into a session summary.
- Updates `checkpoint.md` (overwrite) with current state.
- Updates `project-context.md` if structural changes occurred.
- Runs `memory.py status`; if any kind over soft budget, compacts via Sonnet 4.6.
- Runs `codegraph.py update`.
- Suggests conventional commit message.
- Archives session if older than 7 days.

### 10.3 Auto-update hooks (opt-in)

A `.vscode/tasks.json` template is provided (not enforced):

- On save of any tracked source file: debounced `codegraph.py update --quiet --files <changed>` (1–2s).
- On chat session close: prompt user with `/end-session` reminder.

User copies the template if they want it.

---

## 11. File layout (final tree)

`[K]` = keep, `[E]` = enhance, `[N]` = new, `[D]` = delete.

```
.github/
├─ copilot-instructions.md                    [E] +memory/graph/router instructions
├─ config.yaml                                 [N] codegraph + memory budgets
│
├─ agents/
│  ├─ router.agent.md                         [N] (renames + extends conductor)
│  ├─ planner.agent.md                        [E]
│  ├─ architect.agent.md                      [N]
│  ├─ implementer.agent.md                    [E]
│  ├─ debugger.agent.md                       [E]
│  ├─ reviewer.agent.md                       [E]
│  ├─ validator.agent.md                      [N]
│  ├─ explorer.agent.md                       [E]
│  ├─ cartographer.agent.md                   [N]
│  ├─ scribe.agent.md                         [N]
│  └─ security.agent.md                       [N]
│
├─ prompts/
│  ├─ init.prompt.md                          [N] (replaces root INIT-PROMPT.md)
│  ├─ implement.prompt.md                     [E]
│  ├─ plan.prompt.md                          [N]
│  ├─ validate.prompt.md                      [N]
│  ├─ explain.prompt.md                       [K]
│  ├─ debug.prompt.md                         [N]
│  ├─ refactor.prompt.md                      [E]
│  ├─ review.prompt.md                        [E]
│  ├─ test.prompt.md                          [K]
│  ├─ security-review.prompt.md               [N]
│  ├─ end-session.prompt.md                   [N]
│  ├─ resume.prompt.md                        [N]
│  ├─ compact-memory.prompt.md                [N]
│  ├─ recall.prompt.md                        [N]
│  ├─ graph.prompt.md                         [N]
│  └─ status.prompt.md                        [N]
│
├─ skills/
│  ├─ codebase-scan/SKILL.md                  [E]
│  ├─ context-gather/SKILL.md                 [E]
│  ├─ tdd/SKILL.md                            [E] (verbatim from superpowers)
│  ├─ security-review/SKILL.md                [E]
│  ├─ task-decomposition/SKILL.md             [N]
│  ├─ risk-classification/SKILL.md            [N]
│  ├─ validation-gate/SKILL.md                [N]
│  ├─ memory-compaction/SKILL.md              [N]
│  ├─ code-envelope/SKILL.md                  [N]
│  ├─ session-checkpoint/SKILL.md             [N]
│  ├─ tiered-routing/SKILL.md                 [N]
│  ├─ systematic-debugging/SKILL.md           [N]
│  └─ worktree-isolation/SKILL.md             [N]
│
├─ instructions/
│  ├─ python.instructions.md                  [K]
│  ├─ typescript.instructions.md              [K]
│  ├─ react.instructions.md                   [K]
│  ├─ testing.instructions.md                 [K]
│  ├─ monorepo.instructions.md                [N]
│  ├─ migration.instructions.md               [N]
│  └─ critical-path.instructions.md           [N]
│
├─ tools/
│  ├─ codegraph.py                            [N]
│  ├─ memory.py                               [N]
│  ├─ session.py                              [N]
│  ├─ bootstrap.sh                            [N]
│  └─ requirements.txt                        [N] tree-sitter-language-pack, sqlite-utils
│
├─ project-context.md                         [E] auto-generated, enhanced
│
└─ .cache/                                    [N] gitignored
   ├─ codegraph.db
   ├─ codegraph.json
   ├─ memory/
   ├─ sessions/
   ├─ logs/
   └─ .venv/

# Root-level
AGENTS.md                                      [E] reflects new agents
SETUP.md                                       [E] new architecture
INIT-PROMPT.md                                 [D] deleted, replaced by /init
README.md                                      [N] quickstart for project copy-in
.gitignore (template)                          [N] excludes .github/.cache/
```

---

## 12. Configuration (`.github/config.yaml`)

Single config file controls per-project tuning. Defaults work for any project; user overrides as needed.

```yaml
# Adaptive profile — activates a coherent feature set; per-feature override below
profile: auto              # auto | tiny | small | medium | large | xlarge | custom

# Auto-detection thresholds (only consulted when profile: auto)
profile_thresholds:
  tiny:   { max_files: 50,    max_loc: 2000 }
  small:  { max_files: 500,   max_loc: 20000 }
  medium: { max_files: 5000,  max_loc: 200000 }
  large:  { max_files: 50000, max_loc: 2000000 }
  # > large.max_files OR > large.max_loc ⇒ xlarge

# Per-feature overrides; "auto" defers to profile defaults (see Section 2.5)
features:
  code_graph: auto         # auto | full | symbols-only | off
  memory_compaction: auto  # auto | on | off
  multi_agent: auto        # auto | on | off
  worktree_isolation: auto # auto | on | off
  validator_gate: auto     # auto | mandatory | optional | off

codegraph:
  exclude:
    - "**/node_modules/**"
    - "**/.venv/**"
    - "**/dist/**"
    - "**/build/**"
    - "**/target/**"
    - "**/.git/**"
    - "**/vendor/**"
  languages:
    tier1: [python, javascript, typescript, tsx, go, java, rust, c, cpp]
    tier2: []      # add e.g. [ruby, kotlin] to extend
  budgets:
    envelope_default_tokens: 2000
    impact_max_depth: 3
  scan:
    workers: auto
    batch_size: 5000

memory:
  budgets:
    checkpoint:  { soft: 2000,  hard: 4000  }
    sessions:    { soft: 8000,  hard: 16000 }
    glossary:    { soft: 4000,  hard: 8000  }
    learnings:   { soft: 4000,  hard: 8000  }
  compaction_model: claude-sonnet-4-6
  archive_after_days: 7

dispatch:
  worktree_isolation: auto       # auto | true | false; auto = on for ≥2 parallel tasks
  worktree_dir: .worktrees       # .worktrees | worktrees
  max_retries_per_subtask: 2

models:
  fast:    claude-haiku-4-5
  standard: claude-sonnet-4-6
  thinking: claude-opus-4-6
  fallback:
    fast:    gpt-4.1
    standard: gpt-5.3-codex
    thinking: gpt-5.5

routing:
  critical_path_globs:
    - "**/auth/**"
    - "**/payments/**"
    - "**/crypto/**"
    - "**/security/**"
    - "**/migrations/**"
  deep_keywords: [refactor, redesign, architecture, migrate, rewrite]
```

---

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `tree-sitter-language-pack` install failure on user's Python | Bootstrap creates an isolated venv; failure surfaces clearly with fallback instructions; a stub-only mode lets agents still operate without graph. |
| Code graph staleness silently corrupts results | Every command checks `why-stale` and warns; `@router` auto-runs `update` at session start; `stats` exposes last-scan timestamp. |
| Memory compaction loses important detail | `decisions` kind is never compacted; cold digest is append-only paragraph; user can `memory.py recall` to find anything ever written. |
| Copilot doesn't honor `model:` frontmatter | Each agent's first message includes a recommended-model banner so the user can switch via the picker. Behavior doesn't depend on the right model — just quality varies. |
| User runs out of premium-request quota mid-session | `@router` reports estimated tier per dispatched task; user can override to Sonnet for thinking tasks if budget-constrained. |
| Parallel implementers edit overlapping files | `dispatch.worktree_isolation: auto` defaults to on for ≥2 parallel tasks; each task runs on its own branch in its own worktree; merge happens in Phase 5 with conflict surfacing. |
| 1TB scan exceeds memory or wall-clock budget | Multiprocessing with batched SQLite inserts; default exclusions; `scan --root <subdir>` for partial scans; incremental update is the steady-state, not full scan. |
| `@validator` rubber-stamps work without running checks | Iron Law verbatim in skill; report format requires command output for every ✅; PASS verdict cannot omit verification log. |
| Sessions accumulate unboundedly | Auto-archive after 7 days; `session.py archive` manual trigger; archived sessions stay queryable via `memory.py search`. |
| New developer pastes the folder in and it doesn't work | `/init` is idempotent and reports actionable errors; `README.md` quickstart covers the 3-step path; no global state means worst case is `rm -rf .github/.cache/` and re-run. |
| Profile auto-detection picks the wrong tier (e.g., generated-code repo inflates LoC) | User edits `profile:` in `config.yaml`; per-feature overrides handle edge cases; `/init` prompts before changing an existing profile; `/upgrade-tier --to=<tier>` for explicit moves. |
| User upgrades the codebase past a profile threshold and doesn't notice | Every `/status` and `codegraph.py stats` invocation warns when LoC/file-count crosses the next threshold; warning is non-blocking but persistent. |

---

## 14. Out of scope

- IDE plugin / VS Code extension. We use plain markdown files Copilot already reads.
- Hosted/managed indexing. Everything runs locally.
- Cross-platform AI tool support beyond Copilot.
- Auto-installation of language servers, linters, or test frameworks.
- A dashboard or visualization for the code graph (text CLI only).

---

## 15. Open questions for implementation phase

These are deferred to the implementation plan, not the design:

- Exact tree-sitter query strings per language for symbol extraction.
- FTS5 ranking tuning for `memory.py recall`.
- Whether to parallelize the initial scan with `multiprocessing.Pool` or `concurrent.futures.ProcessPoolExecutor`.
- Specific ✅/❌ examples to put in each new SKILL.md.
- Exact wording of the Iron Law in `validator.agent.md` (verbatim from superpowers vs slight rephrasing for Copilot tone).

---

## 16. Acceptance criteria for the implementation

The implementation is done when:

1. `/init` correctly auto-detects profile on at least three test fixtures: a `tiny` 5-file Python script, a `medium` 200k-LoC project, and a synthetic `large` 5k-file repo. Each completes within its budget (< 1 s, < 5 min, < 15 min) and `.github/.cache/` size stays within the matrix budget.
2. `tiny` profile: `/init` installs zero Python deps, `codegraph.py find` exits with the disabled-stub message, `/implement` works for a small task without touching the graph.
3. `small` profile: `/init` installs only required tree-sitter parsers; `codegraph.py find` works; `codegraph.py refs` returns the not-indexed message.
4. `codegraph.py find <symbol>` returns correct results for at least Python, TypeScript, Go on `medium+` profiles.
5. `codegraph.py impact <file>` returns correct reverse-deps for at least one Python and one TypeScript test fixture on `medium+` profiles.
6. `memory.py write` + `memory.py status` + `memory.py compact` round-trip works end-to-end with a real summary written by the active model.
7. A scripted DEEP-complexity task on a `medium` fixture completes Phases 1–5 end-to-end with two-stage review per task and a validation report containing the verification log.
8. Worktree isolation creates separate worktrees for two parallel tasks on a `large` fixture and merges back cleanly.
9. All 13 skills exist with the superpowers SKILL.md format and reference profile-conditional steps where applicable.
10. All 11 agents exist with correct frontmatter, `model` field, inherited-skills declaration, and a profile-check at prompt top.
11. Per-feature override path works: setting `features.code_graph: full` on a `small` profile activates the full graph despite profile defaults.
12. `/upgrade-tier` correctly bumps a `small` cache to `medium` (full scan, additional deps, gated features activate).
13. `/end-session` updates checkpoint, compacts memory if needed, runs codegraph update (skipped on tiny), and suggests a commit.
14. Documentation (`README.md`, `SETUP.md`, `AGENTS.md`) reflects the new architecture, the adaptive-profile concept, and the 3-step quickstart.

---

End of design.
