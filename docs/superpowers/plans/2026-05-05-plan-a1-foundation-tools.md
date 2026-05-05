# Plan A1 — Foundation Tools (config, memory, session)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the stdlib-only foundation tools the rest of the system depends on: `config.py` (profile + feature loader), `memory.py` (layered memory CLI with auto-compaction), `session.py` (session lifecycle CLI). Plus the `config.yaml` schema and the `.github/.cache/` skeleton.

**Architecture:** Three Python modules in `.github/tools/`, each with a `__main__` block exposing a small CLI. They share `config.py` for profile-aware behavior. SQLite (stdlib) is used for memory FTS only — markdown is the source of truth on disk. No third-party dependencies.

**Tech Stack:** Python 3.10+, stdlib only (`argparse`, `sqlite3`, `pathlib`, `json`, `re`, `datetime`, `shutil`, `subprocess`), `pytest` for tests, PyYAML for config (allowed exception — too painful without it; install via stdlib `pip install pyyaml` in bootstrap).

**Spec reference:** `docs/superpowers/specs/2026-05-05-copilot-orchestration-design.md` §3.2, §3.3, §12, §2.5.

---

## File Structure

| File | Responsibility |
|---|---|
| `.github/tools/config.py` | Load `config.yaml`, resolve `profile: auto`, merge per-feature overrides, expose `Config` dataclass |
| `.github/tools/memory.py` | Memory CLI: write/read/search/recall/status/compact/write-summary |
| `.github/tools/session.py` | Session CLI: start/log/save/end/list/resume/archive |
| `.github/config.yaml` | Project config (profile + feature overrides + budgets) |
| `.github/tools/requirements.txt` | `pyyaml` only (Plan A2 will add tree-sitter) |
| `.github/.gitignore` (extension) | Exclude `.github/.cache/` |
| `tests/tools/test_config.py` | Unit tests |
| `tests/tools/test_memory.py` | Unit tests |
| `tests/tools/test_session.py` | Unit tests |
| `tests/tools/conftest.py` | `tmp_repo` fixture |
| `.github/tools/_lib/__init__.py` | Shared helpers (token-approx, atomic writes) |

19 tasks. Roughly 95 steps. Each task is independent enough to commit individually.

---

## Pre-flight

Before Task 1, verify: Python ≥ 3.10, `git` available, working dir is the repo root. Run baseline:

```bash
python3 --version    # expect 3.10+
git rev-parse --is-inside-work-tree    # expect "true"
which pytest || python3 -m pip install --user pytest pyyaml
pytest --version
```

If any fails, stop and ask the human partner.

---

### Task 1: Project skeleton, requirements, gitignore

**Files:**
- Create: `.github/tools/__init__.py` (empty marker)
- Create: `.github/tools/_lib/__init__.py`
- Create: `.github/tools/requirements.txt`
- Create: `tests/tools/__init__.py` (empty)
- Create: `tests/tools/conftest.py`
- Modify: `.gitignore` (append `.github/.cache/`)

- [ ] **Step 1: Write the failing test**

`tests/tools/conftest.py`:

```python
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
```

`tests/tools/test_config.py` (placeholder for Task 1's purposes):

```python
def test_skeleton_exists(tmp_repo):
    assert (tmp_repo / ".github" / "tools").is_dir()
    assert (tmp_repo / ".github" / ".cache" / "memory" / "decisions").is_dir()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_config.py -v
```

Expected: FAIL — `tests/tools/__init__.py` and `tests/tools/conftest.py` don't exist yet, pytest will error on collection.

- [ ] **Step 3: Create the skeleton files**

`.github/tools/__init__.py`: empty file.

`.github/tools/_lib/__init__.py`: empty file.

`.github/tools/requirements.txt`:

```
pyyaml>=6.0
```

`tests/tools/__init__.py`: empty file.

(`tests/tools/conftest.py` was already written in Step 1.)

Append to `.gitignore`:

```
# Copilot agentic environment cache
.github/.cache/
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_config.py -v
```

Expected: PASS — `test_skeleton_exists` finds the directories.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/__init__.py .github/tools/_lib/__init__.py \
        .github/tools/requirements.txt tests/tools/__init__.py \
        tests/tools/conftest.py tests/tools/test_config.py .gitignore
git commit -m "feat: scaffold tools/ and tests/ skeleton for Plan A1"
```

---

### Task 2: Config YAML template

**Files:**
- Create: `.github/config.yaml`
- Modify: `tests/tools/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_config.py`:

```python
import yaml
from pathlib import Path


def test_config_yaml_exists_and_has_profile_field(tmp_repo, request):
    # Copy the project's config.yaml into the tmp_repo for testing
    src = Path(request.config.rootpath) / ".github" / "config.yaml"
    dst = tmp_repo / ".github" / "config.yaml"
    dst.write_text(src.read_text())
    data = yaml.safe_load(dst.read_text())
    assert data["profile"] == "auto"
    assert "profile_thresholds" in data
    assert "features" in data
    assert data["features"]["code_graph"] == "auto"
    assert "memory" in data
    assert data["memory"]["budgets"]["checkpoint"]["soft"] == 2000
    assert "models" in data
    assert data["models"]["thinking"] == "claude-opus-4-6"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_config.py::test_config_yaml_exists_and_has_profile_field -v
```

Expected: FAIL — `.github/config.yaml` doesn't exist.

- [ ] **Step 3: Create `.github/config.yaml`**

```yaml
# Adaptive profile — activates a coherent feature set; per-feature override below
profile: auto              # auto | tiny | small | medium | large | xlarge | custom

# Auto-detection thresholds (only consulted when profile: auto)
profile_thresholds:
  tiny:   { max_files: 50,    max_loc: 2000 }
  small:  { max_files: 500,   max_loc: 20000 }
  medium: { max_files: 5000,  max_loc: 200000 }
  large:  { max_files: 50000, max_loc: 2000000 }
  # > large.max_files OR > large.max_loc => xlarge

# Per-feature overrides; "auto" defers to profile defaults (see spec §2.5)
features:
  code_graph: auto         # auto | full | symbols-only | off
  memory_compaction: auto  # auto | on | off
  multi_agent: auto        # auto | on | off
  worktree_isolation: auto # auto | on | off
  validator_gate: auto     # auto | mandatory | optional | off

codegraph:
  exclude:
    - "**/node_modules/**"
    - "**/.venv/**"
    - "**/dist/**"
    - "**/build/**"
    - "**/target/**"
    - "**/.git/**"
    - "**/vendor/**"
  languages:
    tier1: [python, javascript, typescript, tsx, go, java, rust, c, cpp]
    tier2: []
  budgets:
    envelope_default_tokens: 2000
    impact_max_depth: 3
  scan:
    workers: auto
    batch_size: 5000

memory:
  budgets:
    checkpoint:  { soft: 2000,  hard: 4000  }
    sessions:    { soft: 8000,  hard: 16000 }
    glossary:    { soft: 4000,  hard: 8000  }
    learnings:   { soft: 4000,  hard: 8000  }
  compaction_model: claude-sonnet-4-6
  archive_after_days: 7

dispatch:
  worktree_isolation: auto
  worktree_dir: .worktrees
  max_retries_per_subtask: 2

models:
  fast:    claude-haiku-4-5
  standard: claude-sonnet-4-6
  thinking: claude-opus-4-6
  fallback:
    fast:    gpt-4.1
    standard: gpt-5.3-codex
    thinking: gpt-5.5

routing:
  critical_path_globs:
    - "**/auth/**"
    - "**/payments/**"
    - "**/crypto/**"
    - "**/security/**"
    - "**/migrations/**"
  deep_keywords: [refactor, redesign, architecture, migrate, rewrite]
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_config.py::test_config_yaml_exists_and_has_profile_field -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/config.yaml tests/tools/test_config.py
git commit -m "feat(config): add config.yaml with profile + feature overrides"
```

---

### Task 3: Config loader (`config.py`) — load + validate

**Files:**
- Create: `.github/tools/config.py`
- Modify: `tests/tools/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_config.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from config import Config, load_config  # noqa: E402


def test_load_config_returns_dataclass(tmp_repo, request):
    src = Path(request.config.rootpath) / ".github" / "config.yaml"
    (tmp_repo / ".github" / "config.yaml").write_text(src.read_text())
    cfg = load_config(tmp_repo / ".github" / "config.yaml")
    assert isinstance(cfg, Config)
    assert cfg.profile == "auto"
    assert cfg.models["thinking"] == "claude-opus-4-6"
    assert cfg.memory_budgets["checkpoint"]["soft"] == 2000


def test_load_config_missing_file_raises(tmp_repo):
    with __import__("pytest").raises(FileNotFoundError):
        load_config(tmp_repo / ".github" / "config.yaml")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_config.py::test_load_config_returns_dataclass -v
```

Expected: FAIL — `config` module doesn't exist.

- [ ] **Step 3: Implement `config.py`**

`.github/tools/config.py`:

```python
"""Config loader for the Copilot agentic environment.

Loads .github/config.yaml, resolves "auto" values, exposes a Config dataclass.
Profile resolution itself happens in Task 4 (resolve_profile); this module
only loads + validates the raw config.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass
class Config:
    profile: str
    profile_thresholds: dict[str, dict[str, int]]
    features: dict[str, str]
    codegraph: dict[str, Any]
    memory_budgets: dict[str, dict[str, int]]
    memory_compaction_model: str
    memory_archive_after_days: int
    dispatch: dict[str, Any]
    models: dict[str, Any]
    routing: dict[str, Any]
    raw: dict[str, Any] = field(repr=False)


VALID_PROFILES = {"auto", "tiny", "small", "medium", "large", "xlarge", "custom"}


def load_config(path: Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    profile = raw.get("profile", "auto")
    if profile not in VALID_PROFILES:
        raise ValueError(f"invalid profile {profile!r}; must be one of {sorted(VALID_PROFILES)}")
    return Config(
        profile=profile,
        profile_thresholds=raw.get("profile_thresholds", {}),
        features=raw.get("features", {}),
        codegraph=raw.get("codegraph", {}),
        memory_budgets=raw.get("memory", {}).get("budgets", {}),
        memory_compaction_model=raw.get("memory", {}).get("compaction_model", "claude-sonnet-4-6"),
        memory_archive_after_days=int(raw.get("memory", {}).get("archive_after_days", 7)),
        dispatch=raw.get("dispatch", {}),
        models=raw.get("models", {}),
        routing=raw.get("routing", {}),
        raw=raw,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_config.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/config.py tests/tools/test_config.py
git commit -m "feat(config): add Config dataclass and load_config"
```

---

### Task 4: Profile resolution + feature resolution

**Files:**
- Modify: `.github/tools/config.py`
- Modify: `tests/tools/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_config.py`:

```python
from config import resolve_profile, resolve_feature  # noqa: E402


def test_resolve_profile_tiny():
    thresholds = {
        "tiny":   {"max_files": 50,    "max_loc": 2000},
        "small":  {"max_files": 500,   "max_loc": 20000},
        "medium": {"max_files": 5000,  "max_loc": 200000},
        "large":  {"max_files": 50000, "max_loc": 2000000},
    }
    assert resolve_profile(files=10, loc=500, thresholds=thresholds) == "tiny"
    assert resolve_profile(files=200, loc=10000, thresholds=thresholds) == "small"
    assert resolve_profile(files=2000, loc=100000, thresholds=thresholds) == "medium"
    assert resolve_profile(files=20000, loc=500000, thresholds=thresholds) == "large"
    assert resolve_profile(files=100000, loc=5000000, thresholds=thresholds) == "xlarge"


def test_resolve_profile_files_alone_can_force_higher_tier():
    thresholds = {
        "tiny":   {"max_files": 50,    "max_loc": 2000},
        "small":  {"max_files": 500,   "max_loc": 20000},
        "medium": {"max_files": 5000,  "max_loc": 200000},
        "large":  {"max_files": 50000, "max_loc": 2000000},
    }
    # Big file count, tiny LoC -> still picks the tier matching files
    assert resolve_profile(files=2000, loc=500, thresholds=thresholds) == "medium"


def test_resolve_feature_auto_uses_profile_default():
    # tiny profile default for code_graph is "off"
    assert resolve_feature("code_graph", "auto", profile="tiny") == "off"
    assert resolve_feature("code_graph", "auto", profile="small") == "symbols-only"
    assert resolve_feature("code_graph", "auto", profile="medium") == "full"


def test_resolve_feature_explicit_overrides_profile():
    assert resolve_feature("code_graph", "full", profile="tiny") == "full"
    assert resolve_feature("validator_gate", "off", profile="large") == "off"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_config.py -v
```

Expected: FAIL — `resolve_profile`, `resolve_feature` not defined.

- [ ] **Step 3: Add resolution functions to `config.py`**

Append to `.github/tools/config.py`:

```python
PROFILE_DEFAULTS: dict[str, dict[str, str]] = {
    "tiny": {
        "code_graph": "off",
        "memory_compaction": "off",
        "multi_agent": "off",
        "worktree_isolation": "off",
        "validator_gate": "optional",
    },
    "small": {
        "code_graph": "symbols-only",
        "memory_compaction": "on",
        "multi_agent": "off",
        "worktree_isolation": "off",
        "validator_gate": "optional",
    },
    "medium": {
        "code_graph": "full",
        "memory_compaction": "on",
        "multi_agent": "on",
        "worktree_isolation": "off",
        "validator_gate": "mandatory",
    },
    "large": {
        "code_graph": "full",
        "memory_compaction": "on",
        "multi_agent": "on",
        "worktree_isolation": "on",
        "validator_gate": "mandatory",
    },
    "xlarge": {
        "code_graph": "full",
        "memory_compaction": "on",
        "multi_agent": "on",
        "worktree_isolation": "on",
        "validator_gate": "mandatory",
    },
}


def resolve_profile(files: int, loc: int, thresholds: dict[str, dict[str, int]]) -> str:
    """Pick the profile whose thresholds the project fits within.

    Both files AND loc must be within the tier's max for it to apply; whichever
    tier has any dimension exceeded escalates to the next tier.
    """
    order = ["tiny", "small", "medium", "large"]
    for tier in order:
        t = thresholds.get(tier, {})
        if files <= t.get("max_files", 0) and loc <= t.get("max_loc", 0):
            return tier
    return "xlarge"


def resolve_feature(feature: str, value: str, profile: str) -> str:
    """If value is 'auto', look up the profile default for the feature.

    Profile 'custom' with auto raises (custom requires explicit values).
    """
    if value != "auto":
        return value
    if profile == "custom":
        raise ValueError(f"profile=custom requires explicit value for feature {feature!r}")
    if profile == "auto":
        # Treat as medium by default before /init has detected; bootstrap will overwrite
        profile = "medium"
    defaults = PROFILE_DEFAULTS.get(profile, {})
    if feature not in defaults:
        raise KeyError(f"unknown feature {feature!r} for profile {profile!r}")
    return defaults[feature]
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_config.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/config.py tests/tools/test_config.py
git commit -m "feat(config): resolve_profile + resolve_feature with profile defaults"
```

---

### Task 5: `_lib` shared helpers — token approx + atomic write

**Files:**
- Create: `.github/tools/_lib/text.py`
- Create: `.github/tools/_lib/io.py`
- Create: `tests/tools/test_lib.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_lib.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.text import approx_tokens  # noqa: E402
from _lib.io import atomic_write_text  # noqa: E402


def test_approx_tokens_uses_chars_div_4():
    assert approx_tokens("") == 0
    assert approx_tokens("abcd") == 1
    assert approx_tokens("a" * 4000) == 1000
    assert approx_tokens("hi") == 1  # rounds up for non-empty


def test_atomic_write_text_writes_then_renames(tmp_path):
    target = tmp_path / "out.md"
    atomic_write_text(target, "hello")
    assert target.read_text() == "hello"
    # No leftover .tmp files
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_text_overwrites(tmp_path):
    target = tmp_path / "out.md"
    target.write_text("old")
    atomic_write_text(target, "new")
    assert target.read_text() == "new"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_lib.py -v
```

Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement helpers**

`.github/tools/_lib/text.py`:

```python
"""Tiny text helpers shared across memory.py / codegraph.py / session.py."""
from __future__ import annotations


def approx_tokens(text: str) -> int:
    """Approximate token count as ceil(chars/4). Avoids any tokenizer dependency.

    Empty string is 0; any non-empty string is at least 1.
    """
    n = len(text)
    if n == 0:
        return 0
    return (n + 3) // 4
```

`.github/tools/_lib/io.py`:

```python
"""Atomic file IO helpers."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, content: str) -> None:
    """Write content to path atomically: write to sibling tmp file, then rename.

    Avoids partial writes if the process is killed mid-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_lib.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/_lib/text.py .github/tools/_lib/io.py tests/tools/test_lib.py
git commit -m "feat(_lib): add approx_tokens and atomic_write_text helpers"
```

---

### Task 6: `memory.py` — write learnings/glossary (append-style kinds)

**Files:**
- Create: `.github/tools/memory.py`
- Create: `tests/tools/test_memory.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_memory.py`:

```python
import sys
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def mem_root(tmp_repo: Path) -> Path:
    return tmp_repo / ".github" / ".cache" / "memory"


def run_memory(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Invoke memory.py as a subprocess from the repo root."""
    tool = repo / "PROJECT_TOOLS_PATH"
    # Resolve to the project's actual memory.py — we copy it into tmp_repo
    return subprocess.run(
        [sys.executable, str(tool), *args],
        capture_output=True, text=True, check=False,
    )


@pytest.fixture
def memory_tool(tmp_repo: Path, request) -> Path:
    """Copy the project's memory.py + config.py + _lib into tmp_repo and return its path."""
    project_root = Path(request.config.rootpath)
    src_tools = project_root / ".github" / "tools"
    dst = tmp_repo / ".github" / "tools"
    # tools dir was already created by tmp_repo; copy module files
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
    # config.yaml
    cfg = project_root / ".github" / "config.yaml"
    (tmp_repo / ".github" / "config.yaml").write_text(cfg.read_text())
    return dst / "memory.py"


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
    # Each entry has a timestamp marker
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
    # Only one "RT:" entry remains (latest wins)
    assert contents.count("RT:") == 1
    assert "rotated" in contents
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_memory.py -v
```

Expected: FAIL — `memory.py` doesn't exist.

- [ ] **Step 3: Implement append-style writes**

`.github/tools/memory.py`:

```python
#!/usr/bin/env python3
"""Memory CLI for the Copilot agentic environment.

Layered memory with bounded budgets. Plain markdown files on disk; SQLite FTS
will be added in a later task. This task implements the simplest path:
appending to learnings/glossary, with glossary dedup-by-term.

Usage:
    memory.py write <kind> <content>
    memory.py read <kind> [--budget N]
    memory.py status
    memory.py search "<query>" [--kind=K]
    memory.py recall "<topic>"
    memory.py compact <kind> [--target N]
    memory.py write-summary <kind> <file>
    memory.py forget <id>
"""
from __future__ import annotations
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

# Allow running as a script
sys.path.insert(0, str(Path(__file__).parent))
from _lib.io import atomic_write_text  # noqa: E402

KINDS = {"checkpoint", "sessions", "decisions", "glossary", "learnings"}


def memory_root(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / ".github" / ".cache" / "memory"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _file_for(kind: str, root: Path) -> Path:
    if kind == "checkpoint":
        return root / "checkpoint.md"
    if kind == "glossary":
        return root / "glossary.md"
    if kind == "learnings":
        return root / "learnings.md"
    raise ValueError(f"_file_for not applicable to kind={kind!r}")


def write(kind: str, content: str, root: Path) -> None:
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; must be one of {sorted(KINDS)}")
    root.mkdir(parents=True, exist_ok=True)
    if kind in ("learnings",):
        _append_simple(_file_for(kind, root), content)
    elif kind == "glossary":
        _write_glossary(root / "glossary.md", content)
    elif kind == "checkpoint":
        # checkpoint is overwrite-style; later tasks will refine
        atomic_write_text(_file_for(kind, root), f"## {_now_iso()}\n\n{content}\n")
    elif kind == "decisions":
        _write_decision(root / "decisions", content)
    elif kind == "sessions":
        _write_session_entry(root / "sessions", content)


def _append_simple(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.exists() else ""
    block = f"\n## {_now_iso()}\n\n{content.rstrip()}\n"
    atomic_write_text(path, existing + block)


def _write_glossary(path: Path, content: str) -> None:
    """Glossary entries are 'TERM: definition'. Dedupe by TERM (latest wins)."""
    m = re.match(r"\s*([A-Za-z0-9_\- ]+?)\s*:\s*(.+)", content, re.DOTALL)
    if not m:
        # Not in TERM: form, just append
        return _append_simple(path, content)
    term = m.group(1).strip()
    existing = path.read_text() if path.exists() else ""
    # Remove any existing block for this term
    pattern = re.compile(
        rf"(?ms)^## .+?\n\n{re.escape(term)}:\s.+?(?=\n## |\Z)"
    )
    cleaned = pattern.sub("", existing).rstrip()
    block = f"\n## {_now_iso()}\n\n{content.rstrip()}\n"
    atomic_write_text(path, (cleaned + block).lstrip("\n"))


def _write_decision(decisions_dir: Path, content: str) -> None:
    """Decisions are one file per DEC-NNN. Content's first line should be 'DEC-NNN: title'."""
    decisions_dir.mkdir(parents=True, exist_ok=True)
    first_line = content.strip().splitlines()[0] if content.strip() else "DEC-XXX: untitled"
    m = re.match(r"(DEC-\d+)\s*:\s*(.+)", first_line)
    if m:
        dec_id = m.group(1)
        slug = re.sub(r"[^a-z0-9]+", "-", m.group(2).lower()).strip("-")[:60]
        fname = f"{dec_id}-{slug}.md"
    else:
        # Auto-assign next DEC number
        existing = sorted(p.name for p in decisions_dir.glob("DEC-*.md"))
        next_n = 1
        if existing:
            last = re.search(r"DEC-(\d+)", existing[-1])
            if last:
                next_n = int(last.group(1)) + 1
        fname = f"DEC-{next_n:03d}-untitled.md"
    atomic_write_text(decisions_dir / fname, f"# {first_line}\n\n_{_now_iso()}_\n\n{content}\n")


def _write_session_entry(sessions_dir: Path, content: str) -> None:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now().strftime("%Y-%m-%d")
    # Find or create today's hot file
    hot_files = sorted(sessions_dir.glob(f"{today}-*.md"))
    if hot_files:
        path = hot_files[-1]
        existing = path.read_text()
    else:
        stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
        path = sessions_dir / f"{stamp}.md"
        existing = f"# Session {stamp}\n"
    block = f"\n## {_now_iso()}\n\n{content.rstrip()}\n"
    atomic_write_text(path, existing + block)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    p_write = sub.add_parser("write")
    p_write.add_argument("kind", choices=sorted(KINDS))
    p_write.add_argument("content")
    args = p.parse_args(argv)
    root = memory_root()
    if args.cmd == "write":
        write(args.kind, args.content, root)
        return 0
    p.error(f"unsupported command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_memory.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/memory.py tests/tools/test_memory.py
git commit -m "feat(memory): write command for learnings/glossary/checkpoint/decisions/sessions"
```

---

### Task 7: `memory.py read` — token-budget aware reads

**Files:**
- Modify: `.github/tools/memory.py`
- Modify: `tests/tools/test_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_memory.py`:

```python
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
    # Write 10 large entries
    for i in range(10):
        subprocess.run(
            [sys.executable, str(memory_tool), "write", "learnings", "x" * 200 + f" entry-{i}"],
            check=True,
        )
    cp = subprocess.run(
        [sys.executable, str(memory_tool), "read", "learnings", "--budget", "100"],
        capture_output=True, text=True, check=True,
    )
    # Output should be small — far less than 10 * 200 chars
    assert len(cp.stdout) < 1000
    # Most recent entry must be present (entry-9)
    assert "entry-9" in cp.stdout
    # Earliest entry should be excluded
    assert "entry-0" not in cp.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_memory.py::test_memory_read_returns_full_when_under_budget -v
```

Expected: FAIL — read command not implemented.

- [ ] **Step 3: Implement `read`**

In `.github/tools/memory.py`:

Add import:

```python
from _lib.text import approx_tokens
```

Add function before `main`:

```python
def read(kind: str, budget: int | None, root: Path) -> str:
    """Return memory content for kind, capped to budget tokens.

    For append-style kinds (learnings, glossary), reads from newest entry first
    and stops adding entries once budget is hit.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    if kind == "checkpoint":
        path = _file_for("checkpoint", root)
        return path.read_text() if path.exists() else ""
    if kind in ("learnings", "glossary"):
        path = _file_for(kind, root)
        if not path.exists():
            return ""
        text = path.read_text()
        if budget is None:
            return text
        # Split into entries by "## " heading; keep the file header (everything
        # before the first "## ") then iterate from newest to oldest.
        parts = re.split(r"(?m)^(?=## )", text)
        header = parts[0] if parts and not parts[0].startswith("## ") else ""
        entries = [p for p in parts if p.startswith("## ")]
        chosen: list[str] = []
        used = approx_tokens(header)
        for entry in reversed(entries):
            t = approx_tokens(entry)
            if used + t > budget:
                break
            chosen.append(entry)
            used += t
        return header + "".join(reversed(chosen))
    if kind == "decisions":
        ddir = root / "decisions"
        if not ddir.exists():
            return ""
        out = ""
        for f in sorted(ddir.glob("DEC-*.md")):
            chunk = f.read_text() + "\n"
            if budget is not None and approx_tokens(out + chunk) > budget:
                break
            out += chunk
        return out
    if kind == "sessions":
        sdir = root / "sessions"
        if not sdir.exists():
            return ""
        # Newest hot file first
        hot = sorted(sdir.glob("20*.md"), reverse=True)
        out = ""
        for f in hot:
            chunk = f.read_text() + "\n"
            if budget is not None and approx_tokens(out + chunk) > budget:
                break
            out += chunk
        return out
    return ""
```

Update `main` to wire up `read`:

```python
    p_read = sub.add_parser("read")
    p_read.add_argument("kind", choices=sorted(KINDS))
    p_read.add_argument("--budget", type=int, default=None)
    # ... after p_write registered, before parse_args
```

In the dispatch block:

```python
    if args.cmd == "read":
        sys.stdout.write(read(args.kind, args.budget, root))
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_memory.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/memory.py tests/tools/test_memory.py
git commit -m "feat(memory): read command with token-budget truncation"
```

---

### Task 8: `memory.py status` — sizes vs budgets

**Files:**
- Modify: `.github/tools/memory.py`
- Modify: `tests/tools/test_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_memory.py`:

```python
import json


def test_memory_status_reports_sizes_and_exit_code(memory_tool):
    # Empty state: all sizes 0, status exits 0
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
    # Force learnings way over hard budget (8000 tokens = 32000 chars)
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_memory.py::test_memory_status_reports_sizes_and_exit_code -v
```

Expected: FAIL — status command not implemented.

- [ ] **Step 3: Implement `status`**

In `.github/tools/memory.py`, add helper to load budgets from `config.yaml`:

```python
import json
from config import load_config


def _budgets(root: Path) -> dict[str, dict[str, int]]:
    cfg_path = root.parent.parent / "config.yaml"  # .github/.cache/memory -> .github/config.yaml
    if cfg_path.exists():
        return load_config(cfg_path).memory_budgets
    return {
        "checkpoint":  {"soft": 2000,  "hard": 4000},
        "sessions":    {"soft": 8000,  "hard": 16000},
        "glossary":    {"soft": 4000,  "hard": 8000},
        "learnings":   {"soft": 4000,  "hard": 8000},
    }


def status(root: Path) -> tuple[dict, bool]:
    """Return (status_dict, any_over_hard)."""
    budgets = _budgets(root)
    over = False
    out: dict[str, dict[str, int]] = {}
    for kind in ["checkpoint", "sessions", "glossary", "learnings"]:
        # Sum tokens for this kind
        if kind == "sessions":
            sdir = root / "sessions"
            text = ""
            if sdir.exists():
                for f in sorted(sdir.glob("20*.md")):
                    text += f.read_text()
        elif kind in ("checkpoint", "glossary", "learnings"):
            path = _file_for(kind, root)
            text = path.read_text() if path.exists() else ""
        toks = approx_tokens(text)
        b = budgets.get(kind, {"soft": 0, "hard": 0})
        out[kind] = {"tokens": toks, "soft": b["soft"], "hard": b["hard"]}
        if toks > b["hard"]:
            over = True
    return out, over
```

Wire up subcommand in `main`:

```python
    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")
```

```python
    if args.cmd == "status":
        data, over = status(root)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            for kind, v in data.items():
                marker = "⚠️" if v["tokens"] > v["hard"] else ("·" if v["tokens"] > v["soft"] else "✓")
                print(f"{marker} {kind:<12} {v['tokens']:>6} tokens  (soft={v['soft']}, hard={v['hard']})")
        return 1 if over else 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_memory.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/memory.py tests/tools/test_memory.py
git commit -m "feat(memory): status command with --json and exit-nonzero on hard overflow"
```

---

### Task 9: `memory.py compact` — emit compaction request file

**Files:**
- Modify: `.github/tools/memory.py`
- Modify: `tests/tools/test_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_memory.py`:

```python
def test_memory_compact_writes_request_file(memory_tool, mem_root):
    # Create enough learnings to need compaction
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
    # The request must include the chunks to fold and clear instructions
    assert "## Chunks to summarize" in content
    assert "## Instructions" in content
    assert "memory.py write-summary learnings" in content
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_memory.py::test_memory_compact_writes_request_file -v
```

Expected: FAIL — `compact` not implemented.

- [ ] **Step 3: Implement `compact`**

In `.github/tools/memory.py`:

```python
COMPACT_REQUEST_TEMPLATE = """\
# Compaction request

kind: {kind}
target_tokens: {target}
generated: {ts}

## Instructions

Summarize the chunks below into approximately {target} tokens of dense markdown.
Preserve: dates, decisions, file paths, error messages, named entities.
Drop: filler, repeated context, conversational asides.
Output one cohesive markdown summary (no chunk separators).

When done, save your summary to `<some-file>` then run:

  python3 .github/tools/memory.py write-summary {kind} <some-file>

The tool will atomically rotate tiers (oldest hot -> warm; oldest warm -> cold)
and delete this request file.

## Chunks to summarize

{chunks}
"""


def compact(kind: str, target: int, root: Path) -> Path:
    if kind not in {"sessions", "learnings", "glossary", "checkpoint"}:
        raise ValueError(f"compaction not applicable to kind={kind!r}")
    text = read(kind, budget=None, root=root)
    if not text:
        raise RuntimeError(f"no content to compact for kind={kind!r}")
    req_path = root / "_compact_request.md"
    body = COMPACT_REQUEST_TEMPLATE.format(
        kind=kind,
        target=target,
        ts=_now_iso(),
        chunks=text,
    )
    atomic_write_text(req_path, body)
    return req_path
```

Wire up subcommand:

```python
    p_compact = sub.add_parser("compact")
    p_compact.add_argument("kind")
    p_compact.add_argument("--target", type=int, default=2000)
```

```python
    if args.cmd == "compact":
        req = compact(args.kind, args.target, root)
        print(f"compaction request written to {req}")
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_memory.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/memory.py tests/tools/test_memory.py
git commit -m "feat(memory): compact command emits _compact_request.md for active agent"
```

---

### Task 10: `memory.py write-summary` — atomic tier rotation

**Files:**
- Modify: `.github/tools/memory.py`
- Modify: `tests/tools/test_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_memory.py`:

```python
def test_write_summary_rotates_oldest_to_warm_and_deletes_request(memory_tool, mem_root, tmp_path):
    # Set up 5 learnings entries, then ask to compact 3 oldest
    for i in range(5):
        subprocess.run(
            [sys.executable, str(memory_tool), "write", "learnings", f"entry-{i}"],
            check=True,
        )
    # Trigger compact (request written)
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
    # Request file deleted
    assert not (mem_root / "_compact_request.md").exists()
    # Warm file created with the summary
    warm = mem_root / "learnings_warm.md"
    assert warm.exists()
    assert "topics A, B, C" in warm.read_text()
    # Original learnings.md still has the most recent entries
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_memory.py::test_write_summary_rotates_oldest_to_warm_and_deletes_request -v
```

Expected: FAIL — `write-summary` not implemented.

- [ ] **Step 3: Implement `write_summary`**

In `.github/tools/memory.py`:

```python
def write_summary(kind: str, summary_path: Path, root: Path) -> None:
    """Apply a user-produced summary: append to *_warm.md, trim main file, delete request.

    For learnings/glossary: keep the most recent half of entries in the main file,
    fold the older half into _warm.md as the new summary block.
    For sessions: similar but operates per session file in sessions/ dir.
    """
    req = root / "_compact_request.md"
    if not req.exists():
        raise RuntimeError("no compaction request pending")
    summary = summary_path.read_text()
    if kind in ("learnings", "glossary"):
        main_path = _file_for(kind, root)
        text = main_path.read_text() if main_path.exists() else ""
        parts = re.split(r"(?m)^(?=## )", text)
        header = parts[0] if parts and not parts[0].startswith("## ") else ""
        entries = [p for p in parts if p.startswith("## ")]
        keep = max(1, len(entries) // 2)  # keep newest half
        to_warm = entries[:-keep]
        new_main = header + "".join(entries[-keep:])
        warm_path = root / f"{kind}_warm.md"
        prev_warm = warm_path.read_text() if warm_path.exists() else ""
        warm_block = f"\n## Summary written {_now_iso()}\n\n{summary.rstrip()}\n"
        atomic_write_text(warm_path, prev_warm + warm_block)
        atomic_write_text(main_path, new_main)
    elif kind == "sessions":
        sdir = root / "sessions"
        warm_path = sdir / "_warm.md"
        prev_warm = warm_path.read_text() if warm_path.exists() else ""
        warm_block = f"\n## Summary written {_now_iso()}\n\n{summary.rstrip()}\n"
        atomic_write_text(warm_path, prev_warm + warm_block)
        # Move all but the newest hot file into nothing (they're folded into the summary)
        hot = sorted(sdir.glob("20*.md"), reverse=True)
        for f in hot[1:]:
            f.unlink()
    elif kind == "checkpoint":
        # Checkpoint compaction = overwrite with summary
        atomic_write_text(_file_for("checkpoint", root), summary)
    else:
        raise ValueError(f"write-summary not applicable to kind={kind!r}")
    req.unlink()
```

Wire up subcommand:

```python
    p_ws = sub.add_parser("write-summary")
    p_ws.add_argument("kind")
    p_ws.add_argument("file")
```

```python
    if args.cmd == "write-summary":
        try:
            write_summary(args.kind, Path(args.file), root)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"summary applied; tiers rotated for {args.kind}")
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_memory.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/memory.py tests/tools/test_memory.py
git commit -m "feat(memory): write-summary atomically rotates hot->warm and clears request"
```

---

### Task 11: `memory.py search` — SQLite FTS5 across kinds

**Files:**
- Modify: `.github/tools/memory.py`
- Modify: `tests/tools/test_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_memory.py`:

```python
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
    assert "learnings" in cp.stdout  # source kind labeled


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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_memory.py::test_memory_search_finds_matches -v
```

Expected: FAIL — `search` not implemented.

- [ ] **Step 3: Implement `search` (rebuilds FTS index on each call — fine for tiny memory)**

In `.github/tools/memory.py`:

```python
import sqlite3


def _index_path(root: Path) -> Path:
    return root / "_fts.db"


def _rebuild_index(root: Path) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE VIRTUAL TABLE mem USING fts5(kind, source, content)")
    for kind in ["learnings", "glossary", "checkpoint"]:
        path = _file_for(kind, root) if kind != "sessions" else None
        if path and path.exists():
            db.execute(
                "INSERT INTO mem(kind, source, content) VALUES (?, ?, ?)",
                (kind, str(path.relative_to(root)), path.read_text()),
            )
    sdir = root / "sessions"
    if sdir.exists():
        for f in sdir.glob("*.md"):
            db.execute(
                "INSERT INTO mem(kind, source, content) VALUES (?, ?, ?)",
                ("sessions", f.name, f.read_text()),
            )
    ddir = root / "decisions"
    if ddir.exists():
        for f in ddir.glob("DEC-*.md"):
            db.execute(
                "INSERT INTO mem(kind, source, content) VALUES (?, ?, ?)",
                ("decisions", f.name, f.read_text()),
            )
    return db


def search(query: str, root: Path, kind: str | None = None, limit: int = 20) -> list[tuple[str, str, str]]:
    db = _rebuild_index(root)
    if kind:
        rows = db.execute(
            "SELECT kind, source, snippet(mem, 2, '<<', '>>', '...', 12) FROM mem "
            "WHERE kind = ? AND mem MATCH ? LIMIT ?",
            (kind, query, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT kind, source, snippet(mem, 2, '<<', '>>', '...', 12) FROM mem "
            "WHERE mem MATCH ? LIMIT ?",
            (query, limit),
        ).fetchall()
    return rows
```

Wire up:

```python
    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--kind", default=None)
    p_search.add_argument("--limit", type=int, default=20)
```

```python
    if args.cmd == "search":
        rows = search(args.query, root, args.kind, args.limit)
        for kind, source, snip in rows:
            print(f"[{kind}] {source}\n  {snip}\n")
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_memory.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/memory.py tests/tools/test_memory.py
git commit -m "feat(memory): search command via SQLite FTS5 over all memory kinds"
```

---

### Task 12: `memory.py recall` — ranked retrieval across decisions/learnings/glossary

**Files:**
- Modify: `.github/tools/memory.py`
- Modify: `tests/tools/test_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_memory.py`:

```python
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
    # All three kinds should appear (recall covers them); ordering: decisions first by convention
    assert "DEC-001" in out
    assert "leeway" in out
    assert "Open Authorization" in out
    assert out.find("[decisions]") < out.find("[learnings]") < out.find("[glossary]")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_memory.py::test_memory_recall_returns_ranked_snippets -v
```

Expected: FAIL — `recall` not implemented.

- [ ] **Step 3: Implement `recall`**

In `.github/tools/memory.py`:

```python
RECALL_KIND_ORDER = ["decisions", "learnings", "glossary", "sessions", "checkpoint"]


def recall(topic: str, root: Path, limit_per_kind: int = 5) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for kind in RECALL_KIND_ORDER:
        out.extend(search(topic, root, kind=kind, limit=limit_per_kind))
    return out
```

Wire up:

```python
    p_recall = sub.add_parser("recall")
    p_recall.add_argument("topic")
```

```python
    if args.cmd == "recall":
        for kind, source, snip in recall(args.topic, root):
            print(f"[{kind}] {source}\n  {snip}\n")
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_memory.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/memory.py tests/tools/test_memory.py
git commit -m "feat(memory): recall command with kind-priority ordering"
```

---

### Task 13: `memory.py forget` — explicit delete by id or path

**Files:**
- Modify: `.github/tools/memory.py`
- Modify: `tests/tools/test_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_memory.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_memory.py::test_memory_forget_deletes_decision_by_id -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `forget`**

In `.github/tools/memory.py`:

```python
def forget(identifier: str, root: Path) -> Path:
    """Delete a decision by DEC-NNN id, or a session by date stamp."""
    if identifier.startswith("DEC-"):
        ddir = root / "decisions"
        matches = list(ddir.glob(f"{identifier}-*.md"))
        if not matches:
            raise FileNotFoundError(f"no decision matches {identifier!r}")
        for m in matches:
            m.unlink()
        return matches[0]
    # Session by date prefix
    sdir = root / "sessions"
    matches = list(sdir.glob(f"{identifier}*.md"))
    if not matches:
        raise FileNotFoundError(f"no session matches {identifier!r}")
    for m in matches:
        m.unlink()
    return matches[0]
```

Wire up:

```python
    p_forget = sub.add_parser("forget")
    p_forget.add_argument("identifier")
```

```python
    if args.cmd == "forget":
        try:
            p = forget(args.identifier, root)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"deleted: {p}")
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_memory.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/memory.py tests/tools/test_memory.py
git commit -m "feat(memory): forget command for decisions and sessions"
```

---

### Task 14: `session.py start` — create a session directory

**Files:**
- Create: `.github/tools/session.py`
- Create: `tests/tools/test_session.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_session.py`:

```python
import sys
import shutil
import subprocess
import re
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


def test_session_start_creates_directory(session_tool, tmp_repo):
    cp = subprocess.run(
        [sys.executable, str(session_tool), "start", "--label", "feat-x"],
        capture_output=True, text=True, check=True,
    )
    out = cp.stdout.strip()
    # Output is the session id
    assert re.match(r"\d{4}-\d{2}-\d{2}-\d{4}-feat-x", out), out
    sdir = tmp_repo / ".github" / ".cache" / "sessions" / out
    assert sdir.is_dir()
    assert (sdir / "log.md").exists()
    assert (sdir / "tasks").is_dir()
    assert (sdir / "results").is_dir()
    assert (sdir / "reviews").is_dir()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_session.py -v
```

Expected: FAIL — `session.py` doesn't exist.

- [ ] **Step 3: Implement `start`**

`.github/tools/session.py`:

```python
#!/usr/bin/env python3
"""Session lifecycle CLI."""
from __future__ import annotations
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.io import atomic_write_text  # noqa: E402


def sessions_root(repo_root: Path | None = None) -> Path:
    return (repo_root or Path.cwd()) / ".github" / ".cache" / "sessions"


def _slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return s[:40] or "session"


def start(label: str, root: Path) -> str:
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    sid = f"{stamp}-{_slug(label)}"
    sdir = root / sid
    (sdir / "tasks").mkdir(parents=True)
    (sdir / "results").mkdir()
    (sdir / "reviews").mkdir()
    atomic_write_text(sdir / "log.md", f"# Session {sid}\n\nStarted at {stamp}\n")
    return sid


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    p_start = sub.add_parser("start")
    p_start.add_argument("--label", default="session")
    args = p.parse_args(argv)
    root = sessions_root()
    if args.cmd == "start":
        sid = start(args.label, root)
        print(sid)
        return 0
    p.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_session.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/session.py tests/tools/test_session.py
git commit -m "feat(session): start command creates session directory tree"
```

---

### Task 15: `session.py log` and `save`

**Files:**
- Modify: `.github/tools/session.py`
- Modify: `tests/tools/test_session.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_session.py`:

```python
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
    cp = subprocess.run(
        [sys.executable, str(session_tool), "save", sid, "--note", "midpoint"],
        capture_output=True, text=True, check=True,
    )
    snap = tmp_repo / ".github" / ".cache" / "sessions" / sid / "snapshot.md"
    assert snap.exists()
    assert "midpoint" in snap.read_text()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_session.py::test_session_log_appends_to_log_md -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `log` and `save`**

In `.github/tools/session.py`:

```python
def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(sid: str, event_type: str, message: str, root: Path) -> None:
    sdir = root / sid
    if not sdir.exists():
        raise FileNotFoundError(f"no session {sid!r}")
    log_path = sdir / "log.md"
    existing = log_path.read_text() if log_path.exists() else ""
    line = f"\n- {_now_iso()} [{event_type}] {message}\n"
    atomic_write_text(log_path, existing + line)


def save(sid: str, note: str, root: Path) -> None:
    sdir = root / sid
    if not sdir.exists():
        raise FileNotFoundError(f"no session {sid!r}")
    snap = sdir / "snapshot.md"
    body = f"# Snapshot {_now_iso()}\n\n{note}\n"
    atomic_write_text(snap, body)
```

Wire up:

```python
    p_log = sub.add_parser("log")
    p_log.add_argument("sid")
    p_log.add_argument("event_type")
    p_log.add_argument("message")

    p_save = sub.add_parser("save")
    p_save.add_argument("sid")
    p_save.add_argument("--note", default="")
```

```python
    if args.cmd == "log":
        log(args.sid, args.event_type, args.message, root)
        return 0
    if args.cmd == "save":
        save(args.sid, args.note, root)
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_session.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/session.py tests/tools/test_session.py
git commit -m "feat(session): log and save commands"
```

---

### Task 16: `session.py list` and `end`

**Files:**
- Modify: `.github/tools/session.py`
- Modify: `tests/tools/test_session.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_session.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_session.py::test_session_list_shows_sessions -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `list` and `end`**

In `.github/tools/session.py`:

```python
def list_sessions(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def end(sid: str, root: Path) -> None:
    sdir = root / sid
    if not sdir.exists():
        raise FileNotFoundError(f"no session {sid!r}")
    log(sid, "end", "session ended", root)
```

Wire up:

```python
    p_list = sub.add_parser("list")
    p_end = sub.add_parser("end")
    p_end.add_argument("sid")
```

```python
    if args.cmd == "list":
        for sid in list_sessions(root):
            print(sid)
        return 0
    if args.cmd == "end":
        end(args.sid, root)
        print(f"session ended: {args.sid}")
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_session.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/session.py tests/tools/test_session.py
git commit -m "feat(session): list and end commands"
```

---

### Task 17: `session.py archive` — auto-archive old sessions

**Files:**
- Modify: `.github/tools/session.py`
- Modify: `tests/tools/test_session.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_session.py`:

```python
import os
import time


def test_session_archive_moves_old_sessions(session_tool, tmp_repo):
    sid = subprocess.run(
        [sys.executable, str(session_tool), "start", "--label", "old"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    sdir = tmp_repo / ".github" / ".cache" / "sessions" / sid
    # Backdate mtime to 30 days ago
    old = time.time() - 30 * 86400
    for p in sdir.rglob("*"):
        os.utime(p, (old, old))
    os.utime(sdir, (old, old))
    cp = subprocess.run(
        [sys.executable, str(session_tool), "archive", "--days", "7"],
        capture_output=True, text=True, check=True,
    )
    assert sid in cp.stdout  # was archived
    # session moved into _archive/
    assert (tmp_repo / ".github" / ".cache" / "sessions" / "_archive" / sid).is_dir()
    assert not (tmp_repo / ".github" / ".cache" / "sessions" / sid).exists()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_session.py::test_session_archive_moves_old_sessions -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `archive`**

In `.github/tools/session.py`:

```python
import shutil


def archive(days: int, root: Path) -> list[str]:
    archive_dir = root / "_archive"
    archive_dir.mkdir(exist_ok=True)
    cutoff = dt.datetime.now().timestamp() - days * 86400
    moved: list[str] = []
    if not root.exists():
        return moved
    for p in root.iterdir():
        if not p.is_dir() or p.name == "_archive":
            continue
        if p.stat().st_mtime < cutoff:
            shutil.move(str(p), str(archive_dir / p.name))
            moved.append(p.name)
    return moved
```

Wire up:

```python
    p_arch = sub.add_parser("archive")
    p_arch.add_argument("--days", type=int, default=7)
```

```python
    if args.cmd == "archive":
        moved = archive(args.days, root)
        for m in moved:
            print(m)
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_session.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/session.py tests/tools/test_session.py
git commit -m "feat(session): archive command moves stale sessions to _archive/"
```

---

### Task 18: `session.py resume` — load prior session metadata

**Files:**
- Modify: `.github/tools/session.py`
- Modify: `tests/tools/test_session.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_session.py`:

```python
def test_session_resume_prints_log_and_open_artifacts(session_tool, tmp_repo):
    sid = subprocess.run(
        [sys.executable, str(session_tool), "start", "--label", "resume"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run([sys.executable, str(session_tool), "log", sid, "info", "did the thing"], check=True)
    # Add a fake task and a fake result
    sdir = tmp_repo / ".github" / ".cache" / "sessions" / sid
    (sdir / "tasks" / "1-foo.md").write_text("---\ntask_id: 1\n---\n# Task 1")
    cp = subprocess.run(
        [sys.executable, str(session_tool), "resume", sid],
        capture_output=True, text=True, check=True,
    )
    assert "did the thing" in cp.stdout
    assert "1-foo.md" in cp.stdout
    assert "no results" in cp.stdout.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/tools/test_session.py::test_session_resume_prints_log_and_open_artifacts -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `resume`**

In `.github/tools/session.py`:

```python
def resume(sid: str, root: Path) -> str:
    sdir = root / sid
    if not sdir.exists():
        raise FileNotFoundError(f"no session {sid!r}")
    out = [f"# Resuming session {sid}\n"]
    log_path = sdir / "log.md"
    if log_path.exists():
        out.append("## Log\n")
        out.append(log_path.read_text())
    tasks = sorted((sdir / "tasks").glob("*.md")) if (sdir / "tasks").exists() else []
    if tasks:
        out.append("\n## Tasks\n")
        for t in tasks:
            out.append(f"- {t.name}")
    results = sorted((sdir / "results").glob("*.md")) if (sdir / "results").exists() else []
    if results:
        out.append("\n## Results\n")
        for r in results:
            out.append(f"- {r.name}")
    else:
        out.append("\n(no results yet)")
    return "\n".join(out)
```

Wire up:

```python
    p_resume = sub.add_parser("resume")
    p_resume.add_argument("sid")
```

```python
    if args.cmd == "resume":
        print(resume(args.sid, root))
        return 0
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/tools/test_session.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/tools/session.py tests/tools/test_session.py
git commit -m "feat(session): resume command prints log + open tasks/results"
```

---

### Task 19: End-to-end smoke test (memory + session)

**Files:**
- Create: `tests/tools/test_e2e_a1.py`

- [ ] **Step 1: Write the failing test**

`tests/tools/test_e2e_a1.py`:

```python
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

    # Write some memory
    py(tools["memory"], "write", "decisions", "DEC-001: use Sonnet 4.6 for compaction")
    py(tools["memory"], "write", "learnings", "tree-sitter-language-pack covers ~50 languages")
    py(tools["memory"], "write", "glossary", "FTS: full-text search")
    py(tools["memory"], "write", "checkpoint", "midway through Plan A1")

    # Status: not over
    cp = subprocess.run(
        [sys.executable, str(tools["memory"]), "status"],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode == 0

    # Recall
    out = py(tools["memory"], "recall", "compaction")
    assert "DEC-001" in out

    # Search filtered
    out = py(tools["memory"], "search", "tree-sitter")
    assert "language-pack" in out

    # Read with budget
    out = py(tools["memory"], "read", "checkpoint")
    assert "midway through" in out

    # End session
    py(tools["session"], "end", sid)
    log_text = (tmp_repo / ".github" / ".cache" / "sessions" / sid / "log.md").read_text()
    assert "[end]" in log_text

    # List sessions
    out = py(tools["session"], "list")
    assert sid in out
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/tools/test_e2e_a1.py -v
```

Expected: PASS — all individual subsystems already work; this confirms they compose.

- [ ] **Step 3: (No code changes needed if it passes; otherwise debug whichever subsystem fails)**

If a step fails, return to the responsible task and fix.

- [ ] **Step 4: Run the full test suite**

```bash
pytest tests/tools/ -v
```

Expected: all tests across config/memory/session/lib/e2e pass (~25+ tests).

- [ ] **Step 5: Commit**

```bash
git add tests/tools/test_e2e_a1.py
git commit -m "test(e2e): end-to-end smoke test for memory + session subsystems"
```

---

## Self-review checklist

After completing all 19 tasks, verify against the spec:

| Spec section | Plan A1 coverage |
|---|---|
| §3.2 memory.py — kinds, budgets, layered storage | Tasks 6–13 |
| §3.2 — write/read/search/recall/status/compact/write-summary/forget | Tasks 6, 7, 8, 9, 10, 11, 12, 13 |
| §3.2 — token-budgeted reads | Task 7 |
| §3.2 — auto-compaction flow | Tasks 9, 10 |
| §3.3 session.py — start/log/save/end/list/resume/archive | Tasks 14, 15, 16, 17, 18 |
| §12 config.yaml schema | Task 2 |
| §2.5 profile resolution + feature resolution | Tasks 3, 4 |
| §3.2 memory_compaction_model = Sonnet 4.6 | encoded in config.yaml (Task 2); referenced in compaction request (Task 9) |

**Gaps Plan A1 deliberately leaves for later plans:**
- `codegraph.py` (Plan A2)
- `bootstrap.sh` and profile detection at `/init` (Plan A3)
- Tier-aware behavior gating in tools (Plan A2 / A3 — once codegraph exists)
- `memory.py` "warm tier read" (currently `read` returns hot only; warm is written via `write-summary` but reading from warm is added in Plan A2 alongside the tier rotation refinement)

Document the warm-tier read gap with a TODO comment in `memory.py read`:

```python
    # TODO(plan-a2): when warm/cold tiers exist, fall through to them once hot
    # is exhausted but budget remains. Plan A1 returns hot only.
```

---

## Final verification before plan completion

Run the entire suite from a clean state:

```bash
git stash
git stash pop  # confirm tree clean
pytest tests/tools/ -v --tb=short
```

Expected: all tests PASS, exit 0.

If you reach this point with all tests passing, Plan A1 is complete. Hand off to **Plan A2 (Code Graph Tool)** by announcing:

> Plan A1 complete. Next: Plan A2 — codegraph.py (tree-sitter + SQLite, profile-aware).

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-05-plan-a1-foundation-tools.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration. Use `superpowers:subagent-driven-development`.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch with checkpoints for review.

**Which approach?**
