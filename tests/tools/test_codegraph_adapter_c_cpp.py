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
