---
description: "Refactor code to improve clarity, reduce duplication, or improve structure without changing behavior."
---

Refactoring rules:

1. **Read first** — understand current implementation fully
2. **Identify targets** — what specifically to improve (duplication, complexity, naming, structure)
3. **Check tests** — ensure tests exist. If not, suggest adding them BEFORE refactoring
4. **One change type at a time** — don't mix rename + restructure + optimize
5. **Preserve behavior** — no functional changes

For each change, explain:
- What was changed
- Why it's better
- That behavior is preserved

Run tests after refactoring to confirm no regressions.
