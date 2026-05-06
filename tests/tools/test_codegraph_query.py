import sys
import shutil
import subprocess
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from codegraph import scan_into  # noqa: E402


@pytest.fixture
def graph(tmp_path: Path, request) -> tuple[Path, Path]:
    src = Path(request.config.rootpath) / "tests" / "tools" / "fixtures" / "py-mini"
    dst = tmp_path / "py-mini"
    shutil.copytree(src, dst)
    dbp = tmp_path / "g.db"
    scan_into(dst, dbp, exclude=[], workers=1)
    return dst, dbp


@pytest.fixture
def ts_graph(tmp_path: Path, request):
    src = Path(request.config.rootpath) / "tests" / "tools" / "fixtures" / "ts-mini"
    dst = tmp_path / "ts-mini"
    shutil.copytree(src, dst)
    dbp = tmp_path / "g.db"
    scan_into(dst, dbp, exclude=[], workers=1)
    return dst, dbp


def run_cli(*args, db: Path):
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), *args, "--db", str(db), "--json"],
        capture_output=True, text=True, check=False,
    )
    return cp


def test_find_returns_matching_symbol(graph):
    _, dbp = graph
    cp = run_cli("find", "App", db=dbp)
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert any(s["name"] == "App" and s["kind"] == "class" for s in data)


def test_find_filtered_by_kind(graph):
    _, dbp = graph
    cp = run_cli("find", "run", "--kind", "method", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert all(s["kind"] == "method" for s in data)
    assert any(s["name"] == "run" for s in data)


def test_callees_for_run(graph):
    _, dbp = graph
    cp = run_cli("callees", "App.run", db=dbp)
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert any("helper" in c["callee_name"] for c in data)


def test_callers_for_helper(graph):
    _, dbp = graph
    cp = run_cli("callers", "helper", db=dbp)
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert any("run" in c["caller_qualified"] for c in data)


def test_deps_returns_imports_for_file(graph):
    py_root, dbp = graph
    cp = run_cli("deps", "m.py", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any(".u" in d["to_module"] for d in data)


def test_impact_returns_dependents(graph):
    _, dbp = graph
    cp = run_cli("impact", "u.py", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any(d["path"].endswith("m.py") for d in data)


def test_search_finds_by_name_substring(graph):
    _, dbp = graph
    cp = run_cli("search", "helper", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any(s["name"] == "helper" for s in data)


def test_search_uses_fts_for_phrase(graph):
    py_root, dbp = graph
    f = py_root / "u.py"
    f.write_text('def helper(n):\n    """Calls multiply by 2."""\n    return n * 2\n')
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    subprocess.run([sys.executable, str(tool), "update",
                    "--root", str(py_root), "--db", str(dbp)], check=True)
    cp = run_cli("search", "multiply", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any("helper" in s["name"] for s in data)


def test_stats_reports_counts(graph):
    _, dbp = graph
    cp = run_cli("stats", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["files"] >= 2
    assert data["symbols"] >= 4
    assert "last_scan" in data


def test_why_stale_after_edit(graph):
    py_root, dbp = graph
    import time
    time.sleep(0.05)
    (py_root / "u.py").write_text("def helper(n):\n    return n + 999\n")
    project_root = Path(__file__).resolve().parents[2]
    tool = project_root / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), "why-stale",
         "--db", str(dbp), "--root", str(py_root), "--json"],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["stale_files"] >= 1


def test_module_summary_lists_files_in_dir(graph):
    py_root, dbp = graph
    cp = run_cli("module", ".", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["file_count"] >= 2
    assert any(f["path"].endswith("m.py") for f in data["files"])


def test_refs_finds_uses_of_symbol(graph):
    _, dbp = graph
    cp = run_cli("refs", "helper", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any(r["file"].endswith("m.py") for r in data)


def test_ts_find_class_and_method(ts_graph):
    _, dbp = ts_graph
    cp = run_cli("find", "App", db=dbp)
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert any(s["kind"] == "class" for s in data)
    cp = run_cli("find", "run", "--kind", "method", db=dbp)
    data = json.loads(cp.stdout)
    assert any(s["name"] == "run" for s in data)


def test_ts_impact_returns_dependents(ts_graph):
    _, dbp = ts_graph
    cp = run_cli("impact", "foo.ts", db=dbp)
    data = json.loads(cp.stdout)
    assert any(d["path"].endswith("index.ts") for d in data)
