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
