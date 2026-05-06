import sys
import os
import shutil
import subprocess
import re
import time
from pathlib import Path

import pytest


@pytest.fixture
def session_tool(tmp_repo: Path, request) -> Path:
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
    return dst / "session.py"


# --- Task 14: start ---

def test_session_start_creates_directory(session_tool, tmp_repo):
    cp = subprocess.run(
        [sys.executable, str(session_tool), "start", "--label", "feat-x"],
        capture_output=True, text=True, check=True,
    )
    out = cp.stdout.strip()
    assert re.match(r"\d{4}-\d{2}-\d{2}-\d{4}-feat-x", out), out
    sdir = tmp_repo / ".github" / ".cache" / "sessions" / out
    assert sdir.is_dir()
    assert (sdir / "log.md").exists()
    assert (sdir / "tasks").is_dir()
    assert (sdir / "results").is_dir()
    assert (sdir / "reviews").is_dir()


# --- Task 15: log and save ---

def test_session_log_appends_to_log_md(session_tool, tmp_repo):
    sid = subprocess.run(
        [sys.executable, str(session_tool), "start", "--label", "logtest"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run(
        [sys.executable, str(session_tool), "log", sid, "info", "starting plan phase"],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(session_tool), "log", sid, "decision", "use opus 4.6"],
        check=True,
    )
    log = (tmp_repo / ".github" / ".cache" / "sessions" / sid / "log.md").read_text()
    assert "[info] starting plan phase" in log
    assert "[decision] use opus 4.6" in log


def test_session_save_writes_snapshot(session_tool, tmp_repo):
    sid = subprocess.run(
        [sys.executable, str(session_tool), "start", "--label", "savetest"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run(
        [sys.executable, str(session_tool), "save", sid, "--note", "midpoint"],
        capture_output=True, text=True, check=True,
    )
    snap = tmp_repo / ".github" / ".cache" / "sessions" / sid / "snapshot.md"
    assert snap.exists()
    assert "midpoint" in snap.read_text()


# --- Task 16: list and end ---

def test_session_list_shows_sessions(session_tool, tmp_repo):
    a = subprocess.run([sys.executable, str(session_tool), "start", "--label", "a"],
                       capture_output=True, text=True, check=True).stdout.strip()
    b = subprocess.run([sys.executable, str(session_tool), "start", "--label", "b"],
                       capture_output=True, text=True, check=True).stdout.strip()
    cp = subprocess.run(
        [sys.executable, str(session_tool), "list"],
        capture_output=True, text=True, check=True,
    )
    assert a in cp.stdout
    assert b in cp.stdout


def test_session_end_marks_status(session_tool, tmp_repo):
    sid = subprocess.run([sys.executable, str(session_tool), "start", "--label", "endtest"],
                         capture_output=True, text=True, check=True).stdout.strip()
    cp = subprocess.run(
        [sys.executable, str(session_tool), "end", sid],
        capture_output=True, text=True, check=True,
    )
    assert "ended" in cp.stdout.lower()
    log_text = (tmp_repo / ".github" / ".cache" / "sessions" / sid / "log.md").read_text()
    assert "[end]" in log_text


# --- Task 17: archive ---

def test_session_archive_moves_old_sessions(session_tool, tmp_repo):
    sid = subprocess.run(
        [sys.executable, str(session_tool), "start", "--label", "old"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    sdir = tmp_repo / ".github" / ".cache" / "sessions" / sid
    old = time.time() - 30 * 86400
    for p in sdir.rglob("*"):
        os.utime(p, (old, old))
    os.utime(sdir, (old, old))
    cp = subprocess.run(
        [sys.executable, str(session_tool), "archive", "--days", "7"],
        capture_output=True, text=True, check=True,
    )
    assert sid in cp.stdout
    assert (tmp_repo / ".github" / ".cache" / "sessions" / "_archive" / sid).is_dir()
    assert not (tmp_repo / ".github" / ".cache" / "sessions" / sid).exists()


# --- Task 18: resume ---

def test_session_resume_prints_log_and_open_artifacts(session_tool, tmp_repo):
    sid = subprocess.run(
        [sys.executable, str(session_tool), "start", "--label", "resume"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run([sys.executable, str(session_tool), "log", sid, "info", "did the thing"], check=True)
    sdir = tmp_repo / ".github" / ".cache" / "sessions" / sid
    (sdir / "tasks" / "1-foo.md").write_text("---\ntask_id: 1\n---\n# Task 1")
    cp = subprocess.run(
        [sys.executable, str(session_tool), "resume", sid],
        capture_output=True, text=True, check=True,
    )
    assert "did the thing" in cp.stdout
    assert "1-foo.md" in cp.stdout
    assert "no results" in cp.stdout.lower()
