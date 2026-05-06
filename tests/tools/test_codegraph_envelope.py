import sys
import shutil
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from codegraph import scan_into  # noqa: E402


@pytest.fixture
def graph(tmp_path: Path, request):
    src = Path(request.config.rootpath) / "tests" / "tools" / "fixtures" / "py-mini"
    dst = tmp_path / "py-mini"
    shutil.copytree(src, dst)
    dbp = tmp_path / "g.db"
    scan_into(dst, dbp, exclude=[], workers=1)
    return dst, dbp


def test_envelope_for_symbol_includes_signature_and_callers(graph):
    py_root, dbp = graph
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), "envelope", "helper",
         "--db", str(dbp), "--root", str(py_root), "--budget", "1000"],
        capture_output=True, text=True, check=True,
    )
    out = cp.stdout
    assert "## Symbol: helper" in out
    assert "## Callers" in out
    assert "m.py" in out
    assert len(out) <= 1000 * 4 + 200


def test_envelope_for_file_lists_top_symbols(graph):
    py_root, dbp = graph
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), "envelope", "m.py",
         "--db", str(dbp), "--root", str(py_root), "--budget", "1000"],
        capture_output=True, text=True, check=True,
    )
    assert "## File: m.py" in cp.stdout
    assert "App" in cp.stdout
    assert "main" in cp.stdout
