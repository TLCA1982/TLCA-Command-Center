from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


MIGRATION_VERSION = "001_company_contact_structure"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = REPO_ROOT / "database" / "actions.db"
ORIGINAL_COLUMNS = {
    "dossiers": (
        "id",
        "customer",
        "contact",
        "subject",
        "status",
        "follow_up_date",
        "source",
        "external_id",
        "created_at",
        "updated_at",
    ),
    "dossier_events": (
        "id",
        "dossier_id",
        "event_date",
        "event_type",
        "notes",
        "follow_up_date",
        "status_change",
        "created_at",
    ),
    "communicator_import_rows": (
        "source_row_hash",
        "source",
        "source_file",
        "source_row_number",
        "dossier_id",
        "event_ids",
        "imported_at",
    ),
}


def normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def connect(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    return connection


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def require_legacy_schema(connection: sqlite3.Connection) -> None:
    required = {
        "dossiers": set(ORIGINAL_COLUMNS["dossiers"]),
        "dossier_events": set(ORIGINAL_COLUMNS["dossier_events"]),
        "communicator_import_rows": set(ORIGINAL_COLUMNS["communicator_import_rows"]),
    }
    missing = {
        table: sorted(columns - table_columns(connection, table))
        for table, columns in required.items()
        if not columns.issubset(table_columns(connection, table))
    }
    if missing:
        raise RuntimeError(f"Preflight refused: required legacy columns are missing: {missing}")


def backup_database(database: Path) -> Path:
    backup_dir = REPO_ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{database.stem}_{timestamp}{database.suffix}"
    counter = 1
    while backup_path.exists():
        backup_path = backup_dir / f"{database.stem}_{timestamp}_{counter}{database.suffix}"
        counter += 1
    shutil.copy2(database, backup_path)
    return backup_path


def snapshot_original_data(connection: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    snapshot: dict[str, list[tuple[Any, ...]]] = {}
    for table, columns in ORIGINAL_COLUMNS.items():
        quoted_columns = ", ".join(columns)
        snapshot[table] = [
            tuple(row)
            for row in connection.execute(
                f"SELECT {quoted_columns} FROM {table} ORDER BY rowid"
            ).fetchall()
        ]
    return snapshot


def preflight(connection: sqlite3.Connection) -> dict[str, Any]:
    require_legacy_schema(connection)
    dossiers = connection.execute(
        "SELECT id, customer, contact FROM dossiers ORDER BY rowid"
    ).fetchall()

    empty_customers = [row[0] for row in dossiers if not normalize(row[1])]
    company_groups: dict[str, list[str]] = defaultdict(list)
    for row in dossiers:
        key = normalize(row[1])
        if key and row[1] not in company_groups[key]:
            company_groups[key].append(row[1])

    spelling_variants = {
        key: values for key, values in company_groups.items() if len(values) > 1
    }
    if spelling_variants:
        conflicts = "; ".join(
            f"{key!r}: {values!r}" for key, values in sorted(spelling_variants.items())
        )
        raise RuntimeError(
            "Preflight refused: ambiguous normalized company collisions: " + conflicts
        )
    if empty_customers:
        raise RuntimeError(
            "Preflight refused: dossiers with empty customer/company names: "
            + ", ".join(empty_customers)
        )

    existing_migration = None
    if "schema_migrations" in list_tables(connection):
        existing_migration = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (MIGRATION_VERSION,),
        ).fetchone()

    warnings: list[str] = []
    for key, values in spelling_variants.items():
        warnings.append(
            f"Company spelling variants share normalized name {key!r}: {values!r}"
        )
    placeholder_contacts = [
        {"dossier_id": row[0], "company": row[1], "contact": row[2]}
        for row in dossiers
        if normalize(row[2]) == "contact"
    ]
    if placeholder_contacts:
        warnings.append(
            "The literal contact value 'Contact' is preserved and flagged for manual review."
        )

    return {
        "dossier_count": len(dossiers),
        "event_count": connection.execute("SELECT COUNT(*) FROM dossier_events").fetchone()[0],
        "communicator_import_rows_count": connection.execute(
            "SELECT COUNT(*) FROM communicator_import_rows"
        ).fetchone()[0],
        "normalized_company_count": len(company_groups),
        "non_empty_contact_count": sum(bool(normalize(row[2])) for row in dossiers),
        "spelling_variants": spelling_variants,
        "placeholder_contacts": placeholder_contacts,
        "warnings": warnings,
        "already_applied": existing_migration is not None,
    }


def list_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            relationship_type TEXT NULL CHECK (
                relationship_type IN ('Klant', 'Prospect', 'Leverancier')
            ),
            street TEXT NOT NULL DEFAULT '',
            house_number TEXT NOT NULL DEFAULT '',
            postal_code TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_persons (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            job_title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
        """
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS companies_normalized_name_unique "
        "ON companies(normalized_name)"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS contact_person_company_name_unique "
        "ON contact_persons(company_id, normalized_name)"
    )

    dossier_columns = table_columns(connection, "dossiers")
    if "company_id" not in dossier_columns:
        connection.execute("ALTER TABLE dossiers ADD COLUMN company_id TEXT NULL")
    if "primary_contact_person_id" not in dossier_columns:
        connection.execute(
            "ALTER TABLE dossiers ADD COLUMN primary_contact_person_id TEXT NULL"
        )
    if "contact_person_id" not in table_columns(connection, "dossier_events"):
        connection.execute(
            "ALTER TABLE dossier_events ADD COLUMN contact_person_id TEXT NULL"
        )


def migrate(connection: sqlite3.Connection) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    dossiers = connection.execute(
        "SELECT id, customer, contact FROM dossiers ORDER BY rowid"
    ).fetchall()
    company_ids: dict[str, str] = {}
    contact_ids: dict[tuple[str, str], str] = {}
    companies_created = 0
    contacts_created = 0

    for dossier in dossiers:
        company_key = normalize(dossier[1])
        company = connection.execute(
            "SELECT id FROM companies WHERE normalized_name = ?", (company_key,)
        ).fetchone()
        if company is None:
            company_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO companies (
                    id, name, normalized_name, relationship_type, street,
                    house_number, postal_code, city, country, created_at, updated_at
                ) VALUES (?, ?, ?, NULL, '', '', '', '', '', ?, ?)
                """,
                (company_id, dossier[1].strip(), company_key, now, now),
            )
            companies_created += 1
        else:
            company_id = company[0]
        company_ids[company_key] = company_id

        primary_contact_id = None
        contact_name = (dossier[2] or "").strip()
        contact_key = normalize(contact_name)
        if contact_key:
            contact_lookup_key = (company_id, contact_key)
            primary_contact_id = contact_ids.get(contact_lookup_key)
            if primary_contact_id is None:
                contact = connection.execute(
                    """
                    SELECT id FROM contact_persons
                    WHERE company_id = ? AND normalized_name = ?
                    """,
                    (company_id, contact_key),
                ).fetchone()
                if contact is None:
                    primary_contact_id = str(uuid.uuid4())
                    connection.execute(
                        """
                        INSERT INTO contact_persons (
                            id, company_id, name, normalized_name, email, phone,
                            job_title, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, '', '', '', ?, ?)
                        """,
                        (primary_contact_id, company_id, contact_name, contact_key, now, now),
                    )
                    contacts_created += 1
                else:
                    primary_contact_id = contact[0]
                contact_ids[contact_lookup_key] = primary_contact_id

        connection.execute(
            """
            UPDATE dossiers
            SET company_id = ?, primary_contact_person_id = ?
            WHERE id = ?
            """,
            (company_id, primary_contact_id, dossier[0]),
        )

    connection.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
        (MIGRATION_VERSION, now),
    )
    return {
        "companies_created": companies_created,
        "contacts_created": contacts_created,
    }


def validate(
    connection: sqlite3.Connection,
    before: dict[str, Any],
    original_snapshot: dict[str, list[tuple[Any, ...]]],
) -> dict[str, Any]:
    dossier_count = connection.execute("SELECT COUNT(*) FROM dossiers").fetchone()[0]
    event_count = connection.execute("SELECT COUNT(*) FROM dossier_events").fetchone()[0]
    import_count = connection.execute(
        "SELECT COUNT(*) FROM communicator_import_rows"
    ).fetchone()[0]
    invalid_company_ids = connection.execute(
        """
        SELECT COUNT(*) FROM dossiers d
        LEFT JOIN companies c ON c.id = d.company_id
        WHERE d.company_id IS NULL OR c.id IS NULL
        """
    ).fetchone()[0]
    invalid_primary_contacts = connection.execute(
        """
        SELECT COUNT(*)
        FROM dossiers d
        LEFT JOIN contact_persons p ON p.id = d.primary_contact_person_id
        WHERE d.contact IS NOT NULL AND trim(d.contact) != ''
          AND (d.primary_contact_person_id IS NULL OR p.id IS NULL)
        """
    ).fetchone()[0]
    wrong_company_contacts = connection.execute(
        """
        SELECT COUNT(*)
        FROM dossiers d
        JOIN contact_persons p ON p.id = d.primary_contact_person_id
        WHERE p.company_id != d.company_id
        """
    ).fetchone()[0]
    historical_event_contacts = connection.execute(
        "SELECT COUNT(*) FROM dossier_events WHERE contact_person_id IS NOT NULL"
    ).fetchone()[0]

    unchanged = True
    for table, columns in ORIGINAL_COLUMNS.items():
        values = [
            tuple(row)
            for row in connection.execute(
                f"SELECT {', '.join(columns)} FROM {table} ORDER BY rowid"
            ).fetchall()
        ]
        unchanged = unchanged and values == original_snapshot[table]

    checks = {
        "dossier_count_unchanged": dossier_count == before["dossier_count"],
        "event_count_unchanged": event_count == before["event_count"],
        "communicator_import_rows_count_unchanged": import_count
        == before["communicator_import_rows_count"],
        "every_dossier_has_valid_company": invalid_company_ids == 0,
        "every_non_empty_contact_has_primary_contact": invalid_primary_contacts == 0,
        "every_primary_contact_belongs_to_company": wrong_company_contacts == 0,
        "historical_event_contacts_remain_null": historical_event_contacts == 0,
        "original_data_unchanged": unchanged,
    }
    return {
        "counts_after": {
            "dossiers": dossier_count,
            "dossier_events": event_count,
            "communicator_import_rows": import_count,
        },
        "invalid_company_references": invalid_company_ids,
        "invalid_primary_contact_references": invalid_primary_contacts,
        "primary_contacts_from_wrong_company": wrong_company_contacts,
        "historical_events_with_contact": historical_event_contacts,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def run(database: Path) -> dict[str, Any]:
    if not database.exists():
        raise RuntimeError(f"Migration refused: database does not exist: {database}")

    backup_path = backup_database(database)
    with connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        before = preflight(connection)
        snapshot = snapshot_original_data(connection)
        if before["already_applied"]:
            return {
                "migration": MIGRATION_VERSION,
                "status": "already_applied",
                "backup_path": str(backup_path),
                "before": before,
                "companies_created": 0,
                "contacts_created": 0,
                "warnings": before["warnings"],
                "rerun_would_create": {"companies": 0, "contacts": 0},
            }

        connection.execute("BEGIN")
        ensure_schema(connection)
        result = migrate(connection)
        after = validate(connection, before, snapshot)
        if not after["all_checks_passed"]:
            raise RuntimeError(
                "Migration validation failed; transaction will be rolled back: "
                + json.dumps(after, ensure_ascii=False)
            )
        connection.commit()

    return {
        "migration": MIGRATION_VERSION,
        "status": "migrated",
        "backup_path": str(backup_path),
        "before": before,
        **result,
        "after": after,
        "warnings": before["warnings"],
        "rerun_would_create": {"companies": 0, "contacts": 0},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate dossiers to companies and contact persons.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.database), indent=2, ensure_ascii=False))
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()