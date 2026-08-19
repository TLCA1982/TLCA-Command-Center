from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DB_PATH = Path(__file__).resolve().parents[3] / "database" / "actions.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS microsoft_metadata (
                ms_id TEXT PRIMARY KEY,
                source TEXT,
                customer TEXT,
                contact TEXT,
                action_type TEXT,
                lastModifiedDate TEXT
            )
            """
        )


_ensure_table()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def get(ms_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.execute("SELECT * FROM microsoft_metadata WHERE ms_id = ?", (ms_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row is not None else None


def upsert(ms_id: str, source: str | None = None, customer: str | None = None, contact: str | None = None, action_type: str | None = None, last_modified: str | None = None) -> Dict[str, Any]:
    now = last_modified or datetime.utcnow().isoformat()
    existing = get(ms_id)
    params = {
        "ms_id": ms_id,
        "source": source or (existing.get("source") if existing else "Microsoft To Do"),
        "customer": customer if customer is not None else (existing.get("customer") if existing else ""),
        "contact": contact if contact is not None else (existing.get("contact") if existing else ""),
        "action_type": action_type if action_type is not None else (existing.get("action_type") if existing else ""),
        "lastModifiedDate": now,
    }

    with _get_conn() as conn:
        if existing is None:
            conn.execute(
                """
                INSERT INTO microsoft_metadata (ms_id, source, customer, contact, action_type, lastModifiedDate)
                VALUES (:ms_id, :source, :customer, :contact, :action_type, :lastModifiedDate)
                """,
                params,
            )
        else:
            conn.execute(
                """
                UPDATE microsoft_metadata SET
                    source = :source,
                    customer = :customer,
                    contact = :contact,
                    action_type = :action_type,
                    lastModifiedDate = :lastModifiedDate
                WHERE ms_id = :ms_id
                """,
                params,
            )

    return params


def get_all() -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.execute("SELECT * FROM microsoft_metadata ORDER BY lastModifiedDate DESC")
        rows = cur.fetchall()
    return [_row_to_dict(r) for r in rows]
