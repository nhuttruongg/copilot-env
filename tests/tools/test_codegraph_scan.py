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


def test_scan_with_workers_2_matches_single(py_mini: Path, tmp_path: Path):
    db1 = tmp_path / "single.db"
    db2 = tmp_path / "parallel.db"
    n1 = scan_into(py_mini, db1, exclude=[], workers=1)
    n2 = scan_into(py_mini, db2, exclude=[], workers=2)
    assert n1 == n2
    s1 = sorted(sqlite3.connect(str(db1)).execute("SELECT name FROM symbols ORDER BY name").fetchall())
    s2 = sorted(sqlite3.connect(str(db2)).execute("SELECT name FROM symbols ORDER BY name").fetchall())
    assert s1 == s2
