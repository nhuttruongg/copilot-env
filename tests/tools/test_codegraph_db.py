import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from _lib.db import open_db, SCHEMA_VERSION, ensure_schema  # noqa: E402


def test_open_db_creates_schema(tmp_path):
    dbp = tmp_path / "g.db"
    db = open_db(dbp)
    ensure_schema(db)
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    for required in ["files", "symbols", "imports", "calls", "refs", "meta"]:
        assert required in names, f"missing table {required!r}"
    assert "symbols_fts" in names
    v = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    assert v[0] == str(SCHEMA_VERSION)


def test_open_db_idempotent(tmp_path):
    dbp = tmp_path / "g.db"
    open_db(dbp).close()
    db = open_db(dbp)
    ensure_schema(db)
