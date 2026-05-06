"""Smoke test: scan must handle ~1000 small files in < 30s.

Set RUN_PERF=1 to opt in.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from codegraph import scan_into  # noqa: E402


@pytest.mark.skipif(not __import__("os").environ.get("RUN_PERF"),
                    reason="set RUN_PERF=1 to run perf smoke test")
def test_scan_1000_python_files_under_30s(tmp_path: Path):
    src = tmp_path / "synth"
    src.mkdir()
    for i in range(1000):
        (src / f"m{i}.py").write_text(
            f"def f{i}(x):\n    '''doc {i}.'''\n    return x + {i}\n"
        )
    dbp = tmp_path / "g.db"
    t0 = time.time()
    n = scan_into(src, dbp, exclude=[], workers=4)
    elapsed = time.time() - t0
    assert n == 1000
    assert elapsed < 30.0, f"scan took {elapsed:.1f}s, expected < 30s"
