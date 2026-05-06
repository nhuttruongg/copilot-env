#!/usr/bin/env python3
"""Code graph CLI: scan, update, and query a SQLite-backed code index."""
from __future__ import annotations
import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.db import open_db, ensure_schema
from _lib.walker import iter_files, detect_lang
from _lib.adapters import get_adapter


def _file_meta(p: Path, source: bytes) -> tuple[str, float, int]:
    sha = hashlib.sha256(source).hexdigest()
    mtime = p.stat().st_mtime
    line_count = source.count(b"\n") + 1
    return sha, mtime, line_count


def _persist_extracted(db: sqlite3.Connection, file_id: int, ex) -> None:
    sym_id_by_qual: dict[str, int] = {}
    for s in ex.symbols:
        cur = db.execute(
            "INSERT INTO symbols(file_id, name, qualified_name, kind, start_line, "
            "end_line, signature, docstring, visibility) VALUES (?,?,?,?,?,?,?,?,?)",
            (file_id, s.name, s.qualified_name, s.kind, s.start_line, s.end_line,
             s.signature, s.docstring, s.visibility),
        )
        if s.qualified_name:
            sym_id_by_qual[s.qualified_name] = cur.lastrowid
    for i in ex.imports:
        db.execute(
            "INSERT INTO imports(from_file_id, to_module, imported, alias, line) "
            "VALUES (?,?,?,?,?)",
            (file_id, i.to_module, i.imported, i.alias, i.line),
        )
    for c in ex.calls:
        caller_id = sym_id_by_qual.get(c.caller_name)
        db.execute(
            "INSERT INTO calls(caller_symbol_id, callee_name, callee_symbol_id, line) "
            "VALUES (?,?,?,?)",
            (caller_id, c.callee_name, None, c.line),
        )


def _parse_one(args: tuple[str, str, str]) -> tuple:
    """Worker: parse a single file. Returns tuple for DB insert."""
    rel_path, abs_path, root_str = args
    p = Path(abs_path)
    lang = detect_lang(p)
    if lang is None:
        return rel_path, "", "", 0.0, 0, 0, None
    adapter = get_adapter(lang)
    if adapter is None:
        return rel_path, lang, "", 0.0, 0, 0, None
    try:
        source = p.read_bytes()
    except OSError:
        return rel_path, lang, "", 0.0, 0, 1, None
    sha, mtime, lc = _file_meta(p, source)
    try:
        extracted = adapter.extract(source, rel_path)
        return rel_path, lang, sha, mtime, lc, 0, extracted
    except Exception:
        return rel_path, lang, sha, mtime, lc, 1, None


def scan_into(root: Path, db_path: Path, exclude: list[str], workers: int = 1) -> int:
    """Scan root, persist into db_path. Returns count of indexed files."""
    db = open_db(db_path)
    ensure_schema(db)
    db.executescript("DELETE FROM refs; DELETE FROM calls; DELETE FROM imports; "
                     "DELETE FROM symbols; DELETE FROM files;")
    db.commit()

    targets = []
    for p in iter_files(root, exclude):
        if detect_lang(p) is None:
            continue
        rel = str(p.relative_to(root))
        targets.append((rel, str(p), str(root)))

    if workers <= 1:
        results = [_parse_one(t) for t in targets]
    else:
        from multiprocessing import Pool
        with Pool(workers) as pool:
            results = pool.map(_parse_one, targets, chunksize=20)

    n = 0
    for rel_path, lang, sha, mtime, lc, parse_err, extracted in results:
        if not lang:
            continue
        cur = db.execute(
            "INSERT INTO files(path, lang, sha256, mtime, line_count, parse_error) "
            "VALUES (?,?,?,?,?,?)",
            (rel_path, lang, sha, mtime, lc, parse_err),
        )
        if extracted is not None:
            _persist_extracted(db, cur.lastrowid, extracted)
        n += 1
    db.commit()
    return n


def update_into(root: Path, db_path: Path, exclude: list[str]) -> int:
    """Incremental update: re-index changed/new files, remove deleted.

    Returns count of files re-indexed (not counting deletions).
    """
    db = open_db(db_path)
    ensure_schema(db)
    existing = {row[0]: (row[1], row[2]) for row in db.execute(
        "SELECT path, mtime, sha256 FROM files").fetchall()}
    seen: set[str] = set()
    changed = 0
    for p in iter_files(root, exclude):
        if detect_lang(p) is None:
            continue
        rel = str(p.relative_to(root))
        seen.add(rel)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        prev = existing.get(rel)
        if prev is not None and abs(prev[0] - mtime) < 1e-6:
            continue  # unchanged
        db.execute("DELETE FROM files WHERE path = ?", (rel,))
        rel_path, lang, sha, mt, lc, parse_err, extracted = _parse_one(
            (rel, str(p), str(root)))
        if not lang:
            continue
        cur = db.execute(
            "INSERT INTO files(path, lang, sha256, mtime, line_count, parse_error) "
            "VALUES (?,?,?,?,?,?)",
            (rel_path, lang, sha, mt, lc, parse_err),
        )
        if extracted is not None:
            _persist_extracted(db, cur.lastrowid, extracted)
        changed += 1
    for rel in list(existing.keys()):
        if rel not in seen:
            db.execute("DELETE FROM files WHERE path = ?", (rel,))
    db.commit()
    return changed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="codegraph")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--root", default=".")
    p_scan.add_argument("--db", default=".github/.cache/codegraph.db")
    p_scan.add_argument("--exclude", nargs="*", default=[])
    p_scan.add_argument("--workers", type=int, default=1)

    p_upd = sub.add_parser("update")
    p_upd.add_argument("--root", default=".")
    p_upd.add_argument("--db", default=".github/.cache/codegraph.db")
    p_upd.add_argument("--exclude", nargs="*", default=[])

    args = p.parse_args(argv)
    if args.cmd == "scan":
        n = scan_into(Path(args.root), Path(args.db), args.exclude, args.workers)
        print(f"indexed {n} files into {args.db}")
        return 0
    if args.cmd == "update":
        n = update_into(Path(args.root), Path(args.db), args.exclude)
        print(f"updated {n} files in {args.db}")
        return 0
    p.error(f"unsupported command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
