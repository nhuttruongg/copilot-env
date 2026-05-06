# Copilot Agentic Environment — Setup Guide

## An Toan Voi Tai Khoan Cua Nguoi Khac

**100% an toan.** Tat ca customization nam trong `.github/` folder cua project — chi la nhung file Markdown binh thuong. Khong can thiet vao bat ky account settings nao.

- Khi mo workspace khac → khong thay gi
- Khi nguoi khac mo cung workspace → ho cung duoc huong loi (hoac ban `.gitignore` de an di)
- Khong anh huong den VS Code settings, Copilot preferences, hay bat ky cai dat nao cua tai khoan

## Cau Truc

```
copilot-env/
├── .github/
│   ├── copilot-instructions.md          # Zen of Engineering + workflow + standards
│   ├── config.yaml                       # Profile + feature overrides + budgets
│   ├── instructions/                     # Path-specific instructions (auto-applied)
│   │   ├── python.instructions.md       # *.py
│   │   ├── typescript.instructions.md   # *.ts, *.tsx
│   │   ├── react.instructions.md        # *.tsx, *.jsx
│   │   ├── testing.instructions.md      # *.test.*, *.spec.*
│   │   ├── monorepo.instructions.md     # packages/apps/services/**
│   │   ├── migration.instructions.md    # migrations/** (🔴 auto-flag)
│   │   └── critical-path.instructions.md # auth/payments/crypto/security/**
│   ├── agents/                           # Specialized personas (@mention in chat)
│   │   ├── router.agent.md              # @router — classify, route, dispatch
│   │   ├── planner.agent.md             # @planner — research + subtask DAG
│   │   ├── architect.agent.md           # @architect — greenfield design
│   │   ├── implementer.agent.md         # @implementer — TDD execution
│   │   ├── reviewer.agent.md            # @reviewer — two-stage review
│   │   ├── validator.agent.md           # @validator — verification gate
│   │   ├── explorer.agent.md            # @explorer — code understanding
│   │   ├── cartographer.agent.md        # @cartographer — graph queries
│   │   ├── scribe.agent.md              # @scribe — memory + checkpoint
│   │   ├── debugger.agent.md            # @debugger — Four Phases
│   │   ├── security.agent.md            # @security — critical-path audit
│   │   └── conductor.agent.md           # @conductor — legacy (use @router)
│   ├── prompts/                          # Reusable workflows (/slash in chat)
│   │   ├── init.prompt.md               # /init — one-shot setup
│   │   ├── implement.prompt.md          # /implement — auto-routes by complexity
│   │   ├── plan.prompt.md               # /plan — force deep planning
│   │   ├── validate.prompt.md           # /validate — verification gate
│   │   ├── review.prompt.md             # /review
│   │   ├── test.prompt.md               # /test
│   │   ├── explain.prompt.md            # /explain
│   │   ├── refactor.prompt.md           # /refactor
│   │   ├── debug.prompt.md              # /debug
│   │   ├── security-review.prompt.md    # /security-review
│   │   ├── end-session.prompt.md        # /end-session
│   │   ├── resume.prompt.md             # /resume
│   │   ├── compact-memory.prompt.md     # /compact-memory
│   │   ├── recall.prompt.md             # /recall
│   │   ├── graph.prompt.md              # /graph
│   │   └── status.prompt.md             # /status
│   ├── skills/                           # Agent capabilities (13 skills)
│   │   ├── codebase-scan/SKILL.md       # Full project mapping
│   │   ├── context-gather/SKILL.md      # Pre-implementation context
│   │   ├── tdd/SKILL.md                 # TDD with watched-fail Iron Law
│   │   ├── security-review/SKILL.md     # Security audit checklist
│   │   ├── task-decomposition/SKILL.md  # Subtask DAG algorithm
│   │   ├── risk-classification/SKILL.md # 🟢🟡🔴 file risk rubric
│   │   ├── validation-gate/SKILL.md     # Verification Iron Law
│   │   ├── memory-compaction/SKILL.md   # Hot→warm→cold tier rotation
│   │   ├── code-envelope/SKILL.md       # Token-budgeted context packets
│   │   ├── session-checkpoint/SKILL.md  # Session end procedure
│   │   ├── tiered-routing/SKILL.md      # INSTANT/STANDARD/DEEP heuristics
│   │   ├── systematic-debugging/SKILL.md # Four Phases methodology
│   │   └── worktree-isolation/SKILL.md  # Parallel task isolation
│   ├── tools/                            # CLI tools (Python + Bash)
│   │   ├── codegraph.py                 # Code graph: scan, query, envelope
│   │   ├── memory.py                    # Layered memory: write, read, compact
│   │   ├── session.py                   # Session lifecycle management
│   │   ├── bootstrap.sh                 # One-shot environment setup
│   │   ├── requirements.txt             # pyyaml + tree-sitter
│   │   └── _lib/                        # Shared helpers + adapters
│   └── .cache/                           # Runtime data (gitignored)
│       ├── codegraph.db                 # SQLite code graph
│       ├── project-context.md           # Living project map
│       ├── memory/                      # Layered memory files
│       └── sessions/                    # Per-session work logs
├── AGENTS.md                             # Platform-agnostic AI instructions
├── SETUP.md                              # This file
└── INIT-PROMPT.md                        # Legacy — use /init instead
```

## Cach Su Dung

### Buoc 1: Copy vao du an

```bash
# Copy .github folder (CORE — bat buoc)
cp -r copilot-env/.github /path/to/project/

# Copy AGENTS.md (optional — cho cross-platform compatibility)
cp copilot-env/AGENTS.md /path/to/project/
```

**LUU Y:**
- Neu project da co `.github/`, chi copy cac thu muc con (agents, prompts, skills, instructions, tools)
- Xoa instructions khong can (VD: bo react.instructions.md neu project khong dung React)
- `.vscode/settings.json` KHONG can copy — tranh anh huong tai khoan nguoi khac

### Buoc 2: Khoi tao

Mo Copilot Chat (Agent mode) → go `/init`

Bootstrap.sh se tu dong:
1. Detect profile (tiny/small/medium/large/xlarge) dua tren so file va LoC
2. Cai dat dependencies (tree-sitter) trong venv cuc bo
3. Scan code graph (tru profile tiny)
4. Tao `.github/.cache/` voi memory, sessions, project-context

### Buoc 3: Tuy chinh (optional)

1. Chinh `config.yaml` — override profile hoac tung feature rieng
2. Chinh `copilot-instructions.md` — them conventions rieng cua du an
3. Them `.instructions.md` rieng cho framework cu the
4. Tao agent moi neu can

## Cach Su Dung Hang Ngay

### Agents (go @ trong chat)
| Agent | Khi nao dung |
|-------|-------------|
| `@router` | Entry point mac dinh — tu dong phan loai va route |
| `@planner` | Can len ke hoach truoc khi code (Opus 4.6) |
| `@architect` | Thiet ke he thong moi, refactor lon (Opus 4.6) |
| `@implementer` | Code theo TDD, co ky luat |
| `@reviewer` | Review code sau khi implement (2 stages) |
| `@validator` | Verification gate cuoi cung (Opus 4.6) |
| `@explorer` | Tim hieu code/feature qua code graph |
| `@cartographer` | Query code graph nhanh (Haiku 4.5) |
| `@scribe` | Cap nhat memory, checkpoint, project-context |
| `@debugger` | Co bug, can tim root cause (Four Phases) |
| `@security` | Audit bao mat cho critical-path files (Opus 4.6) |

### Prompts (go / trong chat)
| Prompt | Khi nao dung |
|--------|-------------|
| `/init` | Khoi tao lan dau (bootstrap + scan + context) |
| `/implement` | Implement — tu dong route theo complexity |
| `/plan` | Len ke hoach chi tiet (skip routing) |
| `/validate` | Chay verification gate |
| `/review` | Review nhanh |
| `/test` | Tao tests |
| `/explain` | Giai thich code |
| `/refactor` | Tai cau truc (pipeline cho refactor lon) |
| `/debug` | Tim bug theo Four Phases |
| `/security-review` | Audit bao mat |
| `/end-session` | Ket thuc session — luu checkpoint |
| `/resume` | Tiep tuc session truoc |
| `/status` | Xem trang thai project |
| `/recall` | Tim trong memory |
| `/graph` | Query code graph |

### Workflow de xuat
```
Task don gian (< 20 dong) → INSTANT — implement truc tiep
Task trung binh (1-3 files) → /implement → STANDARD route
Task phuc tap → /implement → DEEP route (plan → batch → implement → validate)
Bug → /debug hoac @debugger
Hieu code → /explain hoac @explorer
Ket thuc ngay → /end-session
Bat dau ngay moi → /resume
```

## Nguon Hoc Hoi

Copilot-env duoc tong hop tu:
- copilot_orchestrator (kennedym-ds) — 16 agents, complexity routing, Zen of Engineering
- copilot-orchestra (ShepAlderson) — conductor pattern, TDD workflow
- awesome-copilot (github) — community best practices, folder conventions
- Claude Code — CLAUDE.md pattern, subagent routing

## So Sanh Voi Claude Code

| Tinh Nang | Claude Code | Copilot Env |
|-----------|------------|-------------|
| Instructions | CLAUDE.md | copilot-instructions.md + .instructions.md |
| Agent routing | Subagent types (scout, builder, architect) | @router complexity routing (INSTANT/STANDARD/DEEP) |
| Skills | /skill slash commands | /prompts + skills/ (13 skills) |
| Code graph | GitNexus MCP | codegraph.py (tree-sitter + SQLite) |
| Memory | Beads + native memory | memory.py (layered: checkpoint/sessions/decisions/learnings/glossary) |
| Validation | Manual | @validator with Verification Iron Law |
| Session mgmt | Built-in | session.py (start/log/save/end/resume/archive) |
| MCP | mcp.json config | .vscode/mcp.json |
