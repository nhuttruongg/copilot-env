---
name: codebase-scan
description: "Scan and map the entire project using codegraph and bootstrap.sh: tech stack, architecture, conventions, entry points, dependencies. Run once at /init."
triggers:
  - "scan the codebase"
  - "project analysis"
  - "init setup"
---

# Codebase Scan

Perform a comprehensive scan and output a structured project map.

## Scan Steps

### 1. Project Identity
- Read `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`, or equivalent
- Identify: project name, language, framework, key dependencies
- Check for monorepo (workspaces, turborepo, lerna, nx)
- Run codegraph stats for quantitative overview:
  ```bash
  python3 .github/tools/codegraph.py stats --db .github/.cache/codegraph.db --json
  ```

### 2. Directory Structure
- Map top-level folders with purpose annotations
- Identify architecture pattern (MVC, Clean, DDD, Layered, etc.)

### 3. Entry Points
- Find main entry files
- Map route/endpoint definitions
- Trace initialization flow
- Use codegraph to identify key symbols:
  ```bash
  python3 .github/tools/codegraph.py search "main" --db .github/.cache/codegraph.db
  python3 .github/tools/codegraph.py module src/ --db .github/.cache/codegraph.db
  ```

### 4. Key Conventions
- File naming pattern (kebab, camel, pascal)
- Function/class naming conventions
- Import style (absolute vs relative, barrel exports)
- Error handling patterns
- Logging approach

### 5. Testing Setup
- Framework and runner
- File naming convention (`.test.`, `.spec.`, `__tests__/`)
- Fixture/mock patterns

### 6. Build & Config
- Build tool and scripts
- Environment config (.env, config files)
- CI/CD files

## Output

Save to `.github/project-context.md`:

```markdown
# [Project Name] — Project Map

## Tech Stack
- **Language:** [...]
- **Framework:** [...]
- **Database:** [...]
- **Key Deps:** [...]

## Architecture
[pattern + brief explanation]

## Structure
[annotated directory tree]

## Entry Points
| File | Purpose |
|------|---------|
| ... | ... |

## Conventions
- **Naming:** [...]
- **Testing:** [...]
- **Errors:** [...]
- **Imports:** [...]

## Key Files
| File | Purpose |
|------|---------|
| ... | ... |

## Commands
| Task | Command |
|------|---------|
| Dev | `...` |
| Test | `...` |
| Build | `...` |
| Lint | `...` |
```
