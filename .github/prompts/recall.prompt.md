---
description: "Quick search across project memory. No LLM needed — runs memory.py recall directly and displays ranked results."
---

Search project memory for relevant context:

```bash
python3 .github/tools/memory.py recall "$input"
```

Display the ranked results. If no results, try broader terms:

```bash
python3 .github/tools/memory.py search "$input"
```
