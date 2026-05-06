"""SQLite schema + connection helper for codegraph."""
from __future__ import annotations
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT UNIQUE NOT NULL,
    lang        TEXT,
    sha256      TEXT,
    mtime       REAL,
    line_count  INTEGER,
    parse_error INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);

CREATE TABLE IF NOT EXISTS symbols (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id         INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    qualified_name  TEXT,
    kind            TEXT NOT NULL,
    start_line      INTEGER,
    end_line        INTEGER,
    signature       TEXT,
    docstring       TEXT,
    visibility      TEXT
);
CREATE INDEX IF NOT EXISTS idx_symbols_name      ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file      ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_qualname  ON symbols(qualified_name);

CREATE TABLE IF NOT EXISTS imports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    from_file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    to_module    TEXT NOT NULL,
    imported     TEXT,
    alias        TEXT,
    line         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_imports_to ON imports(to_module);

CREATE TABLE IF NOT EXISTS calls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_symbol_id  INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    callee_name       TEXT NOT NULL,
    callee_symbol_id  INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
    line              INTEGER
);
CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_name);
CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_symbol_id);

CREATE TABLE IF NOT EXISTS refs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id  INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    line       INTEGER,
    kind       TEXT
);
CREATE INDEX IF NOT EXISTS idx_refs_symbol ON refs(symbol_id);

CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name, qualified_name, signature, docstring,
    content='symbols', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, qualified_name, signature, docstring)
    VALUES (new.id, new.name, new.qualified_name, new.signature, new.docstring);
END;
CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, qualified_name, signature, docstring)
    VALUES('delete', old.id, old.name, old.qualified_name, old.signature, old.docstring);
END;
"""


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA_SQL)
    db.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    db.commit()
