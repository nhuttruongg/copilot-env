import sys
import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def mem_root(tmp_repo: Path) -> Path:
    return tmp_repo / ".github" / ".cache" / "memory"


@pytest.fixture
def memory_tool(tmp_repo: Path, request) -> Path:
    """Copy the project's memory.py + config.py + _lib into tmp_repo and return its path."""
    project_root = Path(request.config.rootpath)
    src_tools = project_root / ".github" / "tools"
    dst = tmp_repo / ".github" / "tools"
    import shutil
    for name in ["__init__.py", "config.py", "memory.py"]:
        s = src_tools / name
        if s.exists():
            shutil.copy(s, dst / name)
    (dst / "_lib").mkdir(exist_ok=True)
    for name in ["__init__.py", "text.py", "io.py"]:
        s = src_tools / "_lib" / name
        if s.exists():
            shutil.copy(s, dst / "_lib" / name)
    cfg = project_root / ".github" / "config.yaml"
    (tmp_repo / ".github" / "config.yaml").write_text(cfg.read_text())
    return dst / "memory.py"


# --- Task 6: write ---

def test_memory_write_learnings_appends(memory_tool, mem_root):
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "write", "learnings", "first thing"],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode == 0, cp.stderr
    f = mem_root / "learnings.md"
    assert f.exists()
    assert "first thing" in f.read_text()
    subprocess.run(
        [sys.executable, str(memory_tool), "write", "learnings", "second thing"],
        check=True,
    )
    contents = f.read_text()
    assert "first thing" in contents
    assert "second thing" in contents
    assert contents.count("\n## ") >= 2


def test_memory_write_glossary_dedupes_term(memory_tool, mem_root):
    subprocess.run(
        [sys.executable, str(memory_tool), "write", "glossary", "RT: refresh token"],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(memory_tool), "write", "glossary", "RT: refresh token (rotated)"],
        check=True,
    )
    contents = (mem_root / "glossary.md").read_text()
    assert contents.count("RT:") == 1
    assert "rotated" in contents


# --- Task 7: read ---

def test_memory_read_returns_full_when_under_budget(memory_tool, mem_root):
    subprocess.run([sys.executable, str(memory_tool), "write", "learnings", "alpha"], check=True)
    subprocess.run([sys.executable, str(memory_tool), "write", "learnings", "beta"], check=True)
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "read", "learnings", "--budget", "10000"],
        capture_output=True, text=True, check=True,
    )
    assert "alpha" in cp.stdout
    assert "beta" in cp.stdout


def test_memory_read_truncates_to_budget(memory_tool, mem_root):
    for i in range(10):
        subprocess.run(
            [sys.executable, str(memory_tool), "write", "learnings", "x" * 200 + f" entry-{i}"],
            check=True,
        )
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "read", "learnings", "--budget", "100"],
        capture_output=True, text=True, check=True,
    )
    assert len(cp.stdout) < 1000
    assert "entry-9" in cp.stdout
    assert "entry-0" not in cp.stdout


# --- Task 8: status ---

def test_memory_status_reports_sizes_and_exit_code(memory_tool):
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "status", "--json"],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert "checkpoint" in data
    assert data["checkpoint"]["tokens"] == 0
    assert data["checkpoint"]["soft"] == 2000


def test_memory_status_exit_nonzero_when_over_hard(memory_tool):
    big = "x" * 50000
    subprocess.run(
        [sys.executable, str(memory_tool), "write", "learnings", big],
        check=True,
    )
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "status"],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode != 0
    assert "learnings" in cp.stdout or "learnings" in cp.stderr


# --- Task 9: compact ---

def test_memory_compact_writes_request_file(memory_tool, mem_root):
    for i in range(20):
        subprocess.run(
            [sys.executable, str(memory_tool), "write", "learnings",
             "x" * 1500 + f" item-{i}"],
            check=True,
        )
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "compact", "learnings", "--target", "2000"],
        capture_output=True, text=True, check=True,
    )
    req = mem_root / "_compact_request.md"
    assert req.exists()
    content = req.read_text()
    assert "kind: learnings" in content
    assert "target_tokens: 2000" in content
    assert "## Chunks to summarize" in content
    assert "## Instructions" in content
    assert "memory.py write-summary learnings" in content


# --- Task 10: write-summary ---

def test_write_summary_rotates_oldest_to_warm_and_deletes_request(memory_tool, mem_root, tmp_path):
    for i in range(5):
        subprocess.run(
            [sys.executable, str(memory_tool), "write", "learnings", f"entry-{i}"],
            check=True,
        )
    subprocess.run(
        [sys.executable, str(memory_tool), "compact", "learnings", "--target", "100"],
        check=True,
    )
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("Summary: entries 0..2 covered topics A, B, C.")
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "write-summary", "learnings", str(summary_file)],
        capture_output=True, text=True, check=True,
    )
    assert not (mem_root / "_compact_request.md").exists()
    warm = mem_root / "learnings_warm.md"
    assert warm.exists()
    assert "topics A, B, C" in warm.read_text()
    main = (mem_root / "learnings.md").read_text()
    assert "entry-4" in main


def test_write_summary_errors_without_request(memory_tool, tmp_path):
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("nothing")
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "write-summary", "learnings", str(summary_file)],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode != 0
    assert "no compaction request" in (cp.stderr + cp.stdout).lower()


# --- Task 11: search ---

def test_memory_search_finds_matches(memory_tool, mem_root):
    subprocess.run([sys.executable, str(memory_tool), "write", "learnings",
                    "OAuth refresh-token rotation requires invalidating the old RT"], check=True)
    subprocess.run([sys.executable, str(memory_tool), "write", "glossary",
                    "RT: refresh token (oauth)"], check=True)
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "search", "refresh-token"],
        capture_output=True, text=True, check=True,
    )
    assert "OAuth" in cp.stdout
    assert "learnings" in cp.stdout


def test_memory_search_filtered_by_kind(memory_tool):
    subprocess.run([sys.executable, str(memory_tool), "write", "learnings",
                    "alpha beta gamma"], check=True)
    subprocess.run([sys.executable, str(memory_tool), "write", "glossary",
                    "GAMMA: a Greek letter"], check=True)
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "search", "gamma", "--kind", "glossary"],
        capture_output=True, text=True, check=True,
    )
    assert "Greek" in cp.stdout
    assert "alpha beta" not in cp.stdout


# --- Task 12: recall ---

def test_memory_recall_returns_ranked_snippets(memory_tool):
    subprocess.run([sys.executable, str(memory_tool), "write", "decisions",
                    "DEC-001: oauth tokens stored as bcrypt hash"], check=True)
    subprocess.run([sys.executable, str(memory_tool), "write", "learnings",
                    "oauth library quirk with leeway parameter"], check=True)
    subprocess.run([sys.executable, str(memory_tool), "write", "glossary",
                    "OAuth: Open Authorization"], check=True)
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "recall", "oauth"],
        capture_output=True, text=True, check=True,
    )
    out = cp.stdout
    assert "DEC-001" in out
    assert "leeway" in out
    assert "Open Authorization" in out
    assert out.find("[decisions]") < out.find("[learnings]") < out.find("[glossary]")


# --- Task 13: forget ---

def test_memory_forget_deletes_decision_by_id(memory_tool, mem_root):
    subprocess.run([sys.executable, str(memory_tool), "write", "decisions",
                    "DEC-042: doomed decision"], check=True)
    files = list((mem_root / "decisions").glob("DEC-042-*.md"))
    assert len(files) == 1
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "forget", "DEC-042"],
        capture_output=True, text=True, check=True,
    )
    assert "deleted" in cp.stdout.lower()
    assert not list((mem_root / "decisions").glob("DEC-042-*.md"))


def test_memory_forget_unknown_id_errors(memory_tool):
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "forget", "DEC-999"],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode != 0
