"""Tiny text helpers shared across memory.py / codegraph.py / session.py."""
from __future__ import annotations


def approx_tokens(text: str) -> int:
    """Approximate token count as ceil(chars/4). Avoids any tokenizer dependency.

    Empty string is 0; any non-empty string is at least 1.
    """
    n = len(text)
    if n == 0:
        return 0
    return (n + 3) // 4
