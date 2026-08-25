from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import uuid
from typing import Any, Dict, List

from app.db import get_conn

_get_conn = get_conn


def _ensure_table() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS manual_actions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                customer TEXT,
                contact TEXT,
                type TEXT,
                priority TEXT,
                dueDate TEXT,
                status TEXT,
                notes TEXT,
                createdDate TEXT,
                lastModifiedDate TEXT,
                source TEXT,
                adsolutCustomerId TEXT,
                visitReportId TEXT,
                communicatorId TEXT,
                quotationId TEXT
            )
            """
        )


_ensure_table()


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def get_all() -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.execute('SELECT * FROM manual_actions ORDER BY "lastModifiedDate" DESC')
        rows = cur.fetchall()
    return [_row_to_dict(r) for r in rows]


def create(action: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    action_id = str(uuid.uuid4())
    params = {
        "id": action_id,
        "title": action.get("title", ""),
        "customer": action.get("customer", ""),
        "contact": action.get("contact", ""),
        "type": action.get("type", ""),
        "priority": action.get("priority", "Normaal"),
        "dueDate": action.get("dueDate", ""),
        "status": action.get("status", "Open"),
        "notes": action.get("notes", ""),
        "createdDate": now,
        "lastModifiedDate": now,
        "source": "Command Center",
        "adsolutCustomerId": action.get("adsolutCustomerId"),
        "visitReportId": action.get("visitReportId"),
        "communicatorId": action.get("communicatorId"),
        "quotationId": action.get("quotationId"),
    }

    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO manual_actions (
                id, title, customer, contact, type, priority, "dueDate", status, notes,
                "createdDate", "lastModifiedDate", source, "adsolutCustomerId", "visitReportId", "communicatorId", "quotationId"
            ) VALUES (
                :id, :title, :customer, :contact, :type, :priority, :dueDate, :status, :notes,
                :createdDate, :lastModifiedDate, :source, :adsolutCustomerId, :visitReportId, :communicatorId, :quotationId
            )
            """,
            params,
        )

    return {**params}


def update(action_id: str, action: Dict[str, Any]) -> Dict[str, Any] | None:
    now = datetime.utcnow().isoformat()
    params = {
        "id": action_id,
        "title": action.get("title", ""),
        "customer": action.get("customer", ""),
        "contact": action.get("contact", ""),
        "type": action.get("type", ""),
        "priority": action.get("priority", "Normaal"),
        "dueDate": action.get("dueDate", ""),
        "status": action.get("status", "Open"),
        "notes": action.get("notes", ""),
        "lastModifiedDate": now,
        "adsolutCustomerId": action.get("adsolutCustomerId"),
        "visitReportId": action.get("visitReportId"),
        "communicatorId": action.get("communicatorId"),
        "quotationId": action.get("quotationId"),
    }

    with _get_conn() as conn:
        cur = conn.execute("SELECT id FROM manual_actions WHERE id = :id", {"id": action_id})
        if cur.fetchone() is None:
            return None

        conn.execute(
            """
            UPDATE manual_actions SET
                title = :title,
                customer = :customer,
                contact = :contact,
                type = :type,
                priority = :priority,
                "dueDate" = :dueDate,
                status = :status,
                notes = :notes,
                "lastModifiedDate" = :lastModifiedDate,
                "adsolutCustomerId" = :adsolutCustomerId,
                "visitReportId" = :visitReportId,
                "communicatorId" = :communicatorId,
                "quotationId" = :quotationId
            WHERE id = :id
            """,
            params,
        )

    # return merged record
    with _get_conn() as conn:
        cur = conn.execute("SELECT * FROM manual_actions WHERE id = :id", {"id": action_id})
        row = cur.fetchone()
        return _row_to_dict(row) if row is not None else None


def delete(action_id: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM manual_actions WHERE id = :id", {"id": action_id})
        return cur.rowcount > 0
