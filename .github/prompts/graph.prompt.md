---
description: "Quick code-graph query. No LLM needed — runs codegraph.py commands directly and displays results. Supports: find, refs, callers, callees, deps, impact, search, envelope, module, stats."
---

Run a code-graph query:

Parse the user's query and map it to the appropriate codegraph command:

| Intent | Command |
|---|---|
| Find a symbol | `codegraph.py find <name> [--kind=func\|class\|method]` |
| Who uses this? | `codegraph.py refs <name>` |
| Who calls this? | `codegraph.py callers <name>` |
| What does this call? | `codegraph.py callees <name>` |
| What does this file import? | `codegraph.py deps <file>` |
| What depends on this? | `codegraph.py impact <file> [--depth=2]` |
| Search symbols | `codegraph.py search "<query>"` |
| Get context for a symbol | `codegraph.py envelope <target> --budget 2000` |
| Module overview | `codegraph.py module <path>` |
| Graph stats | `codegraph.py stats` |
| Is graph fresh? | `codegraph.py why-stale` |

All commands use: `python3 .github/tools/codegraph.py <cmd> --db .github/.cache/codegraph.db`

Run the query and display results.
