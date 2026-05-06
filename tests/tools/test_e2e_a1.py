"""End-to-end smoke test: simulate one session's worth of memory + session activity.

This test does not invoke an LLM; it only exercises the CLI surface end to end.
"""
import sys
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tools(tmp_repo: Path, request) -> dict[str, Path]:
    project_root = Path(request.config.rootpath)
    src = project_root / ".github" / "tools"
    dst = tmp_repo / ".github" / "tools"
    for name in ["__init__.py", "config.py", "memory.py", "session.py"]:
        s = src / name
        if s.exists():
            shutil.copy(s, dst / name)
    (dst / "_lib").mkdir(exist_ok=True)
    for name in ["__init__.py", "text.py", "io.py"]:
        s = src / "_lib" / name
        if s.exists():
            shutil.copy(s, dst / "_lib" / name)
    cfg = project_root / ".github" / "config.yaml"
    (tmp_repo / ".github" / "config.yaml").write_text(cfg.read_text())
    return {"memory": dst / "memory.py", "session": dst / "session.py"}


def py(tool: Path, *args: str) -> str:
    cp = subprocess.run([sys.executable, str(tool), *args],
                        capture_output=True, text=True, check=True)
    return cp.stdout


def test_e2e_session_memory_flow(tools, tmp_repo):
    sid = py(tools["session"], "start", "--label", "demo").strip()
    py(tools["session"], "log", sid, "info", "kicked off")

    py(tools["memory"], "write", "decisions", "DEC-001: use Sonnet 4.6 for compaction")
    py(tools["memory"], "write", "learnings", "tree-sitter-language-pack covers ~50 languages")
    py(tools["memory"], "write", "glossary", "FTS: full-text search")
    py(tools["memory"], "write", "checkpoint", "midway through Plan A1")

    cp = subprocess.run(
        [sys.executable, str(tools["memory"]), "status"],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode == 0

    out = py(tools["memory"], "recall", "compaction")
    assert "DEC-001" in out

    out = py(tools["memory"], "search", "tree-sitter")
    assert "language-pack" in out

    out = py(tools["memory"], "read", "checkpoint")
    assert "midway through" in out

    py(tools["session"], "end", sid)
    log_text = (tmp_repo / ".github" / ".cache" / "sessions" / sid / "log.md").read_text()
    assert "[end]" in log_text

    out = py(tools["session"], "list")
    assert sid in out
