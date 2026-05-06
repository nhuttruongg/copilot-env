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
