from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from app.db import get_conn, is_postgresql, require_tables

_get_conn = get_conn


def _ensure_table() -> None:
    if is_postgresql():
        require_tables(("contact_sync_state",))
        return

    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contact_sync_state (
                local_contact_id TEXT PRIMARY KEY,
                outlook_contact_id TEXT,
                last_synced_at TEXT,
                synced_name TEXT,
                synced_company TEXT,
                synced_email TEXT,
                synced_phone TEXT,
                synced_mobile_phone TEXT,
                outlook_last_modified TEXT
            )
            """
        )


_ensure_table()


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def get(local_contact_id: str, *, connection: Any = None) -> Optional[Dict[str, Any]]:
    def _query(conn: Any) -> Optional[Dict[str, Any]]:
        row = conn.execute(
            "SELECT * FROM contact_sync_state WHERE local_contact_id = :local_contact_id",
            {"local_contact_id": local_contact_id},
        ).fetchone()
        return _row_to_dict(row) if row is not None else None

    if connection is not None:
        return _query(connection)
    with _get_conn() as conn:
        return _query(conn)


def get_many(local_contact_ids: Iterable[str], *, connection: Any = None) -> Dict[str, Dict[str, Any]]:
    """Fetch sync baselines for several local contacts in one query."""
    ids = [value for value in local_contact_ids if value]
    if not ids:
        return {}

    def _query(conn: Any) -> Dict[str, Dict[str, Any]]:
        params = {f"id_{index}": value for index, value in enumerate(ids)}
        placeholders = ", ".join(f":{name}" for name in params)
        rows = conn.execute(
            f"SELECT * FROM contact_sync_state WHERE local_contact_id IN ({placeholders})",
            params,
        ).fetchall()
        return {row["local_contact_id"]: _row_to_dict(row) for row in rows}

    if connection is not None:
        return _query(connection)
    with _get_conn() as conn:
        return _query(conn)


def upsert(
    local_contact_id: str,
    outlook_contact_id: str,
    synced_values: Dict[str, str],
    outlook_last_modified: Optional[str],
    *,
    connection: Any,
    synced_at: Optional[str] = None,
) -> None:
    """Persist the post-sync baseline for one linked contact.

    Requires the caller's connection so the write commits/rolls back together
    with the rest of the synchronization transaction.
    """
    params = {
        "local_contact_id": local_contact_id,
        "outlook_contact_id": outlook_contact_id,
        "last_synced_at": synced_at or datetime.utcnow().isoformat(),
        "synced_name": synced_values.get("name", ""),
        "synced_company": synced_values.get("company", ""),
        "synced_email": synced_values.get("email", ""),
        "synced_phone": synced_values.get("phone", ""),
        "synced_mobile_phone": synced_values.get("mobile_phone", ""),
        "outlook_last_modified": outlook_last_modified or "",
    }
    if get(local_contact_id, connection=connection) is None:
        connection.execute(
            """
            INSERT INTO contact_sync_state (
                local_contact_id, outlook_contact_id, last_synced_at,
                synced_name, synced_company, synced_email, synced_phone, synced_mobile_phone,
                outlook_last_modified
            ) VALUES (
                :local_contact_id, :outlook_contact_id, :last_synced_at,
                :synced_name, :synced_company, :synced_email, :synced_phone, :synced_mobile_phone,
                :outlook_last_modified
            )
            """,
            params,
        )
    else:
        connection.execute(
            """
            UPDATE contact_sync_state SET
                outlook_contact_id = :outlook_contact_id,
                last_synced_at = :last_synced_at,
                synced_name = :synced_name,
                synced_company = :synced_company,
                synced_email = :synced_email,
                synced_phone = :synced_phone,
                synced_mobile_phone = :synced_mobile_phone,
                outlook_last_modified = :outlook_last_modified
            WHERE local_contact_id = :local_contact_id
            """,
            params,
        )


def delete(local_contact_id: str, *, connection: Any) -> None:
    connection.execute(
        "DELETE FROM contact_sync_state WHERE local_contact_id = :local_contact_id",
        {"local_contact_id": local_contact_id},
    )
