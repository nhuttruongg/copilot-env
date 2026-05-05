# Plan A2 — Code Graph Tool (`codegraph.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the persistent code graph: tree-sitter-based scanner producing a SQLite store of files/symbols/imports/calls/refs, with CLI commands for query (`find`, `refs`, `callers`, `callees`, `deps`, `impact`, `search`, `envelope`, `stats`, `why-stale`, `module`). Profile-aware: `tiny` is a no-op stub, `small` is symbols-only, `medium+` is full.

**Architecture:** Single `codegraph.py` script delegates per-language parsing to thin adapter modules in `_lib/adapters/`. Each adapter takes a parsed tree-sitter Tree + source bytes and returns a normalized `Extracted(symbols, imports, calls, refs)` dataclass. The driver handles SQLite schema, batched inserts, incremental updates, and queries. `multiprocessing.Pool` parallelizes the scan.

**Tech Stack:** Python 3.10+, `tree-sitter`, `tree-sitter-language-pack` (≥0.5), stdlib `sqlite3`, `multiprocessing`, `pathlib`, `argparse`. Builds on Plan A1's `config.py` and `_lib/io.py`.

**Spec reference:** `docs/superpowers/specs/2026-05-05-copilot-orchestration-design.md` §3.1, §2.5.

---

## File Structure

| File | Responsibility |
|---|---|
| `.github/tools/codegraph.py` | Entry CLI; schema, scan/update orchestration, query commands |
| `.github/tools/_lib/adapters/__init__.py` | `get_adapter(lang)` registry |
| `.github/tools/_lib/adapters/base.py` | `Adapter` ABC + `Extracted` dataclass |
| `.github/tools/_lib/adapters/python.py` | Python tree-sitter adapter |
| `.github/tools/_lib/adapters/javascript.py` | JS adapter (also covers `.jsx` via TSX adapter) |
| `.github/tools/_lib/adapters/typescript.py` | TS + TSX adapter |
| `.github/tools/_lib/adapters/go.py` | Go adapter |
| `.github/tools/_lib/adapters/java.py` | Java adapter |
| `.github/tools/_lib/adapters/rust.py` | Rust adapter |
| `.github/tools/_lib/adapters/c_cpp.py` | C and C++ adapters (sibling languages) |
| `.github/tools/_lib/walker.py` | File walker with glob-pattern excludes |
| `.github/tools/_lib/db.py` | SQLite connection helper + schema |
| `.github/tools/requirements.txt` | (modified) add `tree-sitter`, `tree-sitter-language-pack` |
| `tests/tools/fixtures/py-mini/` | Python test fixture (3 files, known symbols) |
| `tests/tools/fixtures/ts-mini/` | TypeScript test fixture |
| `tests/tools/test_codegraph_*.py` | Test files per task group |

27 tasks. ~130 steps. Tasks 5–12 (per-language adapters) share structure; once Task 5 (Python) is in place, Tasks 6–12 are mostly mechanical translations.

---

## Pre-flight

Before Task 1, verify Plan A1 is merged and tree-sitter installs successfully:

```bash
pytest tests/tools/ -v --tb=short    # Plan A1 must be green
python3 -m pip install --user tree-sitter 'tree-sitter-language-pack>=0.5'
python3 -c "from tree_sitter_language_pack import get_parser; p=get_parser('python'); print(p)"
```

If `tree-sitter-language-pack` import fails, stop and report. On some platforms the pack needs a build toolchain (`build-essential` on Linux); document the platform requirement and ask the human partner.

---

### Task 1: Schema + DB helper

**Files:**
- Create: `.github/tools/_lib/db.py`
- Create: `tests/tools/test_codegraph_db.py`
- Modify: `.github/tools/requirements.txt`

- [ ] **Step 1: Update requirements**

`.github/tools/requirements.txt`:

```
pyyaml>=6.0
tree-sitter>=0.21
tree-sitter-language-pack>=0.5
```

- [ ] **Step 2: Write the failing test**

`tests/tools/test_codegraph_db.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.db import open_db, SCHEMA_VERSION, ensure_schema  # noqa: E402


def test_open_db_creates_schema(tmp_path):
    dbp = tmp_path / "g.db"
    db = open_db(dbp)
    ensure_schema(db)
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    for required in ["files", "symbols", "imports", "calls", "refs", "meta"]:
        assert required in names, f"missing table {required!r}"
    # FTS virtual table
    assert "symbols_fts" in names
    # Schema version stored
    v = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    assert v[0] == str(SCHEMA_VERSION)


def test_open_db_idempotent(tmp_path):
    dbp = tmp_path / "g.db"
    open_db(dbp).close()
    db = open_db(dbp)
    ensure_schema(db)  # second call must not error
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_db.py -v
```

Expected: FAIL — `_lib/db.py` doesn't exist.

- [ ] **Step 4: Implement `_lib/db.py`**

```python
"""SQLite schema + connection helper for codegraph."""
from __future__ import annotations
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT UNIQUE NOT NULL,
    lang        TEXT,
    sha256      TEXT,
    mtime       REAL,
    line_count  INTEGER,
    parse_error INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);

CREATE TABLE IF NOT EXISTS symbols (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id         INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    qualified_name  TEXT,
    kind            TEXT NOT NULL,    -- func | class | method | var | type | const
    start_line      INTEGER,
    end_line        INTEGER,
    signature       TEXT,
    docstring       TEXT,
    visibility      TEXT
);
CREATE INDEX IF NOT EXISTS idx_symbols_name      ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file      ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_qualname  ON symbols(qualified_name);

CREATE TABLE IF NOT EXISTS imports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    from_file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    to_module    TEXT NOT NULL,
    imported     TEXT,
    alias        TEXT,
    line         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_imports_to ON imports(to_module);

CREATE TABLE IF NOT EXISTS calls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_symbol_id  INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    callee_name       TEXT NOT NULL,
    callee_symbol_id  INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
    line              INTEGER
);
CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_name);
CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_symbol_id);

CREATE TABLE IF NOT EXISTS refs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id  INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    line       INTEGER,
    kind       TEXT
);
CREATE INDEX IF NOT EXISTS idx_refs_symbol ON refs(symbol_id);

CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name, qualified_name, signature, docstring,
    content='symbols', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, qualified_name, signature, docstring)
    VALUES (new.id, new.name, new.qualified_name, new.signature, new.docstring);
END;
CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, qualified_name, signature, docstring)
    VALUES('delete', old.id, old.name, old.qualified_name, old.signature, old.docstring);
END;
"""


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA_SQL)
    db.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    db.commit()
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_db.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .github/tools/_lib/db.py .github/tools/requirements.txt tests/tools/test_codegraph_db.py
git commit -m "feat(codegraph): SQLite schema and db helper with FTS5 triggers"
```

---

### Task 2: File walker with exclude patterns

**Files:**
- Create: `.github/tools/_lib/walker.py`
- Create: `tests/tools/test_codegraph_walker.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_codegraph_walker.py`:

```python
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
    assert detect_lang(Path("a.h")) == "c"   # ambiguous; default to c
    assert detect_lang(Path("a.unknown")) is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_walker.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement walker**

`.github/tools/_lib/walker.py`:

```python
"""File walker with glob-pattern excludes."""
from __future__ import annotations
import fnmatch
from pathlib import Path
from typing import Iterator

EXT_LANG = {
    ".py":  "python",
    ".ts":  "typescript",
    ".tsx": "tsx",
    ".js":  "javascript",
    ".jsx": "javascript",
    ".go":  "go",
    ".rs":  "rust",
    ".java": "java",
    ".c":   "c",
    ".h":   "c",
    ".cc":  "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
}


def detect_lang(path: Path) -> str | None:
    return EXT_LANG.get(path.suffix.lower())


def _match_any(rel: str, patterns: list[str]) -> bool:
    """Match relative path against any of the glob patterns.

    Patterns may use `**` for any number of directory components and `*` for
    one path segment.
    """
    for pat in patterns:
        # fnmatch handles ** if we normalize
        if fnmatch.fnmatch(rel, pat):
            return True
        # Also try matching against each suffix to honour **/x/** semantics
        if "**" in pat:
            simple = pat.replace("**", "*")
            if fnmatch.fnmatch(rel, simple):
                return True
    return False


def iter_files(root: Path, exclude: list[str] | None = None) -> Iterator[Path]:
    exclude = exclude or []
    root = root.resolve()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        if _match_any(rel, exclude):
            continue
        yield p
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_walker.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/walker.py tests/tools/test_codegraph_walker.py
git commit -m "feat(codegraph): file walker with glob exclude + lang detection"
```

---

### Task 3: Adapter ABC + `Extracted` dataclass

**Files:**
- Create: `.github/tools/_lib/adapters/__init__.py`
- Create: `.github/tools/_lib/adapters/base.py`
- Create: `tests/tools/test_codegraph_adapters_base.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_codegraph_adapters_base.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_adapters_base.py -v
```

Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement base classes**

`.github/tools/_lib/adapters/__init__.py`:

```python
"""Per-language tree-sitter adapters for codegraph."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call, Ref


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
```

`.github/tools/_lib/adapters/base.py`:

```python
"""Adapter base class + extracted-data dataclasses."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Symbol:
    name: str
    kind: str            # func | class | method | var | type | const
    start_line: int
    end_line: int
    qualified_name: str = ""
    signature: str = ""
    docstring: str = ""
    visibility: str = "public"


@dataclass
class Import:
    to_module: str
    imported: str = ""
    alias: str = ""
    line: int = 0


@dataclass
class Call:
    caller_name: str   # qualified name of the enclosing symbol; "" if module-level
    callee_name: str
    line: int = 0


@dataclass
class Ref:
    symbol_name: str
    line: int
    kind: str = "read"


@dataclass
class Extracted:
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    refs: list[Ref] = field(default_factory=list)


class Adapter(ABC):
    """Per-language extractor.

    Implementations should be stateless and thread-safe; they are called from
    multiprocessing pool workers.
    """

    @property
    @abstractmethod
    def language(self) -> str: ...

    @abstractmethod
    def extract(self, source: bytes, path: str) -> Extracted:
        """Parse source bytes and return extracted symbols/imports/calls/refs."""
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_adapters_base.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/adapters/__init__.py .github/tools/_lib/adapters/base.py \
        tests/tools/test_codegraph_adapters_base.py
git commit -m "feat(codegraph): adapter ABC and Extracted/Symbol/Import/Call dataclasses"
```

---

### Task 4: Tree-sitter loader helper

**Files:**
- Modify: `.github/tools/_lib/adapters/__init__.py`
- Create: `tests/tools/test_codegraph_ts_loader.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_codegraph_ts_loader.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_ts_loader.py -v
```

Expected: FAIL — `get_parser` not exported.

- [ ] **Step 3: Add loader to `_lib/adapters/__init__.py`**

Append to `.github/tools/_lib/adapters/__init__.py`:

```python
from functools import lru_cache

TIER1_LANGS = ["python", "javascript", "typescript", "tsx", "go", "java", "rust", "c", "cpp"]


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
    return [l for l in TIER1_LANGS if get_parser(l) is not None]
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_ts_loader.py -v
```

Expected: PASS (assumes `tree-sitter-language-pack` installed; pre-flight verified).

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/adapters/__init__.py tests/tools/test_codegraph_ts_loader.py
git commit -m "feat(codegraph): cached tree-sitter parser loader for tier1 languages"
```

---

### Task 5: Python adapter

**Files:**
- Create: `.github/tools/_lib/adapters/python.py`
- Create: `tests/tools/test_codegraph_adapter_python.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_codegraph_adapter_python.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.adapters import get_adapter  # noqa: E402

PY = b"""\
import os
from pathlib import Path as P
from .util import helper

class Foo:
    def bar(self, x):
        '''bar doc.'''
        return helper(x)

def top(y):
    return Foo().bar(y) + os.getpid()
"""


def test_python_adapter_extracts_symbols():
    a = get_adapter("python")
    e = a.extract(PY, "module/m.py")
    names = {s.name for s in e.symbols}
    assert {"Foo", "bar", "top"}.issubset(names)
    bar = next(s for s in e.symbols if s.name == "bar")
    assert bar.kind == "method"
    assert "bar doc" in bar.docstring
    foo = next(s for s in e.symbols if s.name == "Foo")
    assert foo.kind == "class"
    top = next(s for s in e.symbols if s.name == "top")
    assert top.kind == "func"


def test_python_adapter_extracts_imports():
    a = get_adapter("python")
    e = a.extract(PY, "module/m.py")
    mods = {(i.to_module, i.imported, i.alias) for i in e.imports}
    assert ("os", "", "") in mods
    assert ("pathlib", "Path", "P") in mods
    assert (".util", "helper", "") in mods


def test_python_adapter_extracts_calls():
    a = get_adapter("python")
    e = a.extract(PY, "module/m.py")
    callees = {c.callee_name for c in e.calls}
    assert "helper" in callees
    assert "os.getpid" in callees or "getpid" in callees
    assert "Foo" in callees or "Foo()" in callees or "bar" in callees
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_adapter_python.py -v
```

Expected: FAIL — `python.py` adapter doesn't exist.

- [ ] **Step 3: Implement Python adapter**

`.github/tools/_lib/adapters/python.py`:

```python
"""Python tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class PythonAdapter(Adapter):
    @property
    def language(self) -> str:
        return "python"

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser("python")
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "import_statement":
            self._import(node, src, out)
        elif t == "import_from_statement":
            self._import_from(node, src, out)
        elif t == "class_definition":
            name = self._field_text(node, "name", src)
            sym = Symbol(
                name=name, kind="class",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
                docstring=self._docstring(node, src),
            )
            out.symbols.append(sym)
            for ch in node.children:
                self._walk(ch, src, out, scope + [name])
            return
        elif t == "function_definition":
            name = self._field_text(node, "name", src)
            kind = "method" if scope else "func"
            sym = Symbol(
                name=name, kind=kind,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
                docstring=self._docstring(node, src),
                visibility="private" if name.startswith("_") and not name.startswith("__") else "public",
            )
            out.symbols.append(sym)
            caller = sym.qualified_name
            for ch in node.children:
                self._walk_calls(ch, src, out, caller)
            return
        elif t == "call":
            self._call(node, src, out, caller="")
        for ch in node.children:
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "call":
            self._call(node, src, out, caller=caller)
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _signature(self, node, src: bytes) -> str:
        # First line of the def
        text = self._text(node, src).splitlines()[0] if self._text(node, src) else ""
        return text.strip()

    def _docstring(self, node, src: bytes) -> str:
        body = node.child_by_field_name("body")
        if body is None:
            return ""
        for ch in body.children:
            if ch.type == "expression_statement":
                inner = ch.children[0] if ch.children else None
                if inner and inner.type == "string":
                    raw = self._text(inner, src)
                    return raw.strip("\"' \n")
            break  # only check first statement
        return ""

    def _import(self, node, src: bytes, out: Extracted) -> None:
        # import a, b as c
        for ch in node.children:
            if ch.type == "dotted_name":
                out.imports.append(Import(to_module=self._text(ch, src), line=ch.start_point[0] + 1))
            elif ch.type == "aliased_import":
                name = ch.child_by_field_name("name")
                alias = ch.child_by_field_name("alias")
                out.imports.append(Import(
                    to_module=self._text(name, src) if name else "",
                    alias=self._text(alias, src) if alias else "",
                    line=ch.start_point[0] + 1,
                ))

    def _import_from(self, node, src: bytes, out: Extracted) -> None:
        # from x import y, z as w
        mod = node.child_by_field_name("module_name")
        # Relative: leading dots
        rel_dots = ""
        for ch in node.children:
            if ch.type == "import_prefix":
                rel_dots = self._text(ch, src)
                break
        mod_text = (rel_dots + (self._text(mod, src) if mod else "")) or rel_dots
        for ch in node.children:
            if ch.type == "dotted_name" and ch is not mod:
                out.imports.append(Import(
                    to_module=mod_text,
                    imported=self._text(ch, src),
                    line=ch.start_point[0] + 1,
                ))
            elif ch.type == "aliased_import":
                name = ch.child_by_field_name("name")
                alias = ch.child_by_field_name("alias")
                out.imports.append(Import(
                    to_module=mod_text,
                    imported=self._text(name, src) if name else "",
                    alias=self._text(alias, src) if alias else "",
                    line=ch.start_point[0] + 1,
                ))

    def _call(self, node, src: bytes, out: Extracted, caller: str) -> None:
        fn = node.child_by_field_name("function")
        if fn is None:
            return
        callee = self._text(fn, src)
        out.calls.append(Call(caller_name=caller, callee_name=callee, line=node.start_point[0] + 1))
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_adapter_python.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/adapters/python.py tests/tools/test_codegraph_adapter_python.py
git commit -m "feat(codegraph): Python adapter — symbols, imports, calls, docstrings"
```

---

### Task 6: TypeScript / TSX adapter

**Files:**
- Create: `.github/tools/_lib/adapters/typescript.py`
- Create: `tests/tools/test_codegraph_adapter_typescript.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_codegraph_adapter_typescript.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.adapters import get_adapter  # noqa: E402

TS = b"""\
import { foo } from './foo';
import * as bar from 'bar';

export class Service {
  doThing(x: number): string {
    return foo(x).toString();
  }
}

export function helper(y: number) {
  return new Service().doThing(y);
}
"""


def test_typescript_adapter_extracts_symbols():
    a = get_adapter("typescript")
    e = a.extract(TS, "x.ts")
    names = {s.name for s in e.symbols}
    assert {"Service", "doThing", "helper"}.issubset(names)


def test_typescript_adapter_extracts_imports():
    a = get_adapter("typescript")
    e = a.extract(TS, "x.ts")
    modules = {i.to_module for i in e.imports}
    assert "./foo" in modules
    assert "bar" in modules


def test_tsx_adapter_handles_jsx():
    a = get_adapter("tsx")
    src = b"export const Btn = () => <button onClick={() => {}}>x</button>"
    e = a.extract(src, "Btn.tsx")
    names = {s.name for s in e.symbols}
    assert "Btn" in names
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_adapter_typescript.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement TS/TSX adapter**

`.github/tools/_lib/adapters/typescript.py`:

```python
"""TypeScript and TSX tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class TypeScriptAdapter(Adapter):
    def __init__(self, language: str = "typescript"):
        if language not in ("typescript", "tsx"):
            raise ValueError(language)
        self._lang = language

    @property
    def language(self) -> str:
        return self._lang

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser(self._lang)
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "import_statement":
            self._import(node, src, out)
        elif t == "class_declaration":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="class",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
            ))
            for ch in node.children:
                self._walk(ch, src, out, scope + [name])
            return
        elif t in ("method_definition", "method_signature"):
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="method",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
            ))
            caller = ".".join(scope + [name])
            for ch in node.children:
                self._walk_calls(ch, src, out, caller)
            return
        elif t == "function_declaration":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="func",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
            ))
            caller = ".".join(scope + [name])
            for ch in node.children:
                self._walk_calls(ch, src, out, caller)
            return
        elif t == "lexical_declaration":
            # const Btn = () => ...
            for ch in node.children:
                if ch.type == "variable_declarator":
                    name_node = ch.child_by_field_name("name")
                    val_node = ch.child_by_field_name("value")
                    if name_node and val_node and val_node.type in ("arrow_function", "function_expression"):
                        name = self._text(name_node, src)
                        out.symbols.append(Symbol(
                            name=name, kind="func",
                            start_line=ch.start_point[0] + 1, end_line=ch.end_point[0] + 1,
                            qualified_name=".".join(scope + [name]),
                            signature=self._text(ch, src).split("\n")[0].strip(),
                        ))
        for ch in node.children:
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn is not None:
                out.calls.append(Call(
                    caller_name=caller,
                    callee_name=self._text(fn, src),
                    line=node.start_point[0] + 1,
                ))
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _signature(self, node, src: bytes) -> str:
        text = self._text(node, src).splitlines()[0] if self._text(node, src) else ""
        return text.strip()

    def _import(self, node, src: bytes, out: Extracted) -> None:
        # import { x, y } from 'mod';   import * as ns from 'mod';   import 'mod';
        source_node = node.child_by_field_name("source")
        mod = self._text(source_node, src).strip("'\"") if source_node else ""
        clause = None
        for ch in node.children:
            if ch.type == "import_clause":
                clause = ch
                break
        if clause is None:
            out.imports.append(Import(to_module=mod, line=node.start_point[0] + 1))
            return
        for ch in clause.children:
            if ch.type == "named_imports":
                for spec in ch.children:
                    if spec.type == "import_specifier":
                        name = spec.child_by_field_name("name")
                        alias = spec.child_by_field_name("alias")
                        out.imports.append(Import(
                            to_module=mod,
                            imported=self._text(name, src) if name else "",
                            alias=self._text(alias, src) if alias else "",
                            line=node.start_point[0] + 1,
                        ))
            elif ch.type == "namespace_import":
                ident = ch.children[-1] if ch.children else None
                out.imports.append(Import(
                    to_module=mod,
                    alias=self._text(ident, src) if ident else "",
                    line=node.start_point[0] + 1,
                ))
            elif ch.type == "identifier":
                out.imports.append(Import(
                    to_module=mod,
                    imported="default",
                    alias=self._text(ch, src),
                    line=node.start_point[0] + 1,
                ))
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_adapter_typescript.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/adapters/typescript.py tests/tools/test_codegraph_adapter_typescript.py
git commit -m "feat(codegraph): TypeScript + TSX adapter"
```

---

### Task 7: JavaScript adapter

Same structure as TS, simpler. Reuses TS query patterns; declared as a separate adapter so future per-language tweaks don't break TS.

**Files:**
- Create: `.github/tools/_lib/adapters/javascript.py`
- Create: `tests/tools/test_codegraph_adapter_javascript.py`

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.adapters import get_adapter  # noqa: E402

JS = b"""\
import { add } from './math';
class Counter { tick() { return add(this.n, 1); } }
function go(n) { return new Counter().tick(); }
export const Box = () => 'box';
"""


def test_js_adapter_symbols_and_imports():
    a = get_adapter("javascript")
    e = a.extract(JS, "x.js")
    names = {s.name for s in e.symbols}
    assert {"Counter", "tick", "go", "Box"}.issubset(names)
    assert any(i.to_module == "./math" for i in e.imports)
    callees = {c.callee_name for c in e.calls}
    assert any("add" in c for c in callees)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_adapter_javascript.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement JS adapter**

`.github/tools/_lib/adapters/javascript.py`:

```python
"""JavaScript adapter — same shape as TS, simpler types."""
from __future__ import annotations
from .typescript import TypeScriptAdapter


class JavaScriptAdapter(TypeScriptAdapter):
    def __init__(self):
        # Reuse TS extraction logic; tree-sitter-language-pack 'javascript' parser
        # has overlapping node types for the constructs we extract (class_declaration,
        # function_declaration, lexical_declaration, import_statement).
        super().__init__("javascript")  # will use 'javascript' parser via get_parser

    @property
    def language(self) -> str:
        return "javascript"

    # If JS-specific tweaks are needed later, override _walk here. For now,
    # the TS implementation handles all our extraction cases.
```

Note that `TypeScriptAdapter.__init__` validates `language` — extend it to accept `javascript`:

In `.github/tools/_lib/adapters/typescript.py`, change the validator:

```python
        if language not in ("typescript", "tsx", "javascript"):
            raise ValueError(language)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_adapter_javascript.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/adapters/javascript.py .github/tools/_lib/adapters/typescript.py \
        tests/tools/test_codegraph_adapter_javascript.py
git commit -m "feat(codegraph): JavaScript adapter (reuses TypeScript walker)"
```

---

### Task 8: Go adapter

**Files:**
- Create: `.github/tools/_lib/adapters/go.py`
- Create: `tests/tools/test_codegraph_adapter_go.py`

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.adapters import get_adapter  # noqa: E402

GO = b'''\
package svc

import (
    "fmt"
    e "errors"
)

type Service struct{}

func (s *Service) Do(x int) string {
    return fmt.Sprintf("%d", x)
}

func New() *Service { return &Service{} }
'''


def test_go_adapter_symbols_imports_calls():
    a = get_adapter("go")
    e = a.extract(GO, "svc.go")
    names = {s.name for s in e.symbols}
    assert {"Service", "Do", "New"}.issubset(names)
    mods = {(i.to_module, i.alias) for i in e.imports}
    assert ("fmt", "") in mods
    assert ("errors", "e") in mods
    callees = {c.callee_name for c in e.calls}
    assert any("Sprintf" in c for c in callees)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_adapter_go.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement Go adapter**

`.github/tools/_lib/adapters/go.py`:

```python
"""Go tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class GoAdapter(Adapter):
    @property
    def language(self) -> str:
        return "go"

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser("go")
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "import_declaration":
            self._imports(node, src, out)
        elif t == "type_declaration":
            for ch in node.children:
                if ch.type == "type_spec":
                    name = self._field_text(ch, "name", src)
                    out.symbols.append(Symbol(
                        name=name, kind="type",
                        start_line=ch.start_point[0] + 1, end_line=ch.end_point[0] + 1,
                        qualified_name=name, signature=self._line(ch, src),
                    ))
        elif t == "function_declaration":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="func",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=name, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=name)
        elif t == "method_declaration":
            recv = node.child_by_field_name("receiver")
            name = self._field_text(node, "name", src)
            qual = self._receiver_type(recv, src) + "." + name if recv else name
            out.symbols.append(Symbol(
                name=name, kind="method",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=qual, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=qual)
        for ch in node.children:
            if t in ("function_declaration", "method_declaration"):
                continue  # already handled
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn is not None:
                out.calls.append(Call(
                    caller_name=caller,
                    callee_name=self._text(fn, src),
                    line=node.start_point[0] + 1,
                ))
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    def _imports(self, node, src: bytes, out: Extracted) -> None:
        for ch in node.children:
            if ch.type == "import_spec":
                self._import_spec(ch, src, out)
            elif ch.type == "import_spec_list":
                for spec in ch.children:
                    if spec.type == "import_spec":
                        self._import_spec(spec, src, out)

    def _import_spec(self, spec, src: bytes, out: Extracted) -> None:
        name_node = spec.child_by_field_name("name")
        path_node = spec.child_by_field_name("path")
        path = self._text(path_node, src).strip('"') if path_node else ""
        alias = self._text(name_node, src) if name_node else ""
        out.imports.append(Import(to_module=path, alias=alias, line=spec.start_point[0] + 1))

    def _receiver_type(self, recv_node, src: bytes) -> str:
        # find the type node inside parameter_list
        for ch in recv_node.children:
            if ch.type == "parameter_declaration":
                tnode = ch.child_by_field_name("type")
                if tnode is not None:
                    return self._text(tnode, src).lstrip("*")
        return ""

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _line(self, node, src: bytes) -> str:
        return self._text(node, src).splitlines()[0].strip() if self._text(node, src) else ""
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_adapter_go.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/adapters/go.py tests/tools/test_codegraph_adapter_go.py
git commit -m "feat(codegraph): Go adapter — funcs, methods, types, imports, calls"
```

---

### Task 9: Java adapter

**Files:**
- Create: `.github/tools/_lib/adapters/java.py`
- Create: `tests/tools/test_codegraph_adapter_java.py`

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.adapters import get_adapter  # noqa: E402

JAVA = b"""\
package com.acme;

import java.util.List;
import java.util.Map.Entry;

public class Service {
    public String process(int x) {
        return String.valueOf(x);
    }
}
"""


def test_java_adapter_symbols_imports_calls():
    a = get_adapter("java")
    e = a.extract(JAVA, "Service.java")
    names = {s.name for s in e.symbols}
    assert {"Service", "process"}.issubset(names)
    mods = {i.to_module for i in e.imports}
    assert "java.util.List" in mods
    assert any("valueOf" in c.callee_name for c in e.calls)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_adapter_java.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement Java adapter**

`.github/tools/_lib/adapters/java.py`:

```python
"""Java tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class JavaAdapter(Adapter):
    @property
    def language(self) -> str:
        return "java"

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser("java")
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "import_declaration":
            scoped = node.children[1] if len(node.children) > 1 else None
            if scoped is not None:
                out.imports.append(Import(
                    to_module=self._text(scoped, src),
                    line=node.start_point[0] + 1,
                ))
        elif t == "class_declaration":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="class",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]), signature=self._line(node, src),
            ))
            for ch in node.children:
                self._walk(ch, src, out, scope + [name])
            return
        elif t == "method_declaration":
            name = self._field_text(node, "name", src)
            qual = ".".join(scope + [name])
            out.symbols.append(Symbol(
                name=name, kind="method",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=qual, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=qual)
            return
        for ch in node.children:
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "method_invocation":
            name_node = node.child_by_field_name("name")
            obj = node.child_by_field_name("object")
            callee = ""
            if obj is not None:
                callee = self._text(obj, src) + "." + self._text(name_node, src)
            elif name_node is not None:
                callee = self._text(name_node, src)
            if callee:
                out.calls.append(Call(caller_name=caller, callee_name=callee,
                                      line=node.start_point[0] + 1))
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _line(self, node, src: bytes) -> str:
        return self._text(node, src).splitlines()[0].strip() if self._text(node, src) else ""
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_adapter_java.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/adapters/java.py tests/tools/test_codegraph_adapter_java.py
git commit -m "feat(codegraph): Java adapter — classes, methods, imports, invocations"
```

---

### Task 10: Rust adapter

**Files:**
- Create: `.github/tools/_lib/adapters/rust.py`
- Create: `tests/tools/test_codegraph_adapter_rust.py`

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.adapters import get_adapter  # noqa: E402

RUST = b'''\
use std::collections::HashMap;
use crate::util::{helper, other as o};

pub struct Foo { x: i32 }

impl Foo {
    pub fn bar(&self, n: i32) -> i32 {
        helper(n) + self.x
    }
}

pub fn make() -> Foo { Foo { x: 0 } }
'''


def test_rust_adapter_symbols_imports_calls():
    a = get_adapter("rust")
    e = a.extract(RUST, "lib.rs")
    names = {s.name for s in e.symbols}
    assert {"Foo", "bar", "make"}.issubset(names)
    mods = {i.to_module for i in e.imports}
    assert any("HashMap" in m or "collections" in m for m in mods)
    callees = {c.callee_name for c in e.calls}
    assert any("helper" in c for c in callees)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_adapter_rust.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement Rust adapter**

`.github/tools/_lib/adapters/rust.py`:

```python
"""Rust tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class RustAdapter(Adapter):
    @property
    def language(self) -> str:
        return "rust"

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser("rust")
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "use_declaration":
            self._use(node, src, out)
        elif t == "struct_item":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="type",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]), signature=self._line(node, src),
            ))
        elif t == "function_item":
            name = self._field_text(node, "name", src)
            qual = ".".join(scope + [name])
            kind = "method" if scope else "func"
            out.symbols.append(Symbol(
                name=name, kind=kind,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=qual, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=qual)
            return
        elif t == "impl_item":
            type_node = node.child_by_field_name("type")
            type_name = self._text(type_node, src) if type_node else ""
            for ch in node.children:
                self._walk(ch, src, out, scope + [type_name])
            return
        for ch in node.children:
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn is not None:
                out.calls.append(Call(caller_name=caller, callee_name=self._text(fn, src),
                                      line=node.start_point[0] + 1))
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    def _use(self, node, src: bytes, out: Extracted) -> None:
        # use a::b::{c, d as e};
        for ch in node.children:
            if ch.type in ("scoped_identifier", "scoped_use_list", "use_list", "identifier"):
                # Simplification: store the whole use path as to_module
                out.imports.append(Import(
                    to_module=self._text(ch, src),
                    line=node.start_point[0] + 1,
                ))
                break

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _line(self, node, src: bytes) -> str:
        return self._text(node, src).splitlines()[0].strip() if self._text(node, src) else ""
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_adapter_rust.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/adapters/rust.py tests/tools/test_codegraph_adapter_rust.py
git commit -m "feat(codegraph): Rust adapter — structs, fns, impl methods, use decls"
```

---

### Task 11: C / C++ adapter

**Files:**
- Create: `.github/tools/_lib/adapters/c_cpp.py`
- Create: `tests/tools/test_codegraph_adapter_c_cpp.py`

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.adapters import get_adapter  # noqa: E402

C = b"""\
#include <stdio.h>
#include "util.h"

int compute(int x) { return helper(x) + 1; }
int main(void) { return compute(7); }
"""

CPP = b"""\
#include <vector>
namespace ns {
class Foo {
public:
  int bar(int x) { return x * 2; }
};
}
int main() { return ns::Foo().bar(3); }
"""


def test_c_adapter_function_and_includes():
    a = get_adapter("c")
    e = a.extract(C, "x.c")
    names = {s.name for s in e.symbols}
    assert {"compute", "main"}.issubset(names)
    mods = {i.to_module for i in e.imports}
    assert "stdio.h" in mods
    assert "util.h" in mods


def test_cpp_adapter_class_and_method():
    a = get_adapter("cpp")
    e = a.extract(CPP, "x.cpp")
    names = {s.name for s in e.symbols}
    assert "Foo" in names
    assert "bar" in names
    assert "main" in names
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_adapter_c_cpp.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement C/C++ adapter**

`.github/tools/_lib/adapters/c_cpp.py`:

```python
"""C and C++ tree-sitter adapter (sibling languages share a walker)."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class CCppAdapter(Adapter):
    def __init__(self, language: str = "c"):
        if language not in ("c", "cpp"):
            raise ValueError(language)
        self._lang = language

    @property
    def language(self) -> str:
        return self._lang

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser(self._lang)
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "preproc_include":
            for ch in node.children:
                if ch.type in ("string_literal", "system_lib_string"):
                    inc = self._text(ch, src).strip('<>"')
                    out.imports.append(Import(to_module=inc, line=node.start_point[0] + 1))
        elif t == "function_definition":
            decl = node.child_by_field_name("declarator")
            name = self._declarator_name(decl, src) if decl else ""
            qual = ".".join(scope + [name]) if name else ""
            out.symbols.append(Symbol(
                name=name, kind="func" if not scope else "method",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=qual, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=qual)
            return
        elif t in ("class_specifier", "struct_specifier"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = self._text(name_node, src)
                out.symbols.append(Symbol(
                    name=name, kind="class" if t == "class_specifier" else "type",
                    start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    qualified_name=".".join(scope + [name]), signature=self._line(node, src),
                ))
                for ch in node.children:
                    self._walk(ch, src, out, scope + [name])
                return
        elif t == "namespace_definition":
            name_node = node.child_by_field_name("name")
            ns = self._text(name_node, src) if name_node else ""
            for ch in node.children:
                self._walk(ch, src, out, scope + [ns] if ns else scope)
            return
        for ch in node.children:
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn is not None:
                out.calls.append(Call(caller_name=caller, callee_name=self._text(fn, src),
                                      line=node.start_point[0] + 1))
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    def _declarator_name(self, node, src: bytes) -> str:
        # Walk down through pointer/parenthesized declarators to find the identifier
        cur = node
        while cur is not None:
            if cur.type == "identifier" or cur.type == "field_identifier":
                return self._text(cur, src)
            decl = cur.child_by_field_name("declarator")
            if decl is None:
                # Try first identifier child
                for ch in cur.children:
                    if ch.type in ("identifier", "field_identifier", "qualified_identifier"):
                        return self._text(ch, src)
                return ""
            cur = decl
        return ""

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _line(self, node, src: bytes) -> str:
        return self._text(node, src).splitlines()[0].strip() if self._text(node, src) else ""
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_adapter_c_cpp.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/adapters/c_cpp.py tests/tools/test_codegraph_adapter_c_cpp.py
git commit -m "feat(codegraph): C/C++ adapter — funcs, classes, namespaces, includes"
```

---

### Task 12: `codegraph.py` skeleton + `scan` command (single-process)

Multiprocessing is added in the next task; first prove correctness in-process.

**Files:**
- Create: `.github/tools/codegraph.py`
- Create: `tests/tools/fixtures/py-mini/m.py`
- Create: `tests/tools/fixtures/py-mini/u.py`
- Create: `tests/tools/test_codegraph_scan.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/fixtures/py-mini/m.py`:

```python
from .u import helper

class App:
    def run(self, x):
        return helper(x) + 1

def main():
    return App().run(3)
```

`tests/tools/fixtures/py-mini/u.py`:

```python
def helper(n):
    return n * 2
```

`tests/tools/test_codegraph_scan.py`:

```python
import sys
import sqlite3
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from codegraph import scan_into  # noqa: E402


@pytest.fixture
def py_mini(tmp_path: Path, request) -> Path:
    src = Path(request.config.rootpath) / "tests" / "tools" / "fixtures" / "py-mini"
    dst = tmp_path / "py-mini"
    shutil.copytree(src, dst)
    return dst


def test_scan_populates_files_and_symbols(py_mini: Path, tmp_path: Path):
    dbp = tmp_path / "g.db"
    n_files = scan_into(py_mini, dbp, exclude=[], workers=1)
    assert n_files == 2
    db = sqlite3.connect(str(dbp))
    files = {r[0] for r in db.execute("SELECT path FROM files").fetchall()}
    assert any(p.endswith("m.py") for p in files)
    assert any(p.endswith("u.py") for p in files)
    syms = {r[0] for r in db.execute("SELECT name FROM symbols").fetchall()}
    assert {"App", "run", "main", "helper"}.issubset(syms)
    imports = {r[0] for r in db.execute("SELECT to_module FROM imports").fetchall()}
    assert ".u" in imports
    calls = {r[0] for r in db.execute("SELECT callee_name FROM calls").fetchall()}
    assert any("helper" in c for c in calls)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_scan.py -v
```

Expected: FAIL — `codegraph.py` doesn't exist.

- [ ] **Step 3: Implement `scan_into` and the CLI shell**

`.github/tools/codegraph.py`:

```python
#!/usr/bin/env python3
"""Code graph CLI: scan, update, and query a SQLite-backed code index."""
from __future__ import annotations
import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).parent))
from _lib.db import open_db, ensure_schema
from _lib.walker import iter_files, detect_lang
from _lib.adapters import get_adapter


def _file_meta(p: Path, source: bytes) -> tuple[str, float, int]:
    sha = hashlib.sha256(source).hexdigest()
    mtime = p.stat().st_mtime
    line_count = source.count(b"\n") + 1
    return sha, mtime, line_count


def _persist_extracted(db: sqlite3.Connection, file_id: int, ex) -> None:
    sym_id_by_qual: dict[str, int] = {}
    for s in ex.symbols:
        cur = db.execute(
            "INSERT INTO symbols(file_id, name, qualified_name, kind, start_line, "
            "end_line, signature, docstring, visibility) VALUES (?,?,?,?,?,?,?,?,?)",
            (file_id, s.name, s.qualified_name, s.kind, s.start_line, s.end_line,
             s.signature, s.docstring, s.visibility),
        )
        if s.qualified_name:
            sym_id_by_qual[s.qualified_name] = cur.lastrowid
    for i in ex.imports:
        db.execute(
            "INSERT INTO imports(from_file_id, to_module, imported, alias, line) "
            "VALUES (?,?,?,?,?)",
            (file_id, i.to_module, i.imported, i.alias, i.line),
        )
    for c in ex.calls:
        caller_id = sym_id_by_qual.get(c.caller_name)
        db.execute(
            "INSERT INTO calls(caller_symbol_id, callee_name, callee_symbol_id, line) "
            "VALUES (?,?,?,?)",
            (caller_id, c.callee_name, None, c.line),
        )


def scan_into(root: Path, db_path: Path, exclude: list[str], workers: int = 1) -> int:
    """Scan root, persist into db_path. Returns count of indexed files.

    workers==1 runs in-process; >1 will use multiprocessing (Task 13).
    """
    db = open_db(db_path)
    ensure_schema(db)
    # Wipe (full scan replaces)
    db.executescript("DELETE FROM refs; DELETE FROM calls; DELETE FROM imports; "
                     "DELETE FROM symbols; DELETE FROM files;")
    db.commit()

    n = 0
    for p in iter_files(root, exclude):
        lang = detect_lang(p)
        if lang is None:
            continue
        adapter = get_adapter(lang)
        if adapter is None:
            continue
        try:
            source = p.read_bytes()
        except OSError:
            continue
        sha, mtime, lc = _file_meta(p, source)
        try:
            extracted = adapter.extract(source, str(p.relative_to(root)))
            parse_err = 0
        except Exception:
            extracted = None
            parse_err = 1
        cur = db.execute(
            "INSERT INTO files(path, lang, sha256, mtime, line_count, parse_error) "
            "VALUES (?,?,?,?,?,?)",
            (str(p.relative_to(root)), lang, sha, mtime, lc, parse_err),
        )
        if extracted is not None:
            _persist_extracted(db, cur.lastrowid, extracted)
        n += 1
    db.commit()
    return n


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--root", default=".")
    p_scan.add_argument("--db", default=".github/.cache/codegraph.db")
    p_scan.add_argument("--exclude", nargs="*", default=[])
    p_scan.add_argument("--workers", type=int, default=1)
    args = p.parse_args(argv)
    if args.cmd == "scan":
        n = scan_into(Path(args.root), Path(args.db), args.exclude, args.workers)
        print(f"indexed {n} files into {args.db}")
        return 0
    p.error(f"unsupported command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_scan.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/fixtures/py-mini/m.py \
        tests/tools/fixtures/py-mini/u.py tests/tools/test_codegraph_scan.py
git commit -m "feat(codegraph): scan command — single-process scan + persist"
```

---

### Task 13: Parallel scan via multiprocessing pool

**Files:**
- Modify: `.github/tools/codegraph.py`
- Modify: `tests/tools/test_codegraph_scan.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_codegraph_scan.py`:

```python
def test_scan_with_workers_2_matches_single(py_mini: Path, tmp_path: Path):
    db1 = tmp_path / "single.db"
    db2 = tmp_path / "parallel.db"
    n1 = scan_into(py_mini, db1, exclude=[], workers=1)
    n2 = scan_into(py_mini, db2, exclude=[], workers=2)
    assert n1 == n2
    import sqlite3
    s1 = sorted(sqlite3.connect(str(db1)).execute("SELECT name FROM symbols ORDER BY name").fetchall())
    s2 = sorted(sqlite3.connect(str(db2)).execute("SELECT name FROM symbols ORDER BY name").fetchall())
    assert s1 == s2
```

- [ ] **Step 2: Run the test (should still fail with workers=2 path missing)**

```bash
pytest tests/tools/test_codegraph_scan.py::test_scan_with_workers_2_matches_single -v
```

Expected: FAIL — `workers > 1` not implemented.

- [ ] **Step 3: Implement multiprocessing path**

In `.github/tools/codegraph.py`, replace the body of `scan_into`:

```python
def _parse_one(args: tuple[str, str, str]) -> tuple[str, str, str, float, int, int, object | None]:
    """Worker: parse a single file, return tuple suitable for DB insert.

    Returns: (rel_path, lang, sha, mtime, line_count, parse_error, extracted_or_None)
    `extracted` is an Extracted dataclass (picklable).
    """
    rel_path, abs_path, root_str = args
    p = Path(abs_path)
    lang = detect_lang(p)
    if lang is None:
        return rel_path, "", "", 0.0, 0, 0, None
    adapter = get_adapter(lang)
    if adapter is None:
        return rel_path, lang, "", 0.0, 0, 0, None
    try:
        source = p.read_bytes()
    except OSError:
        return rel_path, lang, "", 0.0, 0, 1, None
    sha, mtime, lc = _file_meta(p, source)
    try:
        extracted = adapter.extract(source, rel_path)
        return rel_path, lang, sha, mtime, lc, 0, extracted
    except Exception:
        return rel_path, lang, sha, mtime, lc, 1, None


def scan_into(root: Path, db_path: Path, exclude: list[str], workers: int = 1) -> int:
    db = open_db(db_path)
    ensure_schema(db)
    db.executescript("DELETE FROM refs; DELETE FROM calls; DELETE FROM imports; "
                     "DELETE FROM symbols; DELETE FROM files;")
    db.commit()
    targets = []
    for p in iter_files(root, exclude):
        if detect_lang(p) is None:
            continue
        rel = str(p.relative_to(root))
        targets.append((rel, str(p), str(root)))

    if workers <= 1:
        results = [_parse_one(t) for t in targets]
    else:
        from multiprocessing import Pool
        with Pool(workers) as pool:
            results = pool.map(_parse_one, targets, chunksize=20)

    n = 0
    for rel_path, lang, sha, mtime, lc, parse_err, extracted in results:
        cur = db.execute(
            "INSERT INTO files(path, lang, sha256, mtime, line_count, parse_error) "
            "VALUES (?,?,?,?,?,?)",
            (rel_path, lang, sha, mtime, lc, parse_err),
        )
        if extracted is not None:
            _persist_extracted(db, cur.lastrowid, extracted)
        n += 1
    db.commit()
    return n
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_scan.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_scan.py
git commit -m "feat(codegraph): parallel scan via multiprocessing.Pool"
```

---

### Task 14: Incremental update (`update` command)

**Files:**
- Modify: `.github/tools/codegraph.py`
- Create: `tests/tools/test_codegraph_update.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_codegraph_update.py`:

```python
import sys
import shutil
import subprocess
import sqlite3
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from codegraph import scan_into, update_into  # noqa: E402


@pytest.fixture
def py_mini(tmp_path: Path, request) -> Path:
    src = Path(request.config.rootpath) / "tests" / "tools" / "fixtures" / "py-mini"
    dst = tmp_path / "py-mini"
    shutil.copytree(src, dst)
    return dst


def test_update_picks_up_new_file(py_mini: Path, tmp_path: Path):
    dbp = tmp_path / "g.db"
    scan_into(py_mini, dbp, exclude=[], workers=1)
    db = sqlite3.connect(str(dbp))
    initial = {r[0] for r in db.execute("SELECT path FROM files").fetchall()}
    assert not any(p.endswith("new.py") for p in initial)
    (py_mini / "new.py").write_text("def added():\n    return 7\n")
    n_changed = update_into(py_mini, dbp, exclude=[])
    assert n_changed >= 1
    db = sqlite3.connect(str(dbp))
    after = {r[0] for r in db.execute("SELECT path FROM files").fetchall()}
    assert any(p.endswith("new.py") for p in after)
    syms = {r[0] for r in db.execute("SELECT name FROM symbols").fetchall()}
    assert "added" in syms


def test_update_skips_unchanged_files(py_mini: Path, tmp_path: Path):
    dbp = tmp_path / "g.db"
    scan_into(py_mini, dbp, exclude=[], workers=1)
    n_changed = update_into(py_mini, dbp, exclude=[])
    assert n_changed == 0


def test_update_removes_deleted_file(py_mini: Path, tmp_path: Path):
    dbp = tmp_path / "g.db"
    scan_into(py_mini, dbp, exclude=[], workers=1)
    (py_mini / "u.py").unlink()
    update_into(py_mini, dbp, exclude=[])
    db = sqlite3.connect(str(dbp))
    files = {r[0] for r in db.execute("SELECT path FROM files").fetchall()}
    assert not any(p.endswith("u.py") for p in files)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_update.py -v
```

Expected: FAIL — `update_into` not implemented.

- [ ] **Step 3: Implement `update_into`**

Append to `.github/tools/codegraph.py`:

```python
def update_into(root: Path, db_path: Path, exclude: list[str]) -> int:
    """Incremental update: scan only files whose mtime changed or are new; remove deleted.

    Returns count of files re-indexed (does not count deletions).
    """
    db = open_db(db_path)
    ensure_schema(db)
    existing = {row[0]: (row[1], row[2]) for row in db.execute(
        "SELECT path, mtime, sha256 FROM files").fetchall()}
    seen: set[str] = set()
    changed = 0
    for p in iter_files(root, exclude):
        if detect_lang(p) is None:
            continue
        rel = str(p.relative_to(root))
        seen.add(rel)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        prev = existing.get(rel)
        if prev is not None and abs(prev[0] - mtime) < 1e-6:
            continue  # unchanged
        # Delete prior records for this file
        db.execute("DELETE FROM files WHERE path = ?", (rel,))
        # Re-index
        rel_path, lang, sha, mt, lc, parse_err, extracted = _parse_one((rel, str(p), str(root)))
        cur = db.execute(
            "INSERT INTO files(path, lang, sha256, mtime, line_count, parse_error) "
            "VALUES (?,?,?,?,?,?)",
            (rel_path, lang, sha, mt, lc, parse_err),
        )
        if extracted is not None:
            _persist_extracted(db, cur.lastrowid, extracted)
        changed += 1
    # Remove rows for files that no longer exist
    for rel in list(existing.keys()):
        if rel not in seen:
            db.execute("DELETE FROM files WHERE path = ?", (rel,))
    db.commit()
    return changed
```

Wire up in `main`:

```python
    p_upd = sub.add_parser("update")
    p_upd.add_argument("--root", default=".")
    p_upd.add_argument("--db", default=".github/.cache/codegraph.db")
    p_upd.add_argument("--exclude", nargs="*", default=[])
```

```python
    if args.cmd == "update":
        n = update_into(Path(args.root), Path(args.db), args.exclude)
        print(f"updated {n} files in {args.db}")
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_update.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_update.py
git commit -m "feat(codegraph): incremental update via mtime + delete missing files"
```

---

### Task 15: `find` command

**Files:**
- Modify: `.github/tools/codegraph.py`
- Create: `tests/tools/test_codegraph_query.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_codegraph_query.py`:

```python
import sys
import shutil
import subprocess
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from codegraph import scan_into  # noqa: E402


@pytest.fixture
def graph(tmp_path: Path, request) -> tuple[Path, Path]:
    src = Path(request.config.rootpath) / "tests" / "tools" / "fixtures" / "py-mini"
    dst = tmp_path / "py-mini"
    shutil.copytree(src, dst)
    dbp = tmp_path / "g.db"
    scan_into(dst, dbp, exclude=[], workers=1)
    return dst, dbp


def run_cli(*args, db: Path):
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), *args, "--db", str(db), "--json"],
        capture_output=True, text=True, check=False,
    )
    return cp


def test_find_returns_matching_symbol(graph):
    _, dbp = graph
    cp = run_cli("find", "App", db=dbp)
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert any(s["name"] == "App" and s["kind"] == "class" for s in data)


def test_find_filtered_by_kind(graph):
    _, dbp = graph
    cp = run_cli("find", "run", "--kind", "method", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert all(s["kind"] == "method" for s in data)
    assert any(s["name"] == "run" for s in data)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_query.py::test_find_returns_matching_symbol -v
```

Expected: FAIL — `find` command not implemented.

- [ ] **Step 3: Implement `find`**

Add to `.github/tools/codegraph.py`:

```python
import json as _json


def cmd_find(name: str, db_path: Path, kind: str | None = None, lang: str | None = None) -> list[dict]:
    db = open_db(db_path)
    sql = ("SELECT s.id, s.name, s.qualified_name, s.kind, f.path, "
           "s.start_line, s.end_line, s.signature, f.lang "
           "FROM symbols s JOIN files f ON s.file_id = f.id WHERE s.name = ?")
    params: list = [name]
    if kind:
        sql += " AND s.kind = ?"
        params.append(kind)
    if lang:
        sql += " AND f.lang = ?"
        params.append(lang)
    sql += " ORDER BY f.path, s.start_line"
    rows = db.execute(sql, params).fetchall()
    keys = ["id", "name", "qualified_name", "kind", "file", "start_line", "end_line", "signature", "lang"]
    return [dict(zip(keys, r)) for r in rows]
```

Wire up:

```python
    p_find = sub.add_parser("find")
    p_find.add_argument("name")
    p_find.add_argument("--kind", default=None)
    p_find.add_argument("--lang", default=None)
    p_find.add_argument("--db", default=".github/.cache/codegraph.db")
    p_find.add_argument("--json", action="store_true")
```

```python
    if args.cmd == "find":
        rows = cmd_find(args.name, Path(args.db), args.kind, args.lang)
        if args.json:
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['file']}:{r['start_line']}  {r['kind']}  {r['qualified_name'] or r['name']}  {r['signature']}")
        return 0 if rows else 1
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_query.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_query.py
git commit -m "feat(codegraph): find command with --kind and --lang filters"
```

---

### Task 16: `callers` and `callees` commands

**Files:**
- Modify: `.github/tools/codegraph.py`
- Modify: `tests/tools/test_codegraph_query.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_codegraph_query.py`:

```python
def test_callees_for_run(graph):
    _, dbp = graph
    cp = run_cli("callees", "App.run", db=dbp)
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert any("helper" in c["callee_name"] for c in data)


def test_callers_for_helper(graph):
    _, dbp = graph
    cp = run_cli("callers", "helper", db=dbp)
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert any("run" in c["caller_qualified"] for c in data)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_query.py::test_callees_for_run -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `callers` / `callees`**

Add to `.github/tools/codegraph.py`:

```python
def cmd_callees(qualified_or_name: str, db_path: Path) -> list[dict]:
    db = open_db(db_path)
    rows = db.execute(
        "SELECT c.callee_name, c.line, f.path "
        "FROM calls c "
        "JOIN symbols s ON c.caller_symbol_id = s.id "
        "JOIN files f ON s.file_id = f.id "
        "WHERE s.qualified_name = ? OR s.name = ? "
        "ORDER BY f.path, c.line",
        (qualified_or_name, qualified_or_name),
    ).fetchall()
    return [{"callee_name": r[0], "line": r[1], "file": r[2]} for r in rows]


def cmd_callers(name: str, db_path: Path) -> list[dict]:
    db = open_db(db_path)
    # Match by callee_name or by resolved id
    rows = db.execute(
        "SELECT s.qualified_name, s.name, c.line, f.path "
        "FROM calls c "
        "LEFT JOIN symbols s ON c.caller_symbol_id = s.id "
        "LEFT JOIN files f ON s.file_id = f.id "
        "WHERE c.callee_name = ? OR c.callee_name LIKE ? "
        "ORDER BY f.path, c.line",
        (name, f"%.{name}"),
    ).fetchall()
    return [{"caller_qualified": r[0] or "", "caller_name": r[1] or "", "line": r[2], "file": r[3] or ""} for r in rows]
```

Wire up subcommands (similar pattern to `find`).

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_query.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_query.py
git commit -m "feat(codegraph): callers and callees commands"
```

---

### Task 17: `deps` and `impact` commands

**Files:**
- Modify: `.github/tools/codegraph.py`
- Modify: `tests/tools/test_codegraph_query.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_codegraph_query.py`:

```python
def test_deps_returns_imports_for_file(graph):
    py_root, dbp = graph
    cp = run_cli("deps", "m.py", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any(".u" in d["to_module"] for d in data)


def test_impact_returns_dependents(graph):
    # u.py is imported by m.py, so impact of u.py should include m.py
    _, dbp = graph
    cp = run_cli("impact", "u.py", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any(d["path"].endswith("m.py") for d in data)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_query.py::test_deps_returns_imports_for_file -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `deps` / `impact`**

```python
def cmd_deps(file_path: str, db_path: Path) -> list[dict]:
    db = open_db(db_path)
    rows = db.execute(
        "SELECT i.to_module, i.imported, i.alias, i.line "
        "FROM imports i JOIN files f ON i.from_file_id = f.id "
        "WHERE f.path = ? ORDER BY i.line",
        (file_path,),
    ).fetchall()
    return [{"to_module": r[0], "imported": r[1], "alias": r[2], "line": r[3]} for r in rows]


def cmd_impact(file_path: str, db_path: Path, depth: int = 2) -> list[dict]:
    """Return files that (transitively) import this file's module.

    Heuristic: a file's "module" is its path with extension stripped and slashes
    converted to dots; relative imports starting with '.' are matched against
    sibling files in the same dir.
    """
    db = open_db(db_path)
    # First, find direct dependents
    direct = db.execute(
        "SELECT DISTINCT f.path "
        "FROM imports i JOIN files f ON i.from_file_id = f.id "
        "WHERE i.to_module LIKE ? OR i.to_module = ?",
        (f"%{Path(file_path).stem}", Path(file_path).stem),
    ).fetchall()
    seen = {r[0] for r in direct}
    frontier = list(seen)
    out = [{"path": p, "depth": 1} for p in seen]
    cur_depth = 1
    while frontier and cur_depth < depth:
        cur_depth += 1
        next_frontier = []
        for fp in frontier:
            stem = Path(fp).stem
            rows = db.execute(
                "SELECT DISTINCT f.path FROM imports i JOIN files f ON i.from_file_id = f.id "
                "WHERE i.to_module LIKE ? AND f.path NOT IN (" + ",".join(["?"] * len(seen)) + ")",
                (f"%{stem}", *seen),
            ).fetchall() if seen else []
            for r in rows:
                next_frontier.append(r[0])
                seen.add(r[0])
                out.append({"path": r[0], "depth": cur_depth})
        frontier = next_frontier
    return out
```

Wire up subcommands.

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_query.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_query.py
git commit -m "feat(codegraph): deps and impact commands (forward and reverse imports)"
```

---

### Task 18: `search` command (FTS over symbols)

**Files:**
- Modify: `.github/tools/codegraph.py`
- Modify: `tests/tools/test_codegraph_query.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_codegraph_query.py`:

```python
def test_search_finds_by_name_substring(graph):
    _, dbp = graph
    cp = run_cli("search", "helper", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any(s["name"] == "helper" for s in data)


def test_search_uses_fts_for_phrase(graph):
    # Add a docstring; "Calls helper" should be findable via FTS
    py_root, dbp = graph
    f = py_root / "u.py"
    f.write_text('def helper(n):\n    """Calls multiply by 2."""\n    return n * 2\n')
    # Re-index
    import sys, subprocess
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    subprocess.run([sys.executable, str(tool), "update", "--root", str(py_root), "--db", str(dbp)],
                   check=True)
    cp = run_cli("search", "multiply", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any("helper" in s["name"] for s in data)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_query.py::test_search_finds_by_name_substring -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `search`**

```python
def cmd_search(query: str, db_path: Path, limit: int = 20) -> list[dict]:
    db = open_db(db_path)
    rows = db.execute(
        "SELECT s.name, s.qualified_name, s.kind, f.path, s.start_line, "
        "snippet(symbols_fts, 3, '<<', '>>', '...', 8) "
        "FROM symbols_fts JOIN symbols s ON symbols_fts.rowid = s.id "
        "JOIN files f ON s.file_id = f.id "
        "WHERE symbols_fts MATCH ? "
        "ORDER BY rank LIMIT ?",
        (query, limit),
    ).fetchall()
    return [{"name": r[0], "qualified_name": r[1], "kind": r[2], "file": r[3],
             "start_line": r[4], "snippet": r[5]} for r in rows]
```

Wire up subcommand.

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_query.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_query.py
git commit -m "feat(codegraph): search command via FTS5 over symbols"
```

---

### Task 19: `envelope` command — token-budgeted context packet

**Files:**
- Modify: `.github/tools/codegraph.py`
- Create: `tests/tools/test_codegraph_envelope.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_codegraph_envelope.py`:

```python
import sys
import shutil
import subprocess
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from codegraph import scan_into  # noqa: E402


@pytest.fixture
def graph(tmp_path: Path, request):
    src = Path(request.config.rootpath) / "tests" / "tools" / "fixtures" / "py-mini"
    dst = tmp_path / "py-mini"
    shutil.copytree(src, dst)
    dbp = tmp_path / "g.db"
    scan_into(dst, dbp, exclude=[], workers=1)
    return dst, dbp


def test_envelope_for_symbol_includes_signature_and_callers(graph):
    py_root, dbp = graph
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), "envelope", "helper", "--db", str(dbp),
         "--root", str(py_root), "--budget", "1000"],
        capture_output=True, text=True, check=True,
    )
    out = cp.stdout
    assert "## Symbol: helper" in out
    assert "## Callers" in out
    assert "m.py" in out  # caller file
    # Token budget: must not exceed budget * 4 chars (approx)
    assert len(out) <= 1000 * 4 + 200


def test_envelope_for_file_lists_top_symbols(graph):
    py_root, dbp = graph
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), "envelope", "m.py", "--db", str(dbp),
         "--root", str(py_root), "--budget", "1000"],
        capture_output=True, text=True, check=True,
    )
    assert "## File: m.py" in cp.stdout
    assert "App" in cp.stdout
    assert "main" in cp.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_envelope.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `envelope`**

```python
def cmd_envelope(target: str, db_path: Path, root_path: Path, budget: int = 2000) -> str:
    """Build a context envelope for a symbol or file path, capped at budget tokens."""
    db = open_db(db_path)
    out: list[str] = []
    used = 0

    def add(text: str) -> bool:
        nonlocal used
        t = (len(text) + 3) // 4
        if used + t > budget:
            return False
        out.append(text)
        used += t
        return True

    # Decide: symbol or file?
    is_file = "/" in target or target.endswith((".py", ".ts", ".tsx", ".js", ".go", ".java", ".rs", ".c", ".cpp", ".h"))
    if is_file:
        rows = db.execute(
            "SELECT id, lang FROM files WHERE path = ?", (target,)
        ).fetchone()
        if not rows:
            return f"# File not found in graph: {target}\n"
        file_id, lang = rows
        add(f"# File: {target}\n\n## File: {target} (lang={lang})\n")
        # Top symbols
        syms = db.execute(
            "SELECT name, kind, start_line, signature FROM symbols WHERE file_id = ? "
            "ORDER BY start_line LIMIT 20",
            (file_id,),
        ).fetchall()
        if syms:
            add("\n## Symbols in file\n")
            for s in syms:
                add(f"- L{s[2]}  {s[1]:<7}  `{s[3]}`\n")
        # Imports
        imps = db.execute(
            "SELECT to_module, imported, alias FROM imports WHERE from_file_id = ? LIMIT 20",
            (file_id,),
        ).fetchall()
        if imps:
            add("\n## Imports\n")
            for i in imps:
                add(f"- {i[0]}  {i[1] or ''}  {('as ' + i[2]) if i[2] else ''}\n")
        return "".join(out)

    # Symbol path
    sym = db.execute(
        "SELECT s.id, s.name, s.kind, s.qualified_name, s.signature, s.docstring, "
        "s.start_line, s.end_line, f.path "
        "FROM symbols s JOIN files f ON s.file_id = f.id "
        "WHERE s.qualified_name = ? OR s.name = ? "
        "LIMIT 1",
        (target, target),
    ).fetchone()
    if not sym:
        return f"# Symbol not found in graph: {target}\n"
    sid, name, kind, qual, sig, doc, sl, el, fpath = sym
    add(f"# Envelope: {qual or name}\n\n## Symbol: {qual or name}\n")
    add(f"- file: `{fpath}` lines {sl}-{el}\n- kind: {kind}\n- signature: `{sig}`\n")
    if doc:
        add(f"- doc: {doc[:300]}\n")
    # Body excerpt (read from file if budget allows)
    full = (root_path / fpath).read_text(errors="replace") if (root_path / fpath).exists() else ""
    if full:
        body_lines = full.splitlines()[sl - 1:el]
        body = "\n".join(body_lines[:40])
        add(f"\n```\n{body}\n```\n")
    # Callers
    callers = db.execute(
        "SELECT s2.qualified_name, f2.path, c.line "
        "FROM calls c "
        "LEFT JOIN symbols s2 ON c.caller_symbol_id = s2.id "
        "LEFT JOIN files f2 ON s2.file_id = f2.id "
        "WHERE c.callee_name = ? OR c.callee_name LIKE ? "
        "LIMIT 10",
        (name, f"%.{name}"),
    ).fetchall()
    if callers:
        add("\n## Callers\n")
        for q, p, ln in callers:
            add(f"- {p}:{ln}  {q or ''}\n")
    # Callees
    callees = db.execute(
        "SELECT callee_name, line FROM calls WHERE caller_symbol_id = ? LIMIT 10",
        (sid,),
    ).fetchall()
    if callees:
        add("\n## Callees\n")
        for c, ln in callees:
            add(f"- {c} (L{ln})\n")
    return "".join(out)
```

Wire up subcommand.

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_envelope.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_envelope.py
git commit -m "feat(codegraph): envelope command builds token-budgeted context packet"
```

---

### Task 20: `stats` and `why-stale` commands

**Files:**
- Modify: `.github/tools/codegraph.py`
- Modify: `tests/tools/test_codegraph_query.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_codegraph_query.py`:

```python
def test_stats_reports_counts(graph):
    _, dbp = graph
    cp = run_cli("stats", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["files"] >= 2
    assert data["symbols"] >= 4
    assert "last_scan" in data


def test_why_stale_after_edit(graph):
    py_root, dbp = graph
    # Modify u.py without running update
    import time
    time.sleep(0.05)
    (py_root / "u.py").write_text("def helper(n):\n    return n + 999\n")
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), "why-stale", "--db", str(dbp),
         "--root", str(py_root), "--json"],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["stale_files"] >= 1
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_query.py::test_stats_reports_counts -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `stats` and `why-stale`**

```python
def cmd_stats(db_path: Path) -> dict:
    db = open_db(db_path)
    files = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    symbols = db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    imports = db.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
    calls = db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    parse_errors = db.execute("SELECT COUNT(*) FROM files WHERE parse_error=1").fetchone()[0]
    last_scan = db.execute("SELECT MAX(mtime) FROM files").fetchone()[0]
    return {
        "files": files, "symbols": symbols, "imports": imports, "calls": calls,
        "parse_errors": parse_errors, "last_scan": last_scan,
    }


def cmd_why_stale(root: Path, db_path: Path, exclude: list[str]) -> dict:
    db = open_db(db_path)
    indexed = {r[0]: r[1] for r in db.execute("SELECT path, mtime FROM files").fetchall()}
    stale = 0
    new = 0
    for p in iter_files(root, exclude):
        if detect_lang(p) is None:
            continue
        rel = str(p.relative_to(root))
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        prev = indexed.get(rel)
        if prev is None:
            new += 1
        elif abs(prev - mtime) >= 1e-6:
            stale += 1
    return {"stale_files": stale, "new_files": new, "total_indexed": len(indexed)}
```

Wire up subcommands.

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_query.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_query.py
git commit -m "feat(codegraph): stats and why-stale commands"
```

---

### Task 21: `module` and `refs` commands

**Files:**
- Modify: `.github/tools/codegraph.py`
- Modify: `tests/tools/test_codegraph_query.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_codegraph_query.py`:

```python
def test_module_summary_lists_files_in_dir(graph):
    py_root, dbp = graph
    cp = run_cli("module", ".", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["file_count"] >= 2
    assert any(f["path"].endswith("m.py") for f in data["files"])


def test_refs_finds_uses_of_symbol(graph):
    _, dbp = graph
    cp = run_cli("refs", "helper", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    # helper is called from m.py
    assert any(r["file"].endswith("m.py") for r in data)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_query.py::test_module_summary_lists_files_in_dir -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `module` and `refs`**

`refs` is computed from `calls.callee_name LIKE name` since we don't index assignments separately yet (deferred); this gives a useful approximation:

```python
def cmd_module(path: str, db_path: Path) -> dict:
    db = open_db(db_path)
    if path in (".", ""):
        prefix = ""
    else:
        prefix = path.rstrip("/") + "/"
    rows = db.execute(
        "SELECT path, lang, line_count FROM files WHERE path LIKE ? ORDER BY path",
        (f"{prefix}%",),
    ).fetchall()
    files = [{"path": r[0], "lang": r[1], "lines": r[2]} for r in rows]
    file_ids = [r[0] for r in db.execute("SELECT id FROM files WHERE path LIKE ?",
                                         (f"{prefix}%",)).fetchall()]
    sym_count = 0
    if file_ids:
        sym_count = db.execute(
            "SELECT COUNT(*) FROM symbols WHERE file_id IN (" +
            ",".join("?" * len(file_ids)) + ")", file_ids
        ).fetchone()[0]
    return {"path": path, "file_count": len(files), "symbol_count": sym_count, "files": files}


def cmd_refs(name: str, db_path: Path) -> list[dict]:
    db = open_db(db_path)
    # Use calls table as a proxy for refs (full ref tracking deferred)
    rows = db.execute(
        "SELECT f.path, c.line, c.callee_name "
        "FROM calls c "
        "LEFT JOIN symbols s ON c.caller_symbol_id = s.id "
        "JOIN files f ON COALESCE(s.file_id, "
        " (SELECT file_id FROM symbols WHERE id = c.caller_symbol_id)) = f.id "
        "WHERE c.callee_name = ? OR c.callee_name LIKE ?",
        (name, f"%.{name}"),
    ).fetchall()
    # Fallback when caller is unresolved: just join through calls -> filter by callee
    if not rows:
        rows = db.execute(
            "SELECT 'unknown', line, callee_name FROM calls WHERE callee_name = ? OR callee_name LIKE ?",
            (name, f"%.{name}"),
        ).fetchall()
    return [{"file": r[0], "line": r[1], "callee_name": r[2]} for r in rows]
```

Wire up subcommands.

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_query.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_query.py
git commit -m "feat(codegraph): module summary and refs commands"
```

---

### Task 22: Profile-aware behavior gating

**Files:**
- Modify: `.github/tools/codegraph.py`
- Create: `tests/tools/test_codegraph_profile.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_codegraph_profile.py`:

```python
import sys
import shutil
import subprocess
from pathlib import Path

import pytest


def write_config(tmp_repo: Path, profile: str):
    """Write a minimal config.yaml with the given profile."""
    cfg = f"""
profile: {profile}
features: {{ code_graph: auto }}
codegraph: {{ exclude: [], languages: {{ tier1: [python], tier2: [] }}, budgets: {{ envelope_default_tokens: 2000, impact_max_depth: 3 }}, scan: {{ workers: 1, batch_size: 100 }} }}
memory: {{ budgets: {{}}, compaction_model: claude-sonnet-4-6, archive_after_days: 7 }}
dispatch: {{}}
models: {{}}
routing: {{}}
"""
    (tmp_repo / ".github" / "config.yaml").write_text(cfg)


def copy_tools(tmp_repo: Path, request):
    project_root = Path(request.config.rootpath)
    src = project_root / ".github" / "tools"
    dst = tmp_repo / ".github" / "tools"
    for name in ["__init__.py", "config.py", "codegraph.py"]:
        s = src / name
        if s.exists():
            shutil.copy(s, dst / name)
    for sub in ["_lib"]:
        srcd = src / sub
        if srcd.exists():
            shutil.copytree(srcd, dst / sub, dirs_exist_ok=True)


def test_tiny_profile_scan_is_noop(tmp_repo: Path, request):
    write_config(tmp_repo, "tiny")
    copy_tools(tmp_repo, request)
    (tmp_repo / "x.py").write_text("def f(): pass")
    tool = tmp_repo / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), "scan", "--root", str(tmp_repo)],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode == 0
    assert "disabled" in cp.stdout.lower() or "tiny" in cp.stdout.lower()
    # No db created
    assert not (tmp_repo / ".github" / ".cache" / "codegraph.db").exists()


def test_small_profile_skips_calls_and_refs(tmp_repo: Path, request):
    write_config(tmp_repo, "small")
    copy_tools(tmp_repo, request)
    (tmp_repo / "x.py").write_text("def f(): return g()\ndef g(): return 1\n")
    tool = tmp_repo / ".github" / "tools" / "codegraph.py"
    subprocess.run([sys.executable, str(tool), "scan", "--root", str(tmp_repo)],
                   capture_output=True, text=True, check=True)
    import sqlite3
    db = sqlite3.connect(str(tmp_repo / ".github" / ".cache" / "codegraph.db"))
    syms = db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    calls = db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    assert syms >= 2
    assert calls == 0  # symbols-only mode
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_codegraph_profile.py -v
```

Expected: FAIL — gating not implemented.

- [ ] **Step 3: Add profile gating to `codegraph.py`**

In `.github/tools/codegraph.py`, add at top after imports:

```python
from config import load_config, resolve_feature


def _active_code_graph_mode(repo_root: Path) -> str:
    """Resolve features.code_graph -> one of 'full', 'symbols-only', 'off'."""
    cfg_path = repo_root / ".github" / "config.yaml"
    if not cfg_path.exists():
        return "full"  # safe default if no config
    cfg = load_config(cfg_path)
    val = cfg.features.get("code_graph", "auto")
    return resolve_feature("code_graph", val, cfg.profile)
```

In `scan_into`, at the very top:

```python
def scan_into(root: Path, db_path: Path, exclude: list[str], workers: int = 1) -> int | str:
    mode = _active_code_graph_mode(root)
    if mode == "off":
        return "graph disabled at this profile"
    # ... rest as before
```

In `_persist_extracted`, gate calls/refs by mode:

```python
def _persist_extracted(db: sqlite3.Connection, file_id: int, ex, mode: str = "full") -> None:
    sym_id_by_qual: dict[str, int] = {}
    for s in ex.symbols:
        cur = db.execute(
            "INSERT INTO symbols(file_id, name, qualified_name, kind, start_line, "
            "end_line, signature, docstring, visibility) VALUES (?,?,?,?,?,?,?,?,?)",
            (file_id, s.name, s.qualified_name, s.kind, s.start_line, s.end_line,
             s.signature, s.docstring, s.visibility),
        )
        if s.qualified_name:
            sym_id_by_qual[s.qualified_name] = cur.lastrowid
    if mode == "symbols-only":
        return
    for i in ex.imports:
        db.execute(
            "INSERT INTO imports(from_file_id, to_module, imported, alias, line) "
            "VALUES (?,?,?,?,?)",
            (file_id, i.to_module, i.imported, i.alias, i.line),
        )
    for c in ex.calls:
        caller_id = sym_id_by_qual.get(c.caller_name)
        db.execute(
            "INSERT INTO calls(caller_symbol_id, callee_name, callee_symbol_id, line) "
            "VALUES (?,?,?,?)",
            (caller_id, c.callee_name, None, c.line),
        )
```

Pass mode through `scan_into` and `update_into` to `_persist_extracted`.

In `main`, when `cmd == "scan"` and result is a string, print it and return 0.

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_codegraph_profile.py -v
pytest tests/tools/ -v --tb=short    # full suite still green
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/codegraph.py tests/tools/test_codegraph_profile.py
git commit -m "feat(codegraph): profile-aware gating (tiny=off, small=symbols-only)"
```

---

### Task 23: TypeScript fixture + e2e test on TS

**Files:**
- Create: `tests/tools/fixtures/ts-mini/foo.ts`
- Create: `tests/tools/fixtures/ts-mini/index.ts`
- Modify: `tests/tools/test_codegraph_query.py`

- [ ] **Step 1: Write the failing test + fixture**

`tests/tools/fixtures/ts-mini/foo.ts`:

```typescript
export function helper(x: number): number {
    return x * 2;
}
```

`tests/tools/fixtures/ts-mini/index.ts`:

```typescript
import { helper } from './foo';

export class App {
    run(x: number): number {
        return helper(x) + 1;
    }
}

export function main() {
    return new App().run(3);
}
```

Append to `tests/tools/test_codegraph_query.py`:

```python
@pytest.fixture
def ts_graph(tmp_path: Path, request):
    src = Path(request.config.rootpath) / "tests" / "tools" / "fixtures" / "ts-mini"
    dst = tmp_path / "ts-mini"
    shutil.copytree(src, dst)
    dbp = tmp_path / "g.db"
    scan_into(dst, dbp, exclude=[], workers=1)
    return dst, dbp


def test_ts_find_class_and_method(ts_graph):
    _, dbp = ts_graph
    cp = run_cli("find", "App", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any(s["kind"] == "class" for s in data)
    cp = run_cli("find", "run", "--kind", "method", db=dbp)
    data = json.loads(cp.stdout)
    assert any(s["name"] == "run" for s in data)


def test_ts_impact_returns_dependents(ts_graph):
    _, dbp = ts_graph
    cp = run_cli("impact", "foo.ts", db=dbp)
    data = json.loads(cp.stdout)
    assert any(d["path"].endswith("index.ts") for d in data)
```

(Also add `import shutil` if not present.)

- [ ] **Step 2: Run the test to verify it fails (only if there are bugs)**

```bash
pytest tests/tools/test_codegraph_query.py::test_ts_find_class_and_method -v
```

Expected: PASS — TS adapter and queries already work; test verifies end-to-end on TS.

- [ ] **Step 3: (No code changes if it passes; otherwise debug whichever subsystem failed)**

- [ ] **Step 4: Run the full suite**

```bash
pytest tests/tools/ -v --tb=short
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add tests/tools/fixtures/ts-mini/ tests/tools/test_codegraph_query.py
git commit -m "test(codegraph): TypeScript fixture + e2e tests for find/impact"
```

---

### Task 24: Performance smoke test (mid-size synthetic)

**Files:**
- Create: `tests/tools/test_codegraph_perf.py`

- [ ] **Step 1: Write the test**

`tests/tools/test_codegraph_perf.py`:

```python
"""Smoke test: scan must handle ~1000 small files in < 30s.

This is a performance floor, not a benchmark. Real-world scans are bounded by
disk and parser, not the framework. If this fails, investigate parser/cold-cache
issues before declaring a regression.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from codegraph import scan_into  # noqa: E402


@pytest.mark.skipif(not __import__("os").environ.get("RUN_PERF"),
                    reason="set RUN_PERF=1 to run perf smoke test")
def test_scan_1000_python_files_under_30s(tmp_path: Path):
    src = tmp_path / "synth"
    src.mkdir()
    for i in range(1000):
        (src / f"m{i}.py").write_text(
            f"def f{i}(x):\n    '''doc {i}.'''\n    return x + {i}\n"
        )
    dbp = tmp_path / "g.db"
    t0 = time.time()
    n = scan_into(src, dbp, exclude=[], workers=4)
    elapsed = time.time() - t0
    assert n == 1000
    assert elapsed < 30.0, f"scan took {elapsed:.1f}s, expected < 30s"
```

- [ ] **Step 2: Run the test (opt-in)**

```bash
RUN_PERF=1 pytest tests/tools/test_codegraph_perf.py -v -s
```

Expected: PASS in well under 30s on most machines.

If it fails with > 30s, investigate (cold parser cache? worker count too high?) before declaring a regression.

- [ ] **Step 3: (No code changes if it passes)**

- [ ] **Step 4: Run full suite (without perf)**

```bash
pytest tests/tools/ -v --tb=short
```

Expected: all PASS, perf test SKIPPED.

- [ ] **Step 5: Commit**

```bash
git add tests/tools/test_codegraph_perf.py
git commit -m "test(codegraph): opt-in perf smoke test (1000 files < 30s)"
```

---

### Task 25: End-to-end CLI smoke test (subprocess across all commands)

**Files:**
- Create: `tests/tools/test_codegraph_e2e.py`

- [ ] **Step 1: Write the test**

`tests/tools/test_codegraph_e2e.py`:

```python
"""E2E: drive codegraph.py via subprocess across all commands."""
import sys
import shutil
import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def py_repo(tmp_path: Path, request) -> Path:
    src = Path(request.config.rootpath) / "tests" / "tools" / "fixtures" / "py-mini"
    dst = tmp_path / "py-mini"
    shutil.copytree(src, dst)
    return dst


def py(tool: Path, *args, expect_code: int = 0) -> str:
    cp = subprocess.run([sys.executable, str(tool), *args],
                        capture_output=True, text=True, check=False)
    assert cp.returncode == expect_code, f"args={args!r}\nstdout={cp.stdout}\nstderr={cp.stderr}"
    return cp.stdout


def test_e2e_full_cli_flow(py_repo: Path, tmp_path: Path):
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    db = tmp_path / "g.db"

    # scan
    py(tool, "scan", "--root", str(py_repo), "--db", str(db))
    # stats
    out = py(tool, "stats", "--db", str(db), "--json")
    stats = json.loads(out)
    assert stats["files"] >= 2
    # find
    out = py(tool, "find", "App", "--db", str(db), "--json")
    assert "App" in out
    # callers / callees
    py(tool, "callers", "helper", "--db", str(db), "--json")
    py(tool, "callees", "App.run", "--db", str(db), "--json")
    # deps / impact
    py(tool, "deps", "m.py", "--db", str(db), "--json")
    py(tool, "impact", "u.py", "--db", str(db), "--json")
    # search
    py(tool, "search", "helper", "--db", str(db), "--json")
    # envelope
    py(tool, "envelope", "helper", "--root", str(py_repo), "--db", str(db),
       "--budget", "1500")
    # update no-op
    out = py(tool, "update", "--root", str(py_repo), "--db", str(db))
    assert "0 files" in out or "updated 0" in out
    # why-stale
    py(tool, "why-stale", "--root", str(py_repo), "--db", str(db), "--json")
    # module
    py(tool, "module", ".", "--db", str(db), "--json")
    # refs
    py(tool, "refs", "helper", "--db", str(db), "--json")
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/tools/test_codegraph_e2e.py -v
```

Expected: PASS — every command works end-to-end via subprocess.

- [ ] **Step 3: Fix any failing command's wiring**

If a subcommand was misregistered or its `--json` flag was missing, fix it now and re-run.

- [ ] **Step 4: Run the full Plan A1 + A2 suite**

```bash
pytest tests/tools/ -v --tb=short
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add tests/tools/test_codegraph_e2e.py
git commit -m "test(codegraph): end-to-end CLI flow across all commands"
```

---

## Self-review checklist

| Spec section | Plan A2 coverage |
|---|---|
| §3.1 SQLite schema | Task 1 |
| §3.1 file walker / exclude patterns | Task 2 |
| §3.1 tier1 languages (py, ts, tsx, js, go, java, rust, c, cpp) | Tasks 5–11 |
| §3.1 scan command + multiprocessing | Tasks 12, 13 |
| §3.1 incremental update | Task 14 |
| §3.1 find/refs/callers/callees/deps/impact/search/envelope/stats/why-stale/module | Tasks 15–21 |
| §2.5 profile-aware behavior (tiny/small/medium+) | Task 22 |
| §3.1 performance targets | Task 24 (smoke), full perf test deferred to Plan D |

**Gaps Plan A2 deliberately leaves for later plans:**

- True call resolution (`callee_symbol_id` set when callee is in same project) — current plan inserts NULL; can be enriched by a Plan A2.5 pass that links calls to symbols by name/scope.
- Tier2 languages (Ruby, Kotlin, Swift, etc.) — adapter stubs can be added later following the Python/TS pattern.
- Git-diff-driven incremental update (currently mtime-based) — Plan A3 can add when wiring bootstrap.sh.
- Full reference tracking distinct from calls (assignment, annotation reads) — deferred; current `refs` command approximates from `calls`.

---

## Final verification

```bash
git stash; git stash pop
pytest tests/tools/ -v --tb=short
```

Expected: all tests PASS.

When green, announce:

> Plan A2 complete. Next: Plan A3 — bootstrap.sh with profile detection, wiring A1 + A2 together for `/init`.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-05-plan-a2-codegraph.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch with checkpoints for review.

**Which approach?**
