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
