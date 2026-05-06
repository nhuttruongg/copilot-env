---
description: "Run the validation gate on a completed session. @validator verifies every acceptance criterion with fresh evidence, runs full test suite, audits code cleanliness, generates probe tests."
---

Run the final validation gate:

## Validation Procedure

Invoke `@validator` to perform the full verification:

1. **Load session** — read `plan.md` and all `results/*.done.md`
2. **Verify each acceptance criterion** — run the proving command NOW, capture output
3. **Run full test suite** — `pytest` / `npm test` / project's test command
4. **Run lint + type check** — project's lint/type tools
5. **Code cleanliness audit** — dead code, leaked TODOs, convention drift
6. **Cross-task consistency** — interfaces between tasks match
7. **Probe tests** — generate 2-3 edge-case tests, run them
8. **Write validation report** to `sessions/<id>/validation.md`

## Iron Law

> NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.
> Every ✅ requires captured command output from THIS session.

Validate session:
