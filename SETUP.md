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
│   ├── instructions/                     # Path-specific instructions (auto-applied)
│   │   ├── typescript.instructions.md   # *.ts, *.tsx
│   │   ├── react.instructions.md        # *.tsx, *.jsx
│   │   ├── python.instructions.md       # *.py
│   │   └── testing.instructions.md      # *.test.*, *.spec.*
│   ├── agents/                           # Specialized personas (@mention in chat)
│   │   ├── conductor.agent.md           # @conductor — orchestrate complex tasks
│   │   ├── planner.agent.md             # @planner — research & plan
│   │   ├── implementer.agent.md         # @implementer — TDD execution
│   │   ├── reviewer.agent.md            # @reviewer — quality gatekeeper
│   │   ├── explorer.agent.md            # @explorer — understand codebase
│   │   └── debugger.agent.md            # @debugger — find root causes
│   ├── prompts/                          # Reusable workflows (/slash in chat)
│   │   ├── implement.prompt.md          # /implement
│   │   ├── review.prompt.md             # /review
│   │   ├── test.prompt.md               # /test
│   │   ├── explain.prompt.md            # /explain
│   │   └── refactor.prompt.md           # /refactor
│   └── skills/                           # Agent capabilities
│       ├── codebase-scan/SKILL.md       # Full project mapping
│       ├── context-gather/SKILL.md      # Pre-implementation context
│       ├── tdd/SKILL.md                 # TDD workflow guide
│       └── security-review/SKILL.md     # Security audit checklist
├── AGENTS.md                             # Platform-agnostic AI instructions
├── SETUP.md                              # This file
└── INIT-PROMPT.md                        # First-time initialization prompt
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
- Neu project da co `.github/`, chi copy cac thu muc con (agents, prompts, skills, instructions)
- Xoa instructions khong can (VD: bo react.instructions.md neu project khong dung React)
- `.vscode/settings.json` KHONG can copy — tranh anh huong tai khoan nguoi khac

### Buoc 2: Tuy chinh (optional)

1. Chinh `copilot-instructions.md` — them conventions rieng cua du an
2. Them `.instructions.md` rieng cho framework cu the
3. Tao agent moi neu can

### Buoc 3: Khoi tao

Mo Copilot Chat (Agent mode) → paste noi dung tu `INIT-PROMPT.md`

## Cach Su Dung Hang Ngay

### Agents (go @ trong chat)
| Agent | Khi nao dung |
|-------|-------------|
| `@conductor` | Task phuc tap, nhieu file, nhieu buoc |
| `@planner` | Can len ke hoach truoc khi code |
| `@implementer` | Code theo TDD, co ky luat |
| `@reviewer` | Review code sau khi implement |
| `@explorer` | Tim hieu code/feature la |
| `@debugger` | Co bug, can tim root cause |

### Prompts (go / trong chat)
| Prompt | Khi nao dung |
|--------|-------------|
| `/implement` | Implement voi workflow day du |
| `/review` | Review nhanh |
| `/test` | Tao tests |
| `/explain` | Giai thich code |
| `/refactor` | Tai cau truc |

### Workflow de xuat
```
Task don gian (< 20 dong) → truc tiep implement
Task trung binh → /implement (tu dong plan + code + verify)
Task phuc tap → @planner → @implementer → @reviewer
Bug → @debugger
Hieu code → @explorer hoac /explain
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
| Agent routing | Subagent types (scout, builder, architect) | @conductor complexity routing |
| Skills | /skill slash commands | /prompts + skills/ |
| Code graph | GitNexus MCP | @workspace + @explorer agent |
| Memory | Beads + native memory | .github/project-context.md |
| MCP | mcp.json config | .vscode/mcp.json |
