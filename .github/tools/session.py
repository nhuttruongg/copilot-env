#!/usr/bin/env python3
"""Session lifecycle CLI."""
from __future__ import annotations
import argparse
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.io import atomic_write_text  # noqa: E402


def sessions_root(repo_root: Path | None = None) -> Path:
    return (repo_root or Path.cwd()) / ".github" / ".cache" / "sessions"


def _slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return s[:40] or "session"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def start(label: str, root: Path) -> str:
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    sid = f"{stamp}-{_slug(label)}"
    sdir = root / sid
    (sdir / "tasks").mkdir(parents=True)
    (sdir / "results").mkdir()
    (sdir / "reviews").mkdir()
    atomic_write_text(sdir / "log.md", f"# Session {sid}\n\nStarted at {stamp}\n")
    return sid


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


def list_sessions(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def end(sid: str, root: Path) -> None:
    sdir = root / sid
    if not sdir.exists():
        raise FileNotFoundError(f"no session {sid!r}")
    log(sid, "end", "session ended", root)


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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start")
    p_start.add_argument("--label", default="session")

    p_log = sub.add_parser("log")
    p_log.add_argument("sid")
    p_log.add_argument("event_type")
    p_log.add_argument("message")

    p_save = sub.add_parser("save")
    p_save.add_argument("sid")
    p_save.add_argument("--note", default="")

    sub.add_parser("list")

    p_end = sub.add_parser("end")
    p_end.add_argument("sid")

    p_arch = sub.add_parser("archive")
    p_arch.add_argument("--days", type=int, default=7)

    p_resume = sub.add_parser("resume")
    p_resume.add_argument("sid")

    args = p.parse_args(argv)
    root = sessions_root()

    if args.cmd == "start":
        sid = start(args.label, root)
        print(sid)
        return 0
    if args.cmd == "log":
        log(args.sid, args.event_type, args.message, root)
        return 0
    if args.cmd == "save":
        save(args.sid, args.note, root)
        return 0
    if args.cmd == "list":
        for sid in list_sessions(root):
            print(sid)
        return 0
    if args.cmd == "end":
        end(args.sid, root)
        print(f"session ended: {args.sid}")
        return 0
    if args.cmd == "archive":
        moved = archive(args.days, root)
        for m in moved:
            print(m)
        return 0
    if args.cmd == "resume":
        print(resume(args.sid, root))
        return 0
    p.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
