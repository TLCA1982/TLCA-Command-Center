from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional

from app.services.microsoft_graph import MicrosoftGraphClient

from app.services.microsoft_graph import MicrosoftGraphClient


DB_PATH = Path(__file__).resolve().parents[3] / "database" / "actions.db"
ALLOWED_RELATIONSHIP_TYPES = {"Klant", "Prospect", "Leverancier"}


class ContactPersonInUseError(ValueError):
    """Raised when a contact person is still referenced by dossier data."""


class OutlookContactCreationError(ValueError):
    def __init__(self, contact: Dict[str, Any], reason: str) -> None:
        super().__init__(reason)
        self.contact = contact


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def normalize_phone(value: str | None) -> str:
    return "".join(character for character in (value or "") if character.isdigit())


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


def _has_outlook_contact_id(connection: sqlite3.Connection) -> bool:
    return "outlook_contact_id" in {row[1] for row in connection.execute("PRAGMA table_info(contact_persons)")}


def _has_outlook_contact_id(connection: sqlite3.Connection) -> bool:
    return "outlook_contact_id" in {row[1] for row in connection.execute("PRAGMA table_info(contact_persons)")}


def reconcile_outlook_contacts(outlook_contacts: list[Dict[str, Any]]) -> Dict[str, Any]:
    with _get_conn() as conn:
        if not _has_outlook_contact_id(conn):
            raise ValueError("Outlook contact reconciliation requires the pending contact Outlook ID migration")
        local_rows = conn.execute(
            """
            SELECT p.*, c.name AS company_name
            FROM contact_persons p
            JOIN companies c ON c.id = p.company_id
            WHERE p.outlook_contact_id IS NULL
            """
        ).fetchall()
        local = [_row_to_dict(row) | {"company_name": row["company_name"]} for row in local_rows]
        linked: list[Dict[str, Any]] = []
        ambiguous: list[Dict[str, Any]] = []
        unmatched: list[Dict[str, Any]] = []

        def candidates_for(predicate: Any) -> list[Dict[str, Any]]:
            return [contact for contact in local if contact["outlook_contact_id"] is None and predicate(contact)]

        for outlook in outlook_contacts:
            outlook_id = outlook.get("id")
            if not outlook_id:
                continue
            emails = [normalize(item.get("address")) for item in outlook.get("emailAddresses", []) if normalize(item.get("address"))]
            phones = [normalize_phone(phone) for phone in outlook.get("businessPhones", []) if normalize_phone(phone)]
            name = normalize(outlook.get("displayName") or " ".join(filter(None, [outlook.get("givenName"), outlook.get("surname")])) )
            company = normalize(outlook.get("companyName"))
            matches: list[Dict[str, Any]] = []
            signal = ""
            for email in emails:
                matches = candidates_for(lambda contact, email=email: normalize(contact.get("email")) == email)
                if matches:
                    signal = "email"
                    break
            if not matches:
                for phone in phones:
                    matches = candidates_for(lambda contact, phone=phone: normalize_phone(contact.get("phone")) == phone)
                    if matches:
                        signal = "phone"
                        break
            if not matches and name and company:
                matches = candidates_for(lambda contact: normalize(contact.get("name")) == name and normalize(contact.get("company_name")) == company)
                if len(matches) == 1:
                    signal = "name_company"
            if len(matches) == 1:
                contact = matches[0]
                conn.execute("UPDATE contact_persons SET outlook_contact_id = ? WHERE id = ?", (outlook_id, contact["id"]))
                contact["outlook_contact_id"] = outlook_id
                linked.append({"contact_person_id": contact["id"], "outlook_contact_id": outlook_id, "signal": signal})
            elif len(matches) > 1:
                ambiguous.append({"outlook_contact_id": outlook_id, "display_name": outlook.get("displayName", ""), "reason": f"multiple {signal or 'name/company'} matches"})
            else:
                unmatched.append({"outlook_contact_id": outlook_id, "display_name": outlook.get("displayName", "")})
        return {"linked": linked, "ambiguous": ambiguous, "unmatched": unmatched}


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
    add_to_outlook = bool(payload.get("add_to_outlook", False))
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
        has_outlook_id = _has_outlook_contact_id(conn)
        if add_to_outlook and not has_outlook_id:
            raise ValueError("Outlook contact creation requires the pending contact Outlook ID migration")
        columns = "id, company_id, name, normalized_name, email, phone, job_title, is_active, is_primary, created_at, updated_at"
        placeholders = ":id, :company_id, :name, :normalized_name, :email, :phone, :job_title, :is_active, :is_primary, :created_at, :updated_at"
        if has_outlook_id:
            columns += ", outlook_contact_id"
            placeholders += ", :outlook_contact_id"
            contact["outlook_contact_id"] = None
        conn.execute(f"INSERT INTO contact_persons ({columns}) VALUES ({placeholders})", contact)
        saved_contact = _get_contact(conn, company_id, contact["id"]) or contact
        if not add_to_outlook:
            return saved_contact

        company = _get_company(conn, company_id)
        conn.commit()
        name_parts = saved_contact["name"].split(None, 1)
        outlook_payload = {
            "displayName": saved_contact["name"],
            "givenName": name_parts[0],
            "surname": name_parts[1] if len(name_parts) > 1 else "",
            "companyName": company["name"] if company else "",
            "jobTitle": saved_contact["job_title"],
            "emailAddresses": ([{"address": saved_contact["email"]}] if saved_contact["email"] else []),
            "businessPhones": ([saved_contact["phone"]] if saved_contact["phone"] else []),
        }
        try:
            outlook_contact = MicrosoftGraphClient().create_contact(outlook_payload)
            outlook_id = outlook_contact.get("id")
            if not outlook_id:
                raise ValueError("Microsoft Graph returned no Outlook contact ID")
            conn.execute("UPDATE contact_persons SET outlook_contact_id = ? WHERE id = ?", (outlook_id, contact["id"]))
            conn.commit()
            return _get_contact(conn, company_id, contact["id"]) or saved_contact
        except Exception as exc:
            raise OutlookContactCreationError(
                saved_contact,
                f"Local contact '{saved_contact['name']}' was saved, but Outlook contact creation failed: {exc}",
            ) from exc


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
        dossier_event = conn.execute(
            "SELECT 1 FROM dossier_events WHERE contact_person_id = ? LIMIT 1",
            (contact_id,),
        ).fetchone()
        if dossier_event is not None:
            raise ContactPersonInUseError(
                "Contact person cannot be deleted because it is used in contact-moment history"
            )
        conn.execute(
            "UPDATE dossiers SET primary_contact_person_id = NULL WHERE primary_contact_person_id = ?",
            (contact_id,),
        )
        conn.execute("DELETE FROM contact_persons WHERE id = ? AND company_id = ?", (contact_id, company_id))
    return True