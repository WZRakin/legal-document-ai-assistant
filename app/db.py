from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "portal.sqlite3"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            status TEXT NOT NULL,
            extracted_text TEXT,
            extracted_json TEXT,
            draft TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_id TEXT NOT NULL,
            page INTEGER NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS edit_learning (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            original_draft TEXT NOT NULL,
            edited_draft TEXT NOT NULL,
            learned_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
        """)


def create_document(filename: str, path: str) -> int:
    with conn() as c:
        cur = c.execute("INSERT INTO documents(filename, path, status) VALUES (?, ?, ?)", (filename, path, "uploaded"))
        return int(cur.lastrowid)


def update_document(document_id: int, **fields: Any) -> None:
    if not fields:
        return
    keys = list(fields.keys())
    values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in fields.values()]
    sql = f"UPDATE documents SET {', '.join([k + '=?' for k in keys])} WHERE id=?"
    with conn() as c:
        c.execute(sql, values + [document_id])


def insert_chunks(document_id: int, chunks: List[dict]) -> None:
    with conn() as c:
        c.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
        c.executemany(
            "INSERT INTO chunks(document_id, chunk_id, page, text) VALUES (?, ?, ?, ?)",
            [(document_id, ch["chunk_id"], ch["page"], ch["text"]) for ch in chunks],
        )


def get_document(document_id: int) -> Dict[str, Any] | None:
    with conn() as c:
        row = c.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    for key in ["extracted_json"]:
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                pass
    return d


def list_documents() -> List[Dict[str, Any]]:
    with conn() as c:
        rows = c.execute("SELECT id, filename, status, created_at FROM documents ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def get_chunks(document_id: int) -> List[Dict[str, Any]]:
    with conn() as c:
        rows = c.execute("SELECT chunk_id, page, text FROM chunks WHERE document_id=? ORDER BY id ASC", (document_id,)).fetchall()
    return [dict(r) for r in rows]


def save_edit_learning(document_id: int, original: str, edited: str, learned: Dict[str, Any]) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO edit_learning(document_id, original_draft, edited_draft, learned_json) VALUES (?, ?, ?, ?)",
            (document_id, original, edited, json.dumps(learned, indent=2)),
        )


def latest_learning_rules(limit: int = 5) -> List[Dict[str, Any]]:
    with conn() as c:
        rows = c.execute("SELECT learned_json, created_at FROM edit_learning ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        try:
            out.append({"created_at": r["created_at"], "learned": json.loads(r["learned_json"])})
        except Exception:
            out.append(dict(r))
    return out
