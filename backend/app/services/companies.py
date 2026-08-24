from __future__ import annotations

import sqlite3
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional

from app.config import get_settings
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


def get_linked_outlook_ids() -> List[str]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT outlook_contact_id FROM contact_persons WHERE outlook_contact_id IS NOT NULL"
        ).fetchall()
    return [row[0] for row in rows]


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


def preview_outlook_reconciliation(outlook_contacts: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Classify category-filtered Outlook contacts without changing local data."""
    with _get_conn() as conn:
        local_rows = conn.execute(
            """
            SELECT p.id, p.name, p.email, p.phone, p.outlook_contact_id, c.name AS company_name
            FROM contact_persons p
            JOIN companies c ON c.id = p.company_id
            ORDER BY p.name COLLATE NOCASE
            """
        ).fetchall()

    local = [{key: row[key] for key in row.keys()} for row in local_rows]
    linked_ids = {contact["outlook_contact_id"] for contact in local if contact["outlook_contact_id"]}
    outlook_by_id = {contact["id"]: contact for contact in outlook_contacts if contact.get("id")}
    already_linked = [
        {"local_contact_id": contact["id"], "outlook_contact_id": contact["outlook_contact_id"], "reason": "existing outlook_contact_id link"}
        for contact in local if contact["outlook_contact_id"]
    ]
    available_local = [contact for contact in local if not contact["outlook_contact_id"]]
    available_outlook = [contact for contact in outlook_contacts if contact.get("id") not in linked_ids]
    matched_local_ids: set[str] = set()
    matched_outlook_ids: set[str] = set()
    exact_match: list[Dict[str, Any]] = []
    ambiguous: list[Dict[str, Any]] = []

    def emails(contact: Dict[str, Any]) -> set[str]:
        return {normalize(item.get("address")) for item in contact.get("emailAddresses", []) if normalize(item.get("address"))}

    def phone(contact: Dict[str, Any]) -> str:
        return normalize_phone(contact.get("phone"))

    def outlook_email(contact: Dict[str, Any]) -> str:
        return next(iter(emails(contact)), "")

    for outlook in available_outlook:
        outlook_id = outlook["id"]
        outlook_emails = emails(outlook)
        outlook_phone = normalize_phone(next(iter(outlook.get("businessPhones", [])), ""))
        outlook_name = normalize(
            outlook.get("displayName")
            or " ".join(filter(None, [outlook.get("givenName"), outlook.get("surname")]))
        )
        outlook_company = normalize(outlook.get("companyName"))
        email_matches = [contact for contact in available_local if contact["id"] not in matched_local_ids and normalize(contact.get("email")) in outlook_emails]
        phone_matches = [contact for contact in available_local if contact["id"] not in matched_local_ids and outlook_phone and phone(contact) == outlook_phone]
        name_company_matches = [
            contact for contact in available_local
            if contact["id"] not in matched_local_ids
            and outlook_name
            and outlook_company
            and normalize(contact.get("name")) == outlook_name
            and normalize(contact.get("company_name")) == outlook_company
        ]
        if len(email_matches) > 1 or len(phone_matches) > 1 or len(name_company_matches) > 1:
            ambiguous.append({"outlook_contact_id": outlook_id, "outlook_name": outlook.get("displayName", ""), "reason": "multiple possible matches"})
            continue
        strong_matches = email_matches or phone_matches
        if email_matches and phone_matches and email_matches[0]["id"] != phone_matches[0]["id"]:
            ambiguous.append({"outlook_contact_id": outlook_id, "outlook_name": outlook.get("displayName", ""), "reason": "email and phone identify different local contacts"})
            continue
        if strong_matches:
            local_contact = strong_matches[0]
            reason = "exact normalized email" if email_matches else "exact normalized phone"
        elif len(name_company_matches) == 1:
            local_contact = name_company_matches[0]
            reason = "exact normalized name and company"
        else:
            continue
        matched_local_ids.add(local_contact["id"])
        matched_outlook_ids.add(outlook_id)
        exact_match.append({
            "local_contact_id": local_contact["id"],
            "local_name": local_contact["name"],
            "local_email": local_contact["email"],
            "local_company": local_contact["company_name"],
            "outlook_contact_id": outlook_id,
            "outlook_name": outlook.get("displayName", ""),
            "outlook_email": outlook_email(outlook),
            "outlook_company": outlook.get("companyName", ""),
            "outlook_categories": outlook.get("categories", []),
            "match_reason": reason,
        })

    unmatched_local = [
        {"local_contact_id": contact["id"], "local_name": contact["name"], "reason": "no safe Outlook match"}
        for contact in available_local if contact["id"] not in matched_local_ids
    ]
    unmatched_outlook = [
        {"outlook_contact_id": contact["id"], "outlook_name": contact.get("displayName", ""), "reason": "no safe local match"}
        for contact in available_outlook if contact["id"] not in matched_outlook_ids and not any(item["outlook_contact_id"] == contact["id"] for item in ambiguous)
    ]
    return {
        "exact_match": exact_match,
        "already_linked": already_linked,
        "unmatched_local": unmatched_local,
        "unmatched_outlook": unmatched_outlook,
        "ambiguous": ambiguous,
    }


def preview_outlook_candidates(outlook_contacts: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Suggest conservative Outlook candidates for unlinked local contacts without writes."""
    allowed_categories = {
        category.casefold()
        for category in get_settings().outlook_business_category_list
    }
    outlook_contacts = [
        contact for contact in outlook_contacts
        if {
            category.casefold()
            for category in contact.get("categories", [])
            if isinstance(category, str)
        }.intersection(allowed_categories)
    ]
    with _get_conn() as conn:
        local_rows = conn.execute(
            """
            SELECT p.id, p.name, p.email, p.phone, p.outlook_contact_id, c.name AS company_name
            FROM contact_persons p
            JOIN companies c ON c.id = p.company_id
            WHERE p.outlook_contact_id IS NULL
            ORDER BY p.name COLLATE NOCASE
            """
        ).fetchall()
        linked_outlook_ids = {
            row[0] for row in conn.execute(
                "SELECT outlook_contact_id FROM contact_persons WHERE outlook_contact_id IS NOT NULL"
            )
        }

    local_contacts = [{key: row[key] for key in row.keys()} for row in local_rows]
    available_outlook = [
        contact for contact in outlook_contacts
        if contact.get("id") and contact.get("id") not in linked_outlook_ids
    ]

    def outlook_name(contact: Dict[str, Any]) -> str:
        return normalize(contact.get("displayName") or " ".join(filter(None, [contact.get("givenName"), contact.get("surname")])) )

    def outlook_email_values(contact: Dict[str, Any]) -> set[str]:
        return {
            normalize(item.get("address"))
            for item in contact.get("emailAddresses", [])
            if normalize(item.get("address"))
        }

    def outlook_phone_values(contact: Dict[str, Any]) -> set[str]:
        return {
            normalize_phone(value)
            for value in contact.get("businessPhones", [])
            if normalize_phone(value)
        }

    def email_domain(value: str) -> str:
        return value.rsplit("@", 1)[1] if "@" in value else ""

    def candidate_fields(local: Dict[str, Any], outlook: Dict[str, Any], signals: list[str], score: int) -> Dict[str, Any]:
        return {
            "local_contact_id": local["id"],
            "local_name": local["name"],
            "local_email": local["email"],
            "local_phone": local["phone"],
            "local_company": local["company_name"],
            "outlook_contact_id": outlook["id"],
            "outlook_name": outlook.get("displayName", ""),
            "outlook_email": next(iter(outlook_email_values(outlook)), ""),
            "outlook_phone": next(iter(outlook_phone_values(outlook)), ""),
            "outlook_company": outlook.get("companyName", ""),
            "outlook_categories": outlook.get("categories", []),
            "match_signals": signals,
            "confidence_score": score,
        }

    strong: list[Dict[str, Any]] = []
    possible: list[Dict[str, Any]] = []
    ambiguous: list[Dict[str, Any]] = []
    no_candidate: list[Dict[str, Any]] = []
    assigned_outlook: dict[str, list[str]] = {}

    for local in local_contacts:
        local_email = normalize(local.get("email"))
        local_phone = normalize_phone(local.get("phone"))
        local_name = normalize(local.get("name"))
        local_company = normalize(local.get("company_name"))
        candidates: list[Dict[str, Any]] = []
        for outlook in available_outlook:
            outlook_emails = outlook_email_values(outlook)
            outlook_phones = outlook_phone_values(outlook)
            name = outlook_name(outlook)
            company = normalize(outlook.get("companyName"))
            signals: list[str] = []
            if local_email and local_email in outlook_emails:
                signals.append("exact normalized email")
            if local_phone and local_phone in outlook_phones:
                signals.append("exact normalized phone")
            if local_name and local_name == name:
                signals.append("exact normalized name")
            if local_name and local_company and local_name == name and local_company == company:
                signals.extend(["exact normalized company", "exact name + company"])
            if local_email and email_domain(local_email) and email_domain(local_email) in {email_domain(value) for value in outlook_emails} and local_company and local_company == company:
                signals.append("email domain + company")
            name_similarity = SequenceMatcher(None, local_name, name).ratio() if local_name and name else 0
            company_similarity = SequenceMatcher(None, local_company, company).ratio() if local_company and company else 0
            if name_similarity >= 0.82 and local_name != name:
                signals.append("similar name formatting/spelling")
            if company_similarity >= 0.82 and local_company != company and name_similarity >= 0.82:
                signals.append("similar company formatting/spelling")
            if signals:
                score = 0
                if "exact normalized email" in signals:
                    score += 100
                if "exact normalized phone" in signals:
                    score += 70
                if "exact normalized name" in signals:
                    score += 35
                if "exact normalized company" in signals:
                    score += 25
                if "exact name + company" in signals:
                    score += 20
                if "email domain + company" in signals:
                    score += 15
                score += int(max(name_similarity, company_similarity) * 10)
                candidates.append(candidate_fields(local, outlook, signals, score))

        email_candidates = [item for item in candidates if "exact normalized email" in item["match_signals"]]
        phone_candidates = [item for item in candidates if "exact normalized phone" in item["match_signals"]]
        if email_candidates and phone_candidates and {item["outlook_contact_id"] for item in email_candidates} != {item["outlook_contact_id"] for item in phone_candidates}:
            ambiguous.append({"local_contact_id": local["id"], "local_name": local["name"], "reason": "email and phone identify conflicting Outlook contacts", "candidates": sorted(candidates, key=lambda item: item["confidence_score"], reverse=True)[:5]})
            continue
        strong_candidates = email_candidates if email_candidates else [
            item for item in phone_candidates
            if "exact normalized name" in item["match_signals"] or "exact normalized company" in item["match_signals"]
        ]
        if len(strong_candidates) == 1:
            selected = strong_candidates[0]
            selected.pop("confidence_score", None)
            strong.append(selected)
            assigned_outlook.setdefault(selected["outlook_contact_id"], []).append(local["id"])
        elif len(strong_candidates) > 1 or (not strong_candidates and len(candidates) > 1 and candidates[0]["confidence_score"] - candidates[1]["confidence_score"] < 15):
            ambiguous.append({"local_contact_id": local["id"], "local_name": local["name"], "reason": "multiple plausible Outlook candidates", "candidates": sorted(candidates, key=lambda item: item["confidence_score"], reverse=True)[:5]})
        elif candidates:
            ranked = sorted(candidates, key=lambda item: item["confidence_score"], reverse=True)[:5]
            for item in ranked:
                item.pop("confidence_score", None)
            possible.append({"local_contact_id": local["id"], "local_name": local["name"], "candidates": ranked, "reason": "plausible candidate requires manual review"})
        else:
            no_candidate.append({"local_contact_id": local["id"], "local_name": local["name"], "reason": "no plausible Outlook candidate"})

    collision_ids = {outlook_id for outlook_id, local_ids in assigned_outlook.items() if len(local_ids) > 1}
    if collision_ids:
        moved = [item for item in strong if item["outlook_contact_id"] in collision_ids]
        strong = [item for item in strong if item["outlook_contact_id"] not in collision_ids]
        ambiguous.extend({"local_contact_id": item["local_contact_id"], "local_name": item["local_name"], "reason": "one Outlook contact matches multiple local contacts", "candidates": [item]} for item in moved)

    classified_ids = ({item["local_contact_id"] for item in strong} | {item["local_contact_id"] for item in possible} | {item["local_contact_id"] for item in ambiguous} | {item["local_contact_id"] for item in no_candidate})
    no_candidate.extend(
        {"local_contact_id": local["id"], "local_name": local["name"], "reason": "no candidate found"}
        for local in local_contacts if local["id"] not in classified_ids
    )
    return {"strong_candidate": strong, "possible_candidate": possible, "ambiguous": ambiguous, "no_candidate": no_candidate}


def compare_linked_outlook_contacts(outlook_contacts: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare locally linked contacts with exact Outlook records without writes."""
    allowed_categories = {category.casefold() for category in get_settings().outlook_business_category_list}
    outlook_by_id = {contact.get("id"): contact for contact in outlook_contacts if contact.get("id")}
    with _get_conn() as conn:
        local_rows = conn.execute(
            """
            SELECT p.id, p.outlook_contact_id, p.name, p.email, p.phone, c.name AS company_name
            FROM contact_persons p
            JOIN companies c ON c.id = p.company_id
            WHERE p.outlook_contact_id IS NOT NULL
            ORDER BY p.name COLLATE NOCASE
            """
        ).fetchall()

    def outlook_name(contact: Dict[str, Any]) -> str:
        return contact.get("displayName") or " ".join(filter(None, [contact.get("givenName"), contact.get("surname")]))

    def outlook_email(contact: Dict[str, Any]) -> str:
        return next((item.get("address", "") for item in contact.get("emailAddresses", []) if item.get("address")), "")

    def outlook_phone(contact: Dict[str, Any]) -> str:
        return next((value for value in contact.get("businessPhones", []) if value), "")

    comparisons: list[Dict[str, Any]] = []
    summary = {
        "total_linked": len(local_rows),
        "linked_ok": 0,
        "identical": 0,
        "different": 0,
        "outlook_contact_missing": 0,
        "category_no_longer_allowed": 0,
        "name_differences": 0,
        "company_differences": 0,
        "email_differences": 0,
        "phone_differences": 0,
    }
    for row in local_rows:
        local = {key: row[key] for key in row.keys()}
        outlook = outlook_by_id.get(row["outlook_contact_id"])
        if outlook is None:
            summary["outlook_contact_missing"] += 1
            comparisons.append({
                "local_contact_id": row["id"],
                "outlook_contact_id": row["outlook_contact_id"],
                "local_name": row["name"],
                "local_company": row["company_name"],
                "local_email": row["email"],
                "local_phone": row["phone"],
                "outlook_name": None,
                "outlook_company": None,
                "outlook_email": None,
                "outlook_phone": None,
                "outlook_categories": [],
                "differences": ["outlook_contact"],
                "status": "outlook_contact_missing",
            })
            continue
        categories = [category for category in outlook.get("categories", []) if isinstance(category, str)]
        if not {category.casefold() for category in categories}.intersection(allowed_categories):
            summary["category_no_longer_allowed"] += 1
            status = "category_no_longer_allowed"
        else:
            status = "linked_ok"
            summary["linked_ok"] += 1
        values = {
            "name": (row["name"], outlook_name(outlook)),
            "company": (row["company_name"], outlook.get("companyName", "")),
            "email": (row["email"], outlook_email(outlook)),
            "phone": (row["phone"], outlook_phone(outlook)),
        }
        differences = [
            field
            for field, (local_value, outlook_value) in values.items()
            if field != "phone" and normalize(local_value) != normalize(outlook_value)
        ]
        if normalize_phone(values["phone"][0]) != normalize_phone(values["phone"][1]):
            differences.append("phone")
        if status == "linked_ok":
            if differences:
                summary["different"] += 1
            else:
                summary["identical"] += 1
            for field in differences:
                summary[f"{field}_differences"] += 1
        comparisons.append({
            "local_contact_id": row["id"],
            "outlook_contact_id": row["outlook_contact_id"],
            "local_name": row["name"],
            "outlook_name": values["name"][1],
            "local_company": row["company_name"],
            "outlook_company": values["company"][1],
            "local_email": row["email"],
            "outlook_email": values["email"][1],
            "local_phone": row["phone"],
            "outlook_phone": values["phone"][1],
            "outlook_categories": categories,
            "differences": differences,
            "status": status,
        })
    return {"summary": summary, "contacts": comparisons}


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