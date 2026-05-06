#!/usr/bin/env python3
"""Code graph CLI: scan, update, and query a SQLite-backed code index."""
from __future__ import annotations
import argparse
import hashlib
import json as _json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.db import open_db, ensure_schema
from _lib.walker import iter_files, detect_lang
from _lib.adapters import get_adapter


# ---------------------------------------------------------------------------
# Profile gating
# ---------------------------------------------------------------------------

def _active_code_graph_mode(repo_root: Path) -> str:
    """Resolve features.code_graph -> 'full', 'symbols-only', or 'off'."""
    cfg_path = repo_root / ".github" / "config.yaml"
    if not cfg_path.exists():
        return "full"
    try:
        from config import load_config, resolve_feature
        cfg = load_config(cfg_path)
        val = cfg.features.get("code_graph", "auto")
        return resolve_feature("code_graph", val, cfg.profile)
    except Exception:
        return "full"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _file_meta(p: Path, source: bytes) -> tuple[str, float, int]:
    sha = hashlib.sha256(source).hexdigest()
    mtime = p.stat().st_mtime
    line_count = source.count(b"\n") + 1
    return sha, mtime, line_count


def _persist_extracted(db: sqlite3.Connection, file_id: int, ex, mode: str = "full") -> None:
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
    if mode == "symbols-only":
        return
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


# ---------------------------------------------------------------------------
# Scan + update
# ---------------------------------------------------------------------------

def scan_into(root: Path, db_path: Path, exclude: list[str], workers: int = 1) -> int | str:
    """Scan root, persist into db_path. Returns count of indexed files (or status string)."""
    mode = _active_code_graph_mode(root)
    if mode == "off":
        return "graph disabled at this profile (tiny)"

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
            _persist_extracted(db, cur.lastrowid, extracted, mode)
        n += 1
    db.commit()
    return n


def update_into(root: Path, db_path: Path, exclude: list[str]) -> int:
    """Incremental update: re-index changed/new files, remove deleted.

    Returns count of files re-indexed (not counting deletions).
    """
    mode = _active_code_graph_mode(root)
    if mode == "off":
        return 0

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
            _persist_extracted(db, cur.lastrowid, extracted, mode)
        changed += 1
    for rel in list(existing.keys()):
        if rel not in seen:
            db.execute("DELETE FROM files WHERE path = ?", (rel,))
    db.commit()
    return changed


# ---------------------------------------------------------------------------
# Query commands
# ---------------------------------------------------------------------------

def cmd_find(name: str, db_path: Path, kind: str | None = None,
             lang: str | None = None) -> list[dict]:
    db = open_db(db_path)
    sql = ("SELECT s.id, s.name, s.qualified_name, s.kind, f.path, "
           "s.start_line, s.end_line, s.signature, f.lang "
           "FROM symbols s JOIN files f ON s.file_id = f.id WHERE s.name = ?")
    params: list = [name]
    if kind:
        sql += " AND s.kind = ?"
        params.append(kind)
    if lang:
        sql += " AND f.lang = ?"
        params.append(lang)
    sql += " ORDER BY f.path, s.start_line"
    rows = db.execute(sql, params).fetchall()
    keys = ["id", "name", "qualified_name", "kind", "file",
            "start_line", "end_line", "signature", "lang"]
    return [dict(zip(keys, r)) for r in rows]


def cmd_callees(qualified_or_name: str, db_path: Path) -> list[dict]:
    db = open_db(db_path)
    rows = db.execute(
        "SELECT c.callee_name, c.line, f.path "
        "FROM calls c "
        "JOIN symbols s ON c.caller_symbol_id = s.id "
        "JOIN files f ON s.file_id = f.id "
        "WHERE s.qualified_name = ? OR s.name = ? "
        "ORDER BY f.path, c.line",
        (qualified_or_name, qualified_or_name),
    ).fetchall()
    return [{"callee_name": r[0], "line": r[1], "file": r[2]} for r in rows]


def cmd_callers(name: str, db_path: Path) -> list[dict]:
    db = open_db(db_path)
    rows = db.execute(
        "SELECT s.qualified_name, s.name, c.line, f.path "
        "FROM calls c "
        "LEFT JOIN symbols s ON c.caller_symbol_id = s.id "
        "LEFT JOIN files f ON s.file_id = f.id "
        "WHERE c.callee_name = ? OR c.callee_name LIKE ? "
        "ORDER BY f.path, c.line",
        (name, f"%.{name}"),
    ).fetchall()
    return [{"caller_qualified": r[0] or "", "caller_name": r[1] or "",
             "line": r[2], "file": r[3] or ""} for r in rows]


def cmd_deps(file_path: str, db_path: Path) -> list[dict]:
    db = open_db(db_path)
    rows = db.execute(
        "SELECT i.to_module, i.imported, i.alias, i.line "
        "FROM imports i JOIN files f ON i.from_file_id = f.id "
        "WHERE f.path = ? ORDER BY i.line",
        (file_path,),
    ).fetchall()
    return [{"to_module": r[0], "imported": r[1], "alias": r[2], "line": r[3]}
            for r in rows]


def cmd_impact(file_path: str, db_path: Path, depth: int = 2) -> list[dict]:
    """Return files that (transitively) import this file's module."""
    db = open_db(db_path)
    stem = Path(file_path).stem
    direct = db.execute(
        "SELECT DISTINCT f.path "
        "FROM imports i JOIN files f ON i.from_file_id = f.id "
        "WHERE i.to_module LIKE ? OR i.to_module = ?",
        (f"%{stem}", stem),
    ).fetchall()
    seen = {r[0] for r in direct}
    frontier = list(seen)
    out = [{"path": p, "depth": 1} for p in seen]
    cur_depth = 1
    while frontier and cur_depth < depth:
        cur_depth += 1
        next_frontier: list[str] = []
        for fp in frontier:
            fstem = Path(fp).stem
            placeholders = ",".join(["?"] * len(seen)) if seen else "'__never__'"
            q = (f"SELECT DISTINCT f.path FROM imports i JOIN files f ON i.from_file_id = f.id "
                 f"WHERE i.to_module LIKE ? AND f.path NOT IN ({placeholders})")
            params_: list = [f"%{fstem}", *list(seen)]
            rows = db.execute(q, params_).fetchall() if seen else []
            for r in rows:
                next_frontier.append(r[0])
                seen.add(r[0])
                out.append({"path": r[0], "depth": cur_depth})
        frontier = next_frontier
    return out


def cmd_search(query: str, db_path: Path, limit: int = 20) -> list[dict]:
    db = open_db(db_path)
    try:
        rows = db.execute(
            "SELECT s.name, s.qualified_name, s.kind, f.path, s.start_line, "
            "snippet(symbols_fts, 3, '<<', '>>', '...', 8) "
            "FROM symbols_fts JOIN symbols s ON symbols_fts.rowid = s.id "
            "JOIN files f ON s.file_id = f.id "
            "WHERE symbols_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (query, limit),
        ).fetchall()
    except Exception:
        rows = []
    return [{"name": r[0], "qualified_name": r[1], "kind": r[2], "file": r[3],
             "start_line": r[4], "snippet": r[5]} for r in rows]


def cmd_envelope(target: str, db_path: Path, root_path: Path,
                 budget: int = 2000) -> str:
    """Build a context envelope for a symbol or file path, capped at budget tokens."""
    db = open_db(db_path)
    out: list[str] = []
    used = 0

    def add(text: str) -> bool:
        nonlocal used
        t = (len(text) + 3) // 4
        if used + t > budget:
            return False
        out.append(text)
        used += t
        return True

    is_file = ("/" in target or "\\" in target or
               target.endswith((".py", ".ts", ".tsx", ".js", ".go",
                                ".java", ".rs", ".c", ".cpp", ".h")))
    if is_file:
        rows = db.execute(
            "SELECT id, lang FROM files WHERE path = ?", (target,)
        ).fetchone()
        if not rows:
            return f"# File not found in graph: {target}\n"
        file_id, lang = rows
        add(f"# File: {target}\n\n## File: {target} (lang={lang})\n")
        syms = db.execute(
            "SELECT name, kind, start_line, signature FROM symbols WHERE file_id = ? "
            "ORDER BY start_line LIMIT 20",
            (file_id,),
        ).fetchall()
        if syms:
            add("\n## Symbols in file\n")
            for s in syms:
                add(f"- L{s[2]}  {s[1]:<7}  `{s[3]}`\n")
        imps = db.execute(
            "SELECT to_module, imported, alias FROM imports WHERE from_file_id = ? LIMIT 20",
            (file_id,),
        ).fetchall()
        if imps:
            add("\n## Imports\n")
            for i in imps:
                add(f"- {i[0]}  {i[1] or ''}  {('as ' + i[2]) if i[2] else ''}\n")
        return "".join(out)

    sym = db.execute(
        "SELECT s.id, s.name, s.kind, s.qualified_name, s.signature, s.docstring, "
        "s.start_line, s.end_line, f.path "
        "FROM symbols s JOIN files f ON s.file_id = f.id "
        "WHERE s.qualified_name = ? OR s.name = ? "
        "LIMIT 1",
        (target, target),
    ).fetchone()
    if not sym:
        return f"# Symbol not found in graph: {target}\n"
    sid, name, kind, qual, sig, doc, sl, el, fpath = sym
    add(f"# Envelope: {qual or name}\n\n## Symbol: {qual or name}\n")
    add(f"- file: `{fpath}` lines {sl}-{el}\n- kind: {kind}\n- signature: `{sig}`\n")
    if doc:
        add(f"- doc: {doc[:300]}\n")
    full = (root_path / fpath).read_text(errors="replace") if (root_path / fpath).exists() else ""
    if full:
        body_lines = full.splitlines()[sl - 1:el]
        body = "\n".join(body_lines[:40])
        add(f"\n```\n{body}\n```\n")
    callers = db.execute(
        "SELECT s2.qualified_name, f2.path, c.line "
        "FROM calls c "
        "LEFT JOIN symbols s2 ON c.caller_symbol_id = s2.id "
        "LEFT JOIN files f2 ON s2.file_id = f2.id "
        "WHERE c.callee_name = ? OR c.callee_name LIKE ? "
        "LIMIT 10",
        (name, f"%.{name}"),
    ).fetchall()
    if callers:
        add("\n## Callers\n")
        for q, p, ln in callers:
            add(f"- {p}:{ln}  {q or ''}\n")
    callees = db.execute(
        "SELECT callee_name, line FROM calls WHERE caller_symbol_id = ? LIMIT 10",
        (sid,),
    ).fetchall()
    if callees:
        add("\n## Callees\n")
        for c, ln in callees:
            add(f"- {c} (L{ln})\n")
    return "".join(out)


def cmd_stats(db_path: Path) -> dict:
    db = open_db(db_path)
    files = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    symbols = db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    imports = db.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
    calls = db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    parse_errors = db.execute("SELECT COUNT(*) FROM files WHERE parse_error=1").fetchone()[0]
    last_scan = db.execute("SELECT MAX(mtime) FROM files").fetchone()[0]
    return {
        "files": files, "symbols": symbols, "imports": imports, "calls": calls,
        "parse_errors": parse_errors, "last_scan": last_scan,
    }


def cmd_why_stale(root: Path, db_path: Path, exclude: list[str]) -> dict:
    db = open_db(db_path)
    indexed = {r[0]: r[1] for r in db.execute("SELECT path, mtime FROM files").fetchall()}
    stale = 0
    new = 0
    for p in iter_files(root, exclude):
        if detect_lang(p) is None:
            continue
        rel = str(p.relative_to(root))
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        prev = indexed.get(rel)
        if prev is None:
            new += 1
        elif abs(prev - mtime) >= 1e-6:
            stale += 1
    return {"stale_files": stale, "new_files": new, "total_indexed": len(indexed)}


def cmd_module(path: str, db_path: Path) -> dict:
    db = open_db(db_path)
    if path in (".", ""):
        prefix = ""
    else:
        prefix = path.rstrip("/") + "/"
    rows = db.execute(
        "SELECT path, lang, line_count FROM files WHERE path LIKE ? ORDER BY path",
        (f"{prefix}%",),
    ).fetchall()
    files = [{"path": r[0], "lang": r[1], "lines": r[2]} for r in rows]
    file_ids = [r[0] for r in db.execute("SELECT id FROM files WHERE path LIKE ?",
                                         (f"{prefix}%",)).fetchall()]
    sym_count = 0
    if file_ids:
        sym_count = db.execute(
            "SELECT COUNT(*) FROM symbols WHERE file_id IN (" +
            ",".join("?" * len(file_ids)) + ")", file_ids
        ).fetchone()[0]
    return {"path": path, "file_count": len(files), "symbol_count": sym_count, "files": files}


def cmd_refs(name: str, db_path: Path) -> list[dict]:
    db = open_db(db_path)
    rows = db.execute(
        "SELECT f.path, c.line, c.callee_name "
        "FROM calls c "
        "LEFT JOIN symbols s ON c.caller_symbol_id = s.id "
        "LEFT JOIN files f ON s.file_id = f.id "
        "WHERE c.callee_name = ? OR c.callee_name LIKE ?",
        (name, f"%.{name}"),
    ).fetchall()
    return [{"file": r[0] or "", "line": r[1], "callee_name": r[2]} for r in rows]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _db_arg(sub) -> None:
    sub.add_argument("--db", default=".github/.cache/codegraph.db")


def _json_arg(sub) -> None:
    sub.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="codegraph")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--root", default=".")
    _db_arg(p_scan)
    p_scan.add_argument("--exclude", nargs="*", default=[])
    p_scan.add_argument("--workers", type=int, default=1)

    p_upd = sub.add_parser("update")
    p_upd.add_argument("--root", default=".")
    _db_arg(p_upd)
    p_upd.add_argument("--exclude", nargs="*", default=[])

    p_find = sub.add_parser("find")
    p_find.add_argument("name")
    p_find.add_argument("--kind", default=None)
    p_find.add_argument("--lang", default=None)
    _db_arg(p_find)
    _json_arg(p_find)

    p_callees = sub.add_parser("callees")
    p_callees.add_argument("name")
    _db_arg(p_callees)
    _json_arg(p_callees)

    p_callers = sub.add_parser("callers")
    p_callers.add_argument("name")
    _db_arg(p_callers)
    _json_arg(p_callers)

    p_deps = sub.add_parser("deps")
    p_deps.add_argument("file")
    _db_arg(p_deps)
    _json_arg(p_deps)

    p_impact = sub.add_parser("impact")
    p_impact.add_argument("file")
    p_impact.add_argument("--depth", type=int, default=2)
    _db_arg(p_impact)
    _json_arg(p_impact)

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=20)
    _db_arg(p_search)
    _json_arg(p_search)

    p_env = sub.add_parser("envelope")
    p_env.add_argument("target")
    p_env.add_argument("--root", default=".")
    p_env.add_argument("--budget", type=int, default=2000)
    _db_arg(p_env)

    p_stats = sub.add_parser("stats")
    _db_arg(p_stats)
    _json_arg(p_stats)

    p_stale = sub.add_parser("why-stale")
    p_stale.add_argument("--root", default=".")
    p_stale.add_argument("--exclude", nargs="*", default=[])
    _db_arg(p_stale)
    _json_arg(p_stale)

    p_mod = sub.add_parser("module")
    p_mod.add_argument("path", nargs="?", default=".")
    _db_arg(p_mod)
    _json_arg(p_mod)

    p_refs = sub.add_parser("refs")
    p_refs.add_argument("name")
    _db_arg(p_refs)
    _json_arg(p_refs)

    args = p.parse_args(argv)

    if args.cmd == "scan":
        result = scan_into(Path(args.root), Path(args.db), args.exclude, args.workers)
        if isinstance(result, str):
            print(result)
        else:
            print(f"indexed {result} files into {args.db}")
        return 0

    if args.cmd == "update":
        n = update_into(Path(args.root), Path(args.db), args.exclude)
        print(f"updated {n} files in {args.db}")
        return 0

    if args.cmd == "find":
        rows = cmd_find(args.name, Path(args.db), args.kind, args.lang)
        if args.json:
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['file']}:{r['start_line']}  {r['kind']:<7}  "
                      f"{r['qualified_name'] or r['name']}  {r['signature']}")
        return 0 if rows else 1

    if args.cmd == "callees":
        rows = cmd_callees(args.name, Path(args.db))
        if args.json:
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['file']}:{r['line']}  {r['callee_name']}")
        return 0

    if args.cmd == "callers":
        rows = cmd_callers(args.name, Path(args.db))
        if args.json:
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['file']}:{r['line']}  {r['caller_qualified'] or r['caller_name']}")
        return 0

    if args.cmd == "deps":
        rows = cmd_deps(args.file, Path(args.db))
        if args.json:
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"L{r['line']}  {r['to_module']}  {r['imported'] or ''}  "
                      f"{('as ' + r['alias']) if r['alias'] else ''}")
        return 0

    if args.cmd == "impact":
        rows = cmd_impact(args.file, Path(args.db), args.depth)
        if args.json:
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"depth={r['depth']}  {r['path']}")
        return 0

    if args.cmd == "search":
        rows = cmd_search(args.query, Path(args.db), args.limit)
        if args.json:
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['file']}:{r['start_line']}  {r['kind']:<7}  {r['name']}")
        return 0

    if args.cmd == "envelope":
        text = cmd_envelope(args.target, Path(args.db), Path(args.root), args.budget)
        print(text, end="")
        return 0

    if args.cmd == "stats":
        data = cmd_stats(Path(args.db))
        if args.json:
            print(_json.dumps(data, indent=2))
        else:
            for k, v in data.items():
                print(f"{k}: {v}")
        return 0

    if args.cmd == "why-stale":
        data = cmd_why_stale(Path(args.root), Path(args.db), args.exclude)
        if args.json:
            print(_json.dumps(data, indent=2))
        else:
            print(f"stale={data['stale_files']}  new={data['new_files']}  "
                  f"indexed={data['total_indexed']}")
        return 0

    if args.cmd == "module":
        data = cmd_module(args.path, Path(args.db))
        if args.json:
            print(_json.dumps(data, indent=2))
        else:
            print(f"{data['path']}: {data['file_count']} files, {data['symbol_count']} symbols")
            for f in data["files"]:
                print(f"  {f['path']}  ({f['lang']}  {f['lines']} lines)")
        return 0

    if args.cmd == "refs":
        rows = cmd_refs(args.name, Path(args.db))
        if args.json:
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['file']}:{r['line']}  {r['callee_name']}")
        return 0

    p.error(f"unsupported command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
