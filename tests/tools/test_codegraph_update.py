import sys
import shutil
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
