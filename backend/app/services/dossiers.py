from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional


DB_PATH = Path(__file__).resolve().parents[3] / "database" / "actions.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dossiers (
                id TEXT PRIMARY KEY,
                customer TEXT,
                contact TEXT,
                subject TEXT,
                status TEXT,
                follow_up_date TEXT,
                source TEXT,
                external_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dossier_events (
                id TEXT PRIMARY KEY,
                dossier_id TEXT,
                event_date TEXT,
                event_type TEXT,
                notes TEXT,
                follow_up_date TEXT,
                status_change TEXT,
                created_at TEXT
            )
            """
        )


_ensure_tables()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def get_all(active_only: bool = True) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    with _get_conn() as conn:
        if active_only:
            cur = conn.execute("SELECT * FROM dossiers WHERE status != 'Afgesloten' ORDER BY updated_at DESC")
        else:
            cur = conn.execute("SELECT * FROM dossiers ORDER BY updated_at DESC")
        rows = cur.fetchall()

        for r in rows:
            d = _row_to_dict(r)
            # determine last activity: prefer the most recent event_date, otherwise use created_at's date part
            ev_cur = conn.execute("SELECT MAX(event_date) as last_event FROM dossier_events WHERE dossier_id = ?", (d.get("id"),))
            ev_row = ev_cur.fetchone()
            last_event = None
            if ev_row is not None:
                last_event = ev_row[0]

            if last_event:
                d["last_activity"] = last_event
            else:
                created = d.get("created_at") or ""
                d["last_activity"] = created.split("T")[0] if created else ""

            results.append(d)

    return results


def get_by_id(dossier_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.execute("SELECT * FROM dossiers WHERE id = ?", (dossier_id,))
        row = cur.fetchone()
        if row is None:
            return None
        dossier = _row_to_dict(row)
        ev_cur = conn.execute("SELECT * FROM dossier_events WHERE dossier_id = ? ORDER BY event_date DESC", (dossier_id,))
        events = [ _row_to_dict(e) for e in ev_cur.fetchall() ]
        dossier["events"] = events
        return dossier


def create(payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    dossier_id = str(uuid.uuid4())
    params = {
        "id": dossier_id,
        "customer": payload.get("customer", ""),
        "contact": payload.get("contact", ""),
        "subject": payload.get("subject", ""),
        "status": payload.get("status", "Lopend"),
        "follow_up_date": payload.get("follow_up_date", ""),
        "source": payload.get("source", "Dossier"),
        "external_id": payload.get("external_id"),
        "created_at": now,
        "updated_at": now,
    }
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO dossiers (id, customer, contact, subject, status, follow_up_date, source, external_id, created_at, updated_at)
            VALUES (:id, :customer, :contact, :subject, :status, :follow_up_date, :source, :external_id, :created_at, :updated_at)
            """,
            params,
        )
    return params


def update(dossier_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        cur = conn.execute("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
        if cur.fetchone() is None:
            return None
        params = {
            "id": dossier_id,
            "customer": payload.get("customer", ""),
            "contact": payload.get("contact", ""),
            "subject": payload.get("subject", ""),
            "status": payload.get("status", "Lopend"),
            "follow_up_date": payload.get("follow_up_date", ""),
            "updated_at": now,
        }
        conn.execute(
            """
            UPDATE dossiers SET
                customer = :customer,
                contact = :contact,
                subject = :subject,
                status = :status,
                follow_up_date = :follow_up_date,
                updated_at = :updated_at
            WHERE id = :id
            """,
            params,
        )
    return get_by_id(dossier_id)


def add_event(dossier_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()
    event_id = str(uuid.uuid4())
    params = {
        "id": event_id,
        "dossier_id": dossier_id,
        "event_date": payload.get("event_date", now.split("T")[0]),
        "event_type": payload.get("event_type", "Notitie"),
        "notes": payload.get("notes", ""),
        "follow_up_date": payload.get("follow_up_date"),
        "status_change": payload.get("status_change"),
        "created_at": now,
    }
    with _get_conn() as conn:
        cur = conn.execute("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
        if cur.fetchone() is None:
            return None
        conn.execute(
            """
            INSERT INTO dossier_events (id, dossier_id, event_date, event_type, notes, follow_up_date, status_change, created_at)
            VALUES (:id, :dossier_id, :event_date, :event_type, :notes, :follow_up_date, :status_change, :created_at)
            """,
            params,
        )
        # optionally update dossier follow_up_date or status
        # Build params for the update statement. SQLite requires all named
        # parameters referenced in the SQL to be present in the mapping, even
        # if their values are None. Provide keys for both follow_up_date and
        # status always, populated when present in payload or None otherwise.
        updates: Dict[str, Any] = {
            "follow_up_date": payload.get("follow_up_date"),
            "status": payload.get("status_change"),
        }

        # Only proceed if at least one of the updatable values is provided
        if updates["follow_up_date"] is not None or updates["status"] is not None:
            updates["updated_at"] = now
            updates["id"] = dossier_id
            conn.execute(
                """
                UPDATE dossiers SET
                    follow_up_date = COALESCE(:follow_up_date, follow_up_date),
                    status = COALESCE(:status, status),
                    updated_at = :updated_at
                WHERE id = :id
                """,
                updates,
            )
    return get_by_id(dossier_id)


def update_event(dossier_id: str, event_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update an existing dossier event. Only update dossier follow_up_date/status when
    the edited event explicitly supplies those values (follow_up_date, status_change).
    Returns the updated dossier or None if not found.
    """
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        # verify dossier exists
        cur = conn.execute("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
        if cur.fetchone() is None:
            return None

        # verify event exists and belongs to dossier
        cur = conn.execute("SELECT id FROM dossier_events WHERE id = ? AND dossier_id = ?", (event_id, dossier_id))
        if cur.fetchone() is None:
            return None

        # prepare update fields for the event row
        event_params = {
            "id": event_id,
            "event_date": payload.get("event_date"),
            "event_type": payload.get("event_type"),
            "notes": payload.get("notes"),
            "follow_up_date": payload.get("follow_up_date"),
        }

        # Build SET clause dynamically for only provided keys (except id)
        set_parts = []
        exec_params: Dict[str, Any] = {"id": event_id}
        for key in ("event_date", "event_type", "notes", "follow_up_date"):
            if event_params.get(key) is not None:
                set_parts.append(f"{key} = :{key}")
                exec_params[key] = event_params.get(key)

        if set_parts:
            sql = f"UPDATE dossier_events SET {', '.join(set_parts)} WHERE id = :id"
            conn.execute(sql, exec_params)

        # Optionally update dossier's follow_up_date or status only when supplied
        update_dossier_params: Dict[str, Any] = {
            "follow_up_date": payload.get("follow_up_date"),
            "status": payload.get("status_change"),
        }

        if update_dossier_params["follow_up_date"] is not None or update_dossier_params["status"] is not None:
            update_dossier_params["updated_at"] = now
            update_dossier_params["id"] = dossier_id
            conn.execute(
                """
                UPDATE dossiers SET
                    follow_up_date = COALESCE(:follow_up_date, follow_up_date),
                    status = COALESCE(:status, status),
                    updated_at = :updated_at
                WHERE id = :id
                """,
                update_dossier_params,
            )

    return get_by_id(dossier_id)


def get_for_actions() -> List[Dict[str, Any]]:
    """Return active dossiers normalized as Actions for merging into /actions feed."""
    results = []
    with _get_conn() as conn:
        cur = conn.execute("SELECT * FROM dossiers WHERE status != 'Afgesloten'")
        rows = cur.fetchall()
        for r in rows:
            d = _row_to_dict(r)
            # normalize status mapping: Lopend->Open, Wachtend->Wachtend, Afgesloten->Afgewerkt
            status_map = {
                "Lopend": "Open",
                "Wachtend": "Wachtend",
                "Afgesloten": "Afgewerkt",
            }
            normalized = {
                "id": d.get("id"),
                "title": d.get("subject", "Onbekend dossier"),
                "source": "Dossier",
                "status": status_map.get(d.get("status"), "Open"),
                "priority": "Normaal",
                "dueDate": d.get("follow_up_date") or "",
                "createdDate": d.get("created_at") or "",
                "lastModifiedDate": d.get("updated_at") or "",
                "customer": d.get("customer") or "",
                "contact": d.get("contact") or "",
                "notes": "",
                "webLink": "",
                "microsoftList": "",
            }
            results.append(normalized)
    return results


def delete(dossier_id: str) -> bool:
    """Delete a dossier and its related events. Returns True if deleted, False if not found."""
    with _get_conn() as conn:
        cur = conn.execute("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
        if cur.fetchone() is None:
            return False
        # delete events first
        conn.execute("DELETE FROM dossier_events WHERE dossier_id = ?", (dossier_id,))
        # delete dossier
        conn.execute("DELETE FROM dossiers WHERE id = ?", (dossier_id,))
    return True


def delete_event(dossier_id: str, event_id: str) -> Optional[Dict[str, Any]]:
    """Delete a single dossier event. Returns the updated dossier dict, or None if not found."""
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        # verify dossier exists
        cur = conn.execute("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
        if cur.fetchone() is None:
            return None

        # verify event exists and belongs to dossier
        cur = conn.execute("SELECT id FROM dossier_events WHERE id = ? AND dossier_id = ?", (event_id, dossier_id))
        if cur.fetchone() is None:
            return None

        # delete the event
        conn.execute("DELETE FROM dossier_events WHERE id = ?", (event_id,))

        # update dossier updated_at timestamp
        conn.execute("UPDATE dossiers SET updated_at = ? WHERE id = ?", (now, dossier_id))

    return get_by_id(dossier_id)
