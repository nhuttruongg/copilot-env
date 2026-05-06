import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.text import approx_tokens  # noqa: E402
from _lib.io import atomic_write_text  # noqa: E402


def test_approx_tokens_uses_chars_div_4():
    assert approx_tokens("") == 0
    assert approx_tokens("abcd") == 1
    assert approx_tokens("a" * 4000) == 1000
    assert approx_tokens("hi") == 1  # rounds up for non-empty


def test_atomic_write_text_writes_then_renames(tmp_path):
    target = tmp_path / "out.md"
    atomic_write_text(target, "hello")
    assert target.read_text() == "hello"
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_text_overwrites(tmp_path):
    target = tmp_path / "out.md"
    target.write_text("old")
    atomic_write_text(target, "new")
    assert target.read_text() == "new"
