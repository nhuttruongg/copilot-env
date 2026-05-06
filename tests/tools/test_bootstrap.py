"""Tests for bootstrap.sh — directory setup, profile detection, idempotency."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


BOOTSTRAP = Path(__file__).resolve().parents[2] / ".github" / "tools" / "bootstrap.sh"
TOOLS_SRC = Path(__file__).resolve().parents[2] / ".github" / "tools"


def run_bootstrap(repo: Path, env_extra: dict | None = None, expect_code: int = 0) -> str:
    env = {**os.environ, "REPO_ROOT": str(repo)}
    if env_extra:
        env.update(env_extra)
    cp = subprocess.run(
        ["bash", str(BOOTSTRAP)],
        capture_output=True, text=True, check=False, env=env,
    )
    assert cp.returncode == expect_code, (
        f"bootstrap exited {cp.returncode}\nstdout={cp.stdout}\nstderr={cp.stderr}"
    )
    return cp.stdout


def make_repo(tmp_path: Path) -> Path:
    """Create a minimal fake repo with .github/tools/ containing the real tools."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # .github/tools directory with real tools
    dst_tools = repo / ".github" / "tools"
    shutil.copytree(TOOLS_SRC, dst_tools)
    shutil.copy(BOOTSTRAP, dst_tools / "bootstrap.sh")
    (dst_tools / "bootstrap.sh").chmod(0o755)
    # init git so profile detection uses git ls-files
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    return repo


def test_bootstrap_creates_directory_structure(tmp_path):
    repo = make_repo(tmp_path)
    run_bootstrap(repo, {"BOOTSTRAP_PROFILE_OVERRIDE": "tiny",
                         "BOOTSTRAP_NO_VENV": "1",
                         "BOOTSTRAP_NO_SCAN": "1"})
    cache = repo / ".github" / ".cache"
    assert (cache / "memory" / "decisions").is_dir()
    assert (cache / "memory" / "sessions").is_dir()
    assert (cache / "logs").is_dir()


def test_bootstrap_writes_gitignore_for_cache(tmp_path):
    repo = make_repo(tmp_path)
    run_bootstrap(repo, {"BOOTSTRAP_PROFILE_OVERRIDE": "tiny",
                         "BOOTSTRAP_NO_VENV": "1", "BOOTSTRAP_NO_SCAN": "1"})
    gitignore = repo / ".github" / ".cache" / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert "*" in content


def test_bootstrap_writes_config_yaml_with_profile(tmp_path):
    repo = make_repo(tmp_path)
    run_bootstrap(repo, {"BOOTSTRAP_PROFILE_OVERRIDE": "small",
                         "BOOTSTRAP_NO_VENV": "1", "BOOTSTRAP_NO_SCAN": "1"})
    config = repo / ".github" / "config.yaml"
    assert config.exists()
    text = config.read_text()
    assert "profile: small" in text
    assert "code_graph: auto" in text
    assert "profile_thresholds:" in text


def test_bootstrap_does_not_overwrite_existing_config(tmp_path):
    repo = make_repo(tmp_path)
    config = repo / ".github" / "config.yaml"
    config.write_text("# custom\nprofile: medium\n")
    run_bootstrap(repo, {"BOOTSTRAP_PROFILE_OVERRIDE": "tiny",
                         "BOOTSTRAP_NO_VENV": "1", "BOOTSTRAP_NO_SCAN": "1"})
    assert config.read_text() == "# custom\nprofile: medium\n"


def test_bootstrap_creates_placeholder_files(tmp_path):
    repo = make_repo(tmp_path)
    run_bootstrap(repo, {"BOOTSTRAP_PROFILE_OVERRIDE": "tiny",
                         "BOOTSTRAP_NO_VENV": "1", "BOOTSTRAP_NO_SCAN": "1"})
    cache = repo / ".github" / ".cache"
    assert (cache / "memory" / "checkpoint.md").exists()
    assert (cache / "memory" / "learnings.md").exists()
    assert (cache / "memory" / "glossary.md").exists()
    assert (cache / "project-context.md").exists()
    ctx = (cache / "project-context.md").read_text()
    assert "Project Context" in ctx


def test_bootstrap_tiny_profile_skips_scan(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("def f(): pass")
    run_bootstrap(repo, {"BOOTSTRAP_PROFILE_OVERRIDE": "tiny",
                         "BOOTSTRAP_NO_VENV": "1", "BOOTSTRAP_NO_SCAN": "1"})
    assert not (repo / ".github" / ".cache" / "codegraph.db").exists()


def test_bootstrap_small_profile_runs_scan(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("def f(): pass\n")
    out = run_bootstrap(repo, {"BOOTSTRAP_PROFILE_OVERRIDE": "small",
                                "BOOTSTRAP_NO_VENV": "1"})
    # scan should have run and created the db
    assert (repo / ".github" / ".cache" / "codegraph.db").exists()
    assert "bootstrap complete" in out


def test_bootstrap_idempotent(tmp_path):
    repo = make_repo(tmp_path)
    env = {"BOOTSTRAP_PROFILE_OVERRIDE": "tiny",
           "BOOTSTRAP_NO_VENV": "1", "BOOTSTRAP_NO_SCAN": "1"}
    run_bootstrap(repo, env)
    # Run again — must succeed without error
    run_bootstrap(repo, env)
    # Config should still have original profile
    config = repo / ".github" / "config.yaml"
    assert "profile: tiny" in config.read_text()


def test_bootstrap_profile_detection_uses_file_count(tmp_path):
    repo = make_repo(tmp_path)
    # Add enough files to cross the tiny threshold (>50 files)
    src_dir = repo / "src"
    src_dir.mkdir()
    for i in range(60):
        (src_dir / f"m{i}.py").write_text(f"x={i}\n")
    # Track them in git
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    # Run without profile override
    run_bootstrap(repo, {"BOOTSTRAP_NO_VENV": "1", "BOOTSTRAP_NO_SCAN": "1"})
    config = repo / ".github" / "config.yaml"
    text = config.read_text()
    # With 60 files and ~120 loc, profile should be "small"
    assert "profile: small" in text


def test_bootstrap_reports_profile_in_output(tmp_path):
    repo = make_repo(tmp_path)
    out = run_bootstrap(repo, {"BOOTSTRAP_PROFILE_OVERRIDE": "medium",
                                "BOOTSTRAP_NO_VENV": "1", "BOOTSTRAP_NO_SCAN": "1"})
    assert "profile: medium" in out
    assert "bootstrap complete" in out
