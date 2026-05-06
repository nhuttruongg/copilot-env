import os
import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.fixture
def tmp_repo(tmp_path: Path):
    """Create a fresh git repo in tmp_path with .github/ skeleton.

    Returns the repo root Path. Working dir is changed into it for the test.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".github" / "tools").mkdir(parents=True)
    (repo / ".github" / ".cache" / "memory" / "decisions").mkdir(parents=True)
    (repo / ".github" / ".cache" / "memory" / "sessions").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    cwd = os.getcwd()
    os.chdir(repo)
    try:
        yield repo
    finally:
        os.chdir(cwd)
