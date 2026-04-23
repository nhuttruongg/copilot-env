---
applyTo: "**/*.tsx,**/*.jsx"
---

# React Instructions

- Use functional components with hooks (no class components)
- Use named exports for components
- Keep components small — extract when a component exceeds ~100 lines
- Co-locate related files (component, styles, tests, types)
- Use `useMemo` and `useCallback` only when there is a measurable performance need
- Prefer controlled components over uncontrolled
- Handle loading, error, and empty states explicitly
- Use React.lazy for code-splitting large routes/components
- Event handler naming: `handleEventName` (e.g., `handleClick`, `handleSubmit`)
- Prop naming: boolean props use `is/has/should` prefix (e.g., `isLoading`, `hasError`)
