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
