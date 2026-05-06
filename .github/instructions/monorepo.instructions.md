---
applyTo: "**/packages/**,**/apps/**,**/services/**"
---

# Monorepo Instructions

When working in a monorepo (workspaces, turborepo, lerna, nx, or similar):

## Scope Narrowing
- Always identify which package/app/service you're working in
- Use `codegraph.py module <path>` to understand package boundaries
- Check `codegraph.py impact <file>` to understand cross-package dependencies
- Do NOT make changes across package boundaries without explicit approval

## Package Awareness
- Respect each package's own dependencies — don't import from sibling packages' internals
- Use the package's public API (exported from index/barrel file)
- Check if the package has its own test config, lint rules, or build step

## Dependency Rules
- Shared dependencies go in the root `package.json` / workspace root
- Package-specific dependencies go in the package's own manifest
- Never duplicate a dependency at both levels with different versions
- When adding a new dependency, check if it already exists elsewhere in the monorepo

## Build & Test
- Run tests scoped to the affected package: `npm test --workspace=<pkg>` or equivalent
- Run the full test suite before declaring done if changes cross package boundaries
- Be aware of build order — some packages depend on others being built first

## Cross-Package Changes
- If a change requires modifications in >1 package, treat it as DEEP complexity
- Document the cross-package dependency in the plan
- Consider interface stability — will this break other consumers?
