import sys
import shutil
import subprocess
import sqlite3
from pathlib import Path

import pytest


def write_config(tmp_repo: Path, profile: str):
    cfg = f"""
profile: {profile}
features: {{ code_graph: auto }}
codegraph: {{ exclude: [], languages: {{ tier1: [python], tier2: [] }}, budgets: {{ envelope_default_tokens: 2000, impact_max_depth: 3 }}, scan: {{ workers: 1, batch_size: 100 }} }}
memory: {{ budgets: {{}}, compaction_model: claude-sonnet-4-6, archive_after_days: 7 }}
dispatch: {{}}
models: {{}}
routing: {{}}
"""
    (tmp_repo / ".github" / "config.yaml").write_text(cfg)


def copy_tools(tmp_repo: Path, request):
    project_root = Path(request.config.rootpath)
    src = project_root / ".github" / "tools"
    dst = tmp_repo / ".github" / "tools"
    dst.mkdir(parents=True, exist_ok=True)
    for name in ["__init__.py", "config.py", "codegraph.py"]:
        s = src / name
        if s.exists():
            shutil.copy(s, dst / name)
    for sub in ["_lib"]:
        srcd = src / sub
        if srcd.exists():
            shutil.copytree(srcd, dst / sub, dirs_exist_ok=True)


def test_tiny_profile_scan_is_noop(tmp_repo: Path, request):
    write_config(tmp_repo, "tiny")
    copy_tools(tmp_repo, request)
    (tmp_repo / "x.py").write_text("def f(): pass")
    tool = tmp_repo / ".github" / "tools" / "codegraph.py"
    cp = subprocess.run(
        [sys.executable, str(tool), "scan", "--root", str(tmp_repo)],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode == 0
    assert "disabled" in cp.stdout.lower() or "tiny" in cp.stdout.lower()
    assert not (tmp_repo / ".github" / ".cache" / "codegraph.db").exists()


def test_small_profile_skips_calls_and_refs(tmp_repo: Path, request):
    write_config(tmp_repo, "small")
    copy_tools(tmp_repo, request)
    (tmp_repo / "x.py").write_text("def f(): return g()\ndef g(): return 1\n")
    tool = tmp_repo / ".github" / "tools" / "codegraph.py"
    subprocess.run([sys.executable, str(tool), "scan", "--root", str(tmp_repo)],
                   capture_output=True, text=True, check=True)
    db = sqlite3.connect(str(tmp_repo / ".github" / ".cache" / "codegraph.db"))
    syms = db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    calls = db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    assert syms >= 2
    assert calls == 0  # symbols-only mode
