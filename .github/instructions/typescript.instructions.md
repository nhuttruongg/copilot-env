---
applyTo: "**/*.ts,**/*.tsx"
---

# TypeScript Instructions

- Use TypeScript strict mode conventions
- Prefer `interface` over `type` for object shapes (unless union/intersection needed)
- Use explicit return types for exported functions
- Prefer `const` over `let`, never use `var`
- Use optional chaining (`?.`) and nullish coalescing (`??`) instead of manual checks
- Prefer `unknown` over `any` — narrow types explicitly
- Use discriminated unions for state management
- Name interfaces without `I` prefix (e.g., `User` not `IUser`)
- Use `readonly` for properties that should not be mutated
- Prefer `Record<K, V>` over `{ [key: string]: V }`
