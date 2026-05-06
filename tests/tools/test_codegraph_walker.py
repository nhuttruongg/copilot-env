import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.walker import iter_files, detect_lang  # noqa: E402


def test_iter_files_respects_exclude(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("# py")
    (tmp_path / "src" / "b.ts").write_text("// ts")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("// drop")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.js").write_text("// drop")

    paths = sorted(iter_files(tmp_path, exclude=["**/node_modules/**", "**/build/**"]))
    assert any(p.name == "a.py" for p in paths)
    assert any(p.name == "b.ts" for p in paths)
    assert not any("node_modules" in p.parts for p in paths)
    assert not any("build" in p.parts for p in paths)


def test_detect_lang_by_extension():
    assert detect_lang(Path("a.py")) == "python"
    assert detect_lang(Path("a.ts")) == "typescript"
    assert detect_lang(Path("a.tsx")) == "tsx"
    assert detect_lang(Path("a.jsx")) == "javascript"
    assert detect_lang(Path("a.go")) == "go"
    assert detect_lang(Path("a.rs")) == "rust"
    assert detect_lang(Path("a.java")) == "java"
    assert detect_lang(Path("a.c")) == "c"
    assert detect_lang(Path("a.cc")) == "cpp"
    assert detect_lang(Path("a.cpp")) == "cpp"
    assert detect_lang(Path("a.h")) == "c"
    assert detect_lang(Path("a.unknown")) is None
