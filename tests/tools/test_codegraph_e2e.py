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
    assert cp.returncode == expect_code, (
        f"args={args!r}\nstdout={cp.stdout}\nstderr={cp.stderr}"
    )
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
