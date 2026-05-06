---
description: "Large refactor pipeline: @planner produces refactor plan → N×@implementer executes with TDD → @validator verifies behavior preserved. For small refactors, implements directly."
---

Refactoring rules:

0. **Assess scope** — if the refactor touches ≥3 files or changes interfaces, invoke `@planner` first for a refactor plan. Otherwise, proceed directly.

1. **Read first** — understand current implementation fully. Use codegraph:
   ```bash
   python3 .github/tools/codegraph.py envelope <target> --budget 2000 --db .github/.cache/codegraph.db
   python3 .github/tools/codegraph.py impact <target-file> --db .github/.cache/codegraph.db
   ```
2. **Identify targets** — what specifically to improve (duplication, complexity, naming, structure)
3. **Check tests** — ensure tests exist. If not, suggest adding them BEFORE refactoring
4. **One change type at a time** — don't mix rename + restructure + optimize
5. **Preserve behavior** — no functional changes

For each change, explain:
- What was changed
- Why it's better
- That behavior is preserved

Run tests after refactoring to confirm no regressions.
