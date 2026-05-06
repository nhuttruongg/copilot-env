"""File walker with glob-pattern excludes."""
from __future__ import annotations
import fnmatch
from pathlib import Path
from typing import Iterator

EXT_LANG = {
    ".py":  "python",
    ".ts":  "typescript",
    ".tsx": "tsx",
    ".js":  "javascript",
    ".jsx": "javascript",
    ".go":  "go",
    ".rs":  "rust",
    ".java": "java",
    ".c":   "c",
    ".h":   "c",
    ".cc":  "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
}


def detect_lang(path: Path) -> str | None:
    return EXT_LANG.get(path.suffix.lower())


def _match_any(rel: str, patterns: list[str]) -> bool:
    p = Path(rel)
    for pat in patterns:
        if "**" in pat:
            # Use pathlib.PurePosixPath.match which handles ** natively in 3.12+
            # For 3.10/3.11 compatibility, check each parent component
            try:
                if p.match(pat):
                    return True
            except Exception:
                pass
            # Also check: strip leading **/ and see if any path suffix matches
            inner = pat.replace("**/", "").replace("/**", "")
            for part in p.parts:
                if fnmatch.fnmatch(part, inner):
                    return True
        else:
            if fnmatch.fnmatch(rel, pat):
                return True
    return False


def iter_files(root: Path, exclude: list[str] | None = None) -> Iterator[Path]:
    exclude = exclude or []
    root = root.resolve()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        if _match_any(rel, exclude):
            continue
        yield p
