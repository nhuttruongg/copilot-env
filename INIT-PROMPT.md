# Prompt Khoi Tao

Copy noi dung ben duoi (tu dong ke `---`) va paste vao Copilot Chat (Agent mode).
Chi can lam **1 lan** cho moi du an.

---

I've set up an agentic environment for this project. Please:

1. **Confirm setup**: Verify you can see the custom instructions from `.github/copilot-instructions.md` and list available agents (`@conductor`, `@planner`, `@implementer`, `@reviewer`, `@explorer`, `@debugger`) and prompts (`/implement`, `/review`, `/test`, `/explain`, `/refactor`).

2. **Scan the codebase**: Analyze the project and create `.github/project-context.md` with:
   - Tech stack (language, framework, key dependencies)
   - Directory structure with purpose annotations
   - Architecture pattern
   - Entry points and key files
   - Naming conventions and code patterns
   - Testing setup (framework, file pattern, utilities)
   - Build/dev/test commands

3. **Report ready status**: Summarize what you found and confirm the environment is active.

**Default workflow after setup:**
- Simple task → just implement (instructions guide you automatically)
- Complex task → `@planner` first, then `@implementer`, then `@reviewer`
- Understand code → `@explorer` or `/explain`
- Bug → `@debugger`
- After any implementation → `/review`
