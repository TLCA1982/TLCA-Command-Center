from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional

from app.services import companies as company_service


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


def _with_event_contact(conn: sqlite3.Connection, event: Dict[str, Any]) -> Dict[str, Any]:
    contact_id = event.get("contact_person_id")
    event["contact_person"] = None
    if contact_id is not None:
        row = conn.execute("SELECT * FROM contact_persons WHERE id = ?", (contact_id,)).fetchone()
        if row is not None:
            event["contact_person"] = _row_to_dict(row)
    return event


def _with_relationships(conn: sqlite3.Connection, dossier: Dict[str, Any]) -> Dict[str, Any]:
    company_id = dossier.get("company_id")
    contact_id = dossier.get("primary_contact_person_id")
    dossier["company"] = None
    dossier["primary_contact_person"] = None
    if company_id:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        if row is not None:
            dossier["company"] = _row_to_dict(row)
    if contact_id:
        row = conn.execute("SELECT * FROM contact_persons WHERE id = ?", (contact_id,)).fetchone()
        if row is not None:
            dossier["primary_contact_person"] = _row_to_dict(row)
    return dossier


def _resolve_relationship(
    conn: sqlite3.Connection,
    payload: Dict[str, Any],
    *,
    allow_inactive_contact_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], str, str]:
    company_id = payload.get("company_id") if "company_id" in payload else None
    contact_id = payload.get("primary_contact_person_id") if "primary_contact_person_id" in payload else None
    if company_id is not None:
        company = conn.execute("SELECT id, name FROM companies WHERE id = ?", (company_id,)).fetchone()
        if company is None:
            raise ValueError("Company not found")
        customer = company[1]
        if contact_id is not None:
            contact = conn.execute(
                                """
                                SELECT id, name FROM contact_persons
                                WHERE id = ? AND company_id = ?
                                    AND (is_active = 1 OR id = ?)
                                """,
                                (contact_id, company_id, allow_inactive_contact_id),
            ).fetchone()
            if contact is None:
                raise ValueError("Primary contact person must be active and belong to the company")
            legacy_contact = contact[1]
        else:
            legacy_contact = ""
        return company_id, contact_id, customer, legacy_contact
    if contact_id is not None:
        raise ValueError("A company is required when primary_contact_person_id is supplied")
    return None, None, payload.get("customer", ""), payload.get("contact", "")


def _validate_event_contact(
    conn: sqlite3.Connection,
    dossier_id: str,
    contact_id: Optional[str],
    *,
    active_only: bool = False,
) -> None:
    if contact_id is None:
        return
    row = conn.execute(
        """
        SELECT 1
        FROM dossiers d
        JOIN contact_persons p ON p.company_id = d.company_id
        WHERE d.id = ? AND p.id = ?
          AND (? = 0 OR p.is_active = 1)
        """,
        (dossier_id, contact_id, int(active_only)),
    ).fetchone()
    if row is None:
        if active_only:
            raise ValueError("Event contact person must be active and belong to the dossier's company")
        raise ValueError("Event contact person does not belong to the dossier's company")


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

            results.append(_with_relationships(conn, d))

    return results


def get_by_id(dossier_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.execute("SELECT * FROM dossiers WHERE id = ?", (dossier_id,))
        row = cur.fetchone()
        if row is None:
            return None
        dossier = _row_to_dict(row)
        _with_relationships(conn, dossier)
        ev_cur = conn.execute("SELECT * FROM dossier_events WHERE dossier_id = ? ORDER BY event_date DESC", (dossier_id,))
        events = [_with_event_contact(conn, _row_to_dict(e)) for e in ev_cur.fetchall()]
        dossier["events"] = events
        return dossier


def create(payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    dossier_id = str(uuid.uuid4())
    with _get_conn() as conn:
        company_id, primary_contact_id, customer, contact = _resolve_relationship(conn, payload)
    params = {
        "id": dossier_id,
        "customer": customer,
        "contact": contact,
        "subject": payload.get("subject", ""),
        "status": payload.get("status", "Lopend"),
        "follow_up_date": payload.get("follow_up_date", ""),
        "source": payload.get("source", "Dossier"),
        "external_id": payload.get("external_id"),
        "created_at": now,
        "updated_at": now,
        "company_id": company_id,
        "primary_contact_person_id": primary_contact_id,
    }
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO dossiers (
                id, customer, contact, subject, status, follow_up_date, source,
                external_id, created_at, updated_at, company_id, primary_contact_person_id
            ) VALUES (
                :id, :customer, :contact, :subject, :status, :follow_up_date, :source,
                :external_id, :created_at, :updated_at, :company_id, :primary_contact_person_id
            )
            """,
            params,
        )
    return get_by_id(dossier_id) or params


def update(dossier_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        cur = conn.execute("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
        if cur.fetchone() is None:
            return None
        existing_dossier = conn.execute(
            "SELECT primary_contact_person_id FROM dossiers WHERE id = ?",
            (dossier_id,),
        ).fetchone()
        existing_primary_id = existing_dossier[0] if existing_dossier else None
        company_id, primary_contact_id, customer, contact = _resolve_relationship(
            conn,
            payload,
            allow_inactive_contact_id=existing_primary_id,
        )
        params = {
            "id": dossier_id,
            "customer": customer,
            "contact": contact,
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
                company_id = CASE WHEN :company_id_supplied THEN :company_id ELSE company_id END,
                primary_contact_person_id = CASE WHEN :contact_id_supplied THEN :primary_contact_person_id ELSE primary_contact_person_id END,
                subject = :subject,
                status = :status,
                follow_up_date = :follow_up_date,
                updated_at = :updated_at
            WHERE id = :id
            """,
            {
                **params,
                "company_id": company_id,
                "primary_contact_person_id": primary_contact_id,
                "company_id_supplied": int("company_id" in payload),
                "contact_id_supplied": int("primary_contact_person_id" in payload),
            },
        )
    return get_by_id(dossier_id)


def add_event(dossier_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()
    event_id = str(uuid.uuid4())
    contact_person_id = payload.get("contact_person_id")
    if contact_person_id is not None and str(contact_person_id).strip() == "":
        contact_person_id = None
    params = {
        "id": event_id,
        "dossier_id": dossier_id,
        "event_date": payload.get("event_date", now.split("T")[0]),
        "event_type": payload.get("event_type", "Notitie"),
        "notes": payload.get("notes", ""),
        "follow_up_date": payload.get("follow_up_date"),
        "status_change": payload.get("status_change"),
        "contact_person_id": contact_person_id,
        "created_at": now,
    }
    with _get_conn() as conn:
        cur = conn.execute("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
        if cur.fetchone() is None:
            return None
        _validate_event_contact(conn, dossier_id, params["contact_person_id"], active_only=True)
        conn.execute(
            """
            INSERT INTO dossier_events (
                id, dossier_id, event_date, event_type, notes, follow_up_date,
                status_change, contact_person_id, created_at
            ) VALUES (
                :id, :dossier_id, :event_date, :event_type, :notes, :follow_up_date,
                :status_change, :contact_person_id, :created_at
            )
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
            "contact_person_id": payload.get("contact_person_id"),
        }
        if event_params["contact_person_id"] is not None and str(event_params["contact_person_id"]).strip() == "":
            event_params["contact_person_id"] = None

        # Build SET clause dynamically for only provided keys (except id)
        set_parts = []
        exec_params: Dict[str, Any] = {"id": event_id}
        _validate_event_contact(conn, dossier_id, event_params["contact_person_id"])
        for key in ("event_date", "event_type", "notes", "follow_up_date", "contact_person_id"):
            if key not in payload:
                continue
            value = event_params.get(key)
            if value is None:
                set_parts.append(f"{key} = NULL")
            else:
                set_parts.append(f"{key} = :{key}")
                exec_params[key] = value

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
