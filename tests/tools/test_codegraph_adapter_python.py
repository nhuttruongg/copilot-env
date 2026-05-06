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
