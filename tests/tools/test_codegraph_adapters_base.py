import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.adapters.base import Extracted, Symbol, Import, Call, Adapter  # noqa: E402


def test_extracted_dataclass_default_empty():
    e = Extracted()
    assert e.symbols == []
    assert e.imports == []
    assert e.calls == []
    assert e.refs == []


def test_symbol_dataclass_required_fields():
    s = Symbol(name="foo", kind="func", start_line=1, end_line=5,
               qualified_name="m.foo", signature="def foo()", docstring="", visibility="public")
    assert s.name == "foo"
    assert s.kind == "func"


def test_adapter_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        Adapter()


from _lib.adapters import get_parser, list_supported_languages  # noqa: E402


def test_get_parser_returns_parser():
    p = get_parser("python")
    assert p is not None
    tree = p.parse(b"x = 1")
    assert tree.root_node is not None


def test_get_parser_unknown_language_returns_none():
    assert get_parser("klingon") is None


def test_supported_languages_includes_tier1():
    langs = set(list_supported_languages())
    for required in ["python", "javascript", "typescript", "tsx", "go", "java", "rust", "c", "cpp"]:
        assert required in langs
