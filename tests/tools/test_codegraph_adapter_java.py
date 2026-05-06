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
