---
applyTo: "**/*.py"
---

# Python Instructions

- Follow PEP 8 style guide
- Use type hints for function parameters and return types
- Use f-strings for string formatting (not .format() or %)
- Prefer list/dict/set comprehensions over manual loops when readable
- Use `pathlib.Path` instead of `os.path` for file operations
- Use context managers (`with`) for resource management
- Use `dataclass` or `pydantic` for data structures
- Prefer `enum.Enum` for fixed sets of values
- Use `logging` module instead of `print()` for production code
- Handle exceptions specifically — never bare `except:`
