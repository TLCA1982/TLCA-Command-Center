from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional


DB_PATH = Path(__file__).resolve().parents[3] / "database" / "actions.db"
ALLOWED_RELATIONSHIP_TYPES = {"Klant", "Prospect", "Leverancier"}


class ContactPersonInUseError(ValueError):
    """Raised when a contact person is still referenced by dossier data."""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    result = {key: row[key] for key in row.keys()}
    for field in ("is_active", "is_primary"):
        if field in result:
            result[field] = bool(result[field])
    return result


def _company_payload(payload: Dict[str, Any], *, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    name = str(payload.get("name", existing.get("name", "") if existing else "") or "").strip()
    if not name:
        raise ValueError("Company name is required")

    relationship_type = payload.get(
        "relationship_type",
        existing.get("relationship_type") if existing else None,
    )
    if relationship_type == "":
        relationship_type = None
    if relationship_type is not None and relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
        raise ValueError("relationship_type must be Klant, Prospect, Leverancier, or null")

    values = {
        "name": name,
        "normalized_name": normalize(name),
        "relationship_type": relationship_type,
    }
    for field in ("street", "house_number", "postal_code", "city", "country"):
        values[field] = str(payload.get(field, existing.get(field, "") if existing else "") or "").strip()
    return values


def _get_company(connection: sqlite3.Connection, company_id: str) -> Optional[Dict[str, Any]]:
    row = connection.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    return _row_to_dict(row) if row is not None else None


def get_all() -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM companies ORDER BY name COLLATE NOCASE").fetchall()
    return [_row_to_dict(row) for row in rows]


def get_by_id(company_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        return _get_company(conn, company_id)


def create(payload: Dict[str, Any]) -> Dict[str, Any]:
    values = _company_payload(payload)
    now = datetime.utcnow().isoformat()
    company = {
        "id": str(uuid.uuid4()),
        **values,
        "created_at": now,
        "updated_at": now,
    }
    with _get_conn() as conn:
        duplicate = conn.execute(
            "SELECT id FROM companies WHERE normalized_name = ?",
            (values["normalized_name"],),
        ).fetchone()
        if duplicate is not None:
            raise ValueError("A company with the same normalized name already exists")
        conn.execute(
            """
            INSERT INTO companies (
                id, name, normalized_name, relationship_type, street, house_number,
                postal_code, city, country, created_at, updated_at
            ) VALUES (
                :id, :name, :normalized_name, :relationship_type, :street, :house_number,
                :postal_code, :city, :country, :created_at, :updated_at
            )
            """,
            company,
        )
    return company


def update(company_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        existing = _get_company(conn, company_id)
        if existing is None:
            return None
        values = _company_payload(payload, existing=existing)
        duplicate = conn.execute(
            "SELECT id FROM companies WHERE normalized_name = ? AND id != ?",
            (values["normalized_name"], company_id),
        ).fetchone()
        if duplicate is not None:
            raise ValueError("A company with the same normalized name already exists")
        values.update({"id": company_id, "updated_at": now})
        conn.execute(
            """
            UPDATE companies SET
                name = :name,
                normalized_name = :normalized_name,
                relationship_type = :relationship_type,
                street = :street,
                house_number = :house_number,
                postal_code = :postal_code,
                city = :city,
                country = :country,
                updated_at = :updated_at
            WHERE id = :id
            """,
            values,
        )
        return _get_company(conn, company_id)


def _as_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise ValueError(f"{field} must be a boolean")


def _contact_payload(payload: Dict[str, Any], *, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    name = str(payload.get("name", existing.get("name", "") if existing else "") or "").strip()
    if not name:
        raise ValueError("Contact person name is required")
    values = {"name": name, "normalized_name": normalize(name)}
    for field in ("email", "phone", "job_title"):
        values[field] = str(payload.get(field, existing.get(field, "") if existing else "") or "").strip()
    values["is_active"] = _as_bool(payload.get("is_active", existing.get("is_active", True) if existing else True), "is_active")
    values["is_primary"] = _as_bool(payload.get("is_primary", existing.get("is_primary", False) if existing else False), "is_primary")
    if not values["is_active"]:
        values["is_primary"] = False
    return values


def _get_contact(connection: sqlite3.Connection, company_id: str, contact_id: str) -> Optional[Dict[str, Any]]:
    row = connection.execute(
        "SELECT * FROM contact_persons WHERE id = ? AND company_id = ?",
        (contact_id, company_id),
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def get_contacts(company_id: str) -> Optional[List[Dict[str, Any]]]:
    with _get_conn() as conn:
        if _get_company(conn, company_id) is None:
            return None
        rows = conn.execute(
            "SELECT * FROM contact_persons WHERE company_id = ? ORDER BY name COLLATE NOCASE",
            (company_id,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def create_contact(company_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    values = _contact_payload(payload)
    now = datetime.utcnow().isoformat()
    contact = {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        **values,
        "created_at": now,
        "updated_at": now,
    }
    with _get_conn() as conn:
        if _get_company(conn, company_id) is None:
            return None
        duplicate = conn.execute(
            "SELECT id FROM contact_persons WHERE company_id = ? AND normalized_name = ?",
            (company_id, values["normalized_name"]),
        ).fetchone()
        if duplicate is not None:
            raise ValueError("A contact person with the same normalized name already exists for this company")
        if values["is_primary"]:
            conn.execute("UPDATE contact_persons SET is_primary = 0 WHERE company_id = ?", (company_id,))
        conn.execute(
            """
            INSERT INTO contact_persons (
                id, company_id, name, normalized_name, email, phone, job_title,
                is_active, is_primary, created_at, updated_at
            ) VALUES (
                :id, :company_id, :name, :normalized_name, :email, :phone, :job_title,
                :is_active, :is_primary, :created_at, :updated_at
            )
            """,
            contact,
        )
    return contact


def update_contact(company_id: str, contact_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        existing = _get_contact(conn, company_id, contact_id)
        if existing is None:
            return None
        values = _contact_payload(payload, existing=existing)
        duplicate = conn.execute(
            """
            SELECT id FROM contact_persons
            WHERE company_id = ? AND normalized_name = ? AND id != ?
            """,
            (company_id, values["normalized_name"], contact_id),
        ).fetchone()
        if duplicate is not None:
            raise ValueError("A contact person with the same normalized name already exists for this company")
        values.update({"id": contact_id, "company_id": company_id, "updated_at": now})
        if values["is_primary"]:
            conn.execute(
                "UPDATE contact_persons SET is_primary = 0 WHERE company_id = ? AND id != ?",
                (company_id, contact_id),
            )
        conn.execute(
            """
            UPDATE contact_persons SET
                name = :name,
                normalized_name = :normalized_name,
                email = :email,
                phone = :phone,
                job_title = :job_title,
                is_active = :is_active,
                is_primary = :is_primary,
                updated_at = :updated_at
            WHERE id = :id AND company_id = :company_id
            """,
            values,
        )
        return _get_contact(conn, company_id, contact_id)


def delete_contact(company_id: str, contact_id: str) -> bool:
    with _get_conn() as conn:
        contact = _get_contact(conn, company_id, contact_id)
        if contact is None:
            return False
        primary_dossier = conn.execute(
            "SELECT 1 FROM dossiers WHERE primary_contact_person_id = ? LIMIT 1",
            (contact_id,),
        ).fetchone()
        if primary_dossier is not None:
            raise ContactPersonInUseError(
                "Contact person cannot be deleted because it is the primary contact of a dossier"
            )
        dossier_event = conn.execute(
            "SELECT 1 FROM dossier_events WHERE contact_person_id = ? LIMIT 1",
            (contact_id,),
        ).fetchone()
        if dossier_event is not None:
            raise ContactPersonInUseError(
                "Contact person cannot be deleted because it is referenced by a dossier event"
            )
        conn.execute("DELETE FROM contact_persons WHERE id = ? AND company_id = ?", (contact_id, company_id))
    return True