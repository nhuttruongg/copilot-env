"""Per-language tree-sitter adapters for codegraph."""
from __future__ import annotations
from functools import lru_cache
from .base import Adapter, Extracted, Symbol, Import, Call, Ref

TIER1_LANGS = ["python", "javascript", "typescript", "tsx", "go", "java", "rust", "c", "cpp"]


def get_adapter(lang: str) -> Adapter | None:
    """Return adapter instance for lang, or None if unsupported."""
    if lang == "python":
        from .python import PythonAdapter
        return PythonAdapter()
    if lang == "javascript":
        from .javascript import JavaScriptAdapter
        return JavaScriptAdapter()
    if lang in ("typescript", "tsx"):
        from .typescript import TypeScriptAdapter
        return TypeScriptAdapter(lang)
    if lang == "go":
        from .go import GoAdapter
        return GoAdapter()
    if lang == "java":
        from .java import JavaAdapter
        return JavaAdapter()
    if lang == "rust":
        from .rust import RustAdapter
        return RustAdapter()
    if lang in ("c", "cpp"):
        from .c_cpp import CCppAdapter
        return CCppAdapter(lang)
    return None


@lru_cache(maxsize=32)
def get_parser(lang: str):
    """Return a cached tree-sitter Parser for lang, or None if unavailable."""
    try:
        from tree_sitter_language_pack import get_parser as _gp
    except ImportError:
        return None
    try:
        return _gp(lang)
    except Exception:
        return None


def list_supported_languages() -> list[str]:
    """Return tier1 languages whose parsers load successfully on this system."""
    return [lang for lang in TIER1_LANGS if get_parser(lang) is not None]
