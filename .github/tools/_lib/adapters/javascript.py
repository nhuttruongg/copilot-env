"""JavaScript adapter — reuses TypeScript walker."""
from __future__ import annotations
from .typescript import TypeScriptAdapter


class JavaScriptAdapter(TypeScriptAdapter):
    def __init__(self):
        super().__init__("javascript")

    @property
    def language(self) -> str:
        return "javascript"
