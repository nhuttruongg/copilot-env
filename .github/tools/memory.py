#!/usr/bin/env python3
"""Memory CLI for the Copilot agentic environment.

Layered memory with bounded budgets. Plain markdown files on disk; SQLite FTS
is used for search/recall. This module implements:
  write, read, status, compact, write-summary, search, recall, forget

Usage:
    memory.py write <kind> <content>
    memory.py read <kind> [--budget N]
    memory.py status [--json]
    memory.py search "<query>" [--kind=K] [--limit N]
    memory.py recall "<topic>"
    memory.py compact <kind> [--target N]
    memory.py write-summary <kind> <file>
    memory.py forget <id>
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.io import atomic_write_text  # noqa: E402
from _lib.text import approx_tokens  # noqa: E402
from config import load_config  # noqa: E402

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
    if kind == "learnings":
        _append_simple(_file_for(kind, root), content)
    elif kind == "glossary":
        _write_glossary(root / "glossary.md", content)
    elif kind == "checkpoint":
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
        return _append_simple(path, content)
    term = m.group(1).strip()
    existing = path.read_text() if path.exists() else ""
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


def read(kind: str, budget: int | None, root: Path) -> str:
    """Return memory content for kind, capped to budget tokens.

    For append-style kinds (learnings, glossary), reads from newest entry first
    and stops adding entries once budget is hit.
    # TODO(plan-a2): when warm/cold tiers exist, fall through to them once hot
    # is exhausted but budget remains. Plan A1 returns hot only.
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
        hot = sorted(sdir.glob("20*.md"), reverse=True)
        out = ""
        for f in hot:
            chunk = f.read_text() + "\n"
            if budget is not None and approx_tokens(out + chunk) > budget:
                break
            out += chunk
        return out
    return ""


def _budgets(root: Path) -> dict[str, dict[str, int]]:
    cfg_path = root.parent.parent / "config.yaml"
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


def write_summary(kind: str, summary_path: Path, root: Path) -> None:
    """Apply a user-produced summary: append to *_warm.md, trim main file, delete request."""
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
        keep = max(1, len(entries) // 2)
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
        hot = sorted(sdir.glob("20*.md"), reverse=True)
        for f in hot[1:]:
            f.unlink()
    elif kind == "checkpoint":
        atomic_write_text(_file_for("checkpoint", root), summary)
    else:
        raise ValueError(f"write-summary not applicable to kind={kind!r}")
    req.unlink()


def _rebuild_index(root: Path) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE VIRTUAL TABLE mem USING fts5(kind, source, content)")
    for kind in ["learnings", "glossary", "checkpoint"]:
        path = _file_for(kind, root)
        if path.exists():
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


def _fts_query(query: str) -> str:
    """Wrap query in quotes if it contains FTS5 special characters (e.g. hyphens)."""
    if re.search(r'[-+*^()"]', query):
        return f'"{query}"'
    return query


def search(query: str, root: Path, kind: str | None = None, limit: int = 20) -> list[tuple[str, str, str]]:
    db = _rebuild_index(root)
    fts_q = _fts_query(query)
    if kind:
        rows = db.execute(
            "SELECT kind, source, snippet(mem, 2, '<<', '>>', '...', 12) FROM mem "
            "WHERE kind = ? AND mem MATCH ? LIMIT ?",
            (kind, fts_q, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT kind, source, snippet(mem, 2, '<<', '>>', '...', 12) FROM mem "
            "WHERE mem MATCH ? LIMIT ?",
            (fts_q, limit),
        ).fetchall()
    return rows


RECALL_KIND_ORDER = ["decisions", "learnings", "glossary", "sessions", "checkpoint"]


def recall(topic: str, root: Path, limit_per_kind: int = 5) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for kind in RECALL_KIND_ORDER:
        out.extend(search(topic, root, kind=kind, limit=limit_per_kind))
    return out


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
    sdir = root / "sessions"
    matches = list(sdir.glob(f"{identifier}*.md"))
    if not matches:
        raise FileNotFoundError(f"no session matches {identifier!r}")
    for m in matches:
        m.unlink()
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write")
    p_write.add_argument("kind", choices=sorted(KINDS))
    p_write.add_argument("content")

    p_read = sub.add_parser("read")
    p_read.add_argument("kind", choices=sorted(KINDS))
    p_read.add_argument("--budget", type=int, default=None)

    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")

    p_compact = sub.add_parser("compact")
    p_compact.add_argument("kind")
    p_compact.add_argument("--target", type=int, default=2000)

    p_ws = sub.add_parser("write-summary")
    p_ws.add_argument("kind")
    p_ws.add_argument("file")

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--kind", default=None)
    p_search.add_argument("--limit", type=int, default=20)

    p_recall = sub.add_parser("recall")
    p_recall.add_argument("topic")

    p_forget = sub.add_parser("forget")
    p_forget.add_argument("identifier")

    args = p.parse_args(argv)
    root = memory_root()

    if args.cmd == "write":
        write(args.kind, args.content, root)
        return 0
    if args.cmd == "read":
        sys.stdout.write(read(args.kind, args.budget, root))
        return 0
    if args.cmd == "status":
        data, over = status(root)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            for kind, v in data.items():
                marker = "!" if v["tokens"] > v["hard"] else ("." if v["tokens"] > v["soft"] else "ok")
                print(f"{marker} {kind:<12} {v['tokens']:>6} tokens  (soft={v['soft']}, hard={v['hard']})")
        return 1 if over else 0
    if args.cmd == "compact":
        req = compact(args.kind, args.target, root)
        print(f"compaction request written to {req}")
        return 0
    if args.cmd == "write-summary":
        try:
            write_summary(args.kind, Path(args.file), root)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"summary applied; tiers rotated for {args.kind}")
        return 0
    if args.cmd == "search":
        rows = search(args.query, root, args.kind, args.limit)
        for kind, source, snip in rows:
            print(f"[{kind}] {source}\n  {snip}\n")
        return 0
    if args.cmd == "recall":
        for kind, source, snip in recall(args.topic, root):
            print(f"[{kind}] {source}\n  {snip}\n")
        return 0
    if args.cmd == "forget":
        try:
            p_result = forget(args.identifier, root)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"deleted: {p_result}")
        return 0
    p.error(f"unsupported command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
