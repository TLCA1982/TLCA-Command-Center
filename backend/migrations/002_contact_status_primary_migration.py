from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


MIGRATION_VERSION = "002_contact_status_primary"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = REPO_ROOT / "database" / "actions.db"


def connect(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def list_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


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


def preflight(connection: sqlite3.Connection) -> dict[str, Any]:
    tables = list_tables(connection)
    required_tables = {"companies", "contact_persons", "dossiers", "dossier_events"}
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        raise RuntimeError(f"Preflight refused: required tables are missing: {missing_tables}")

    required_contact_columns = {"id", "company_id", "is_active", "is_primary"}
    existing_columns = table_columns(connection, "contact_persons")
    missing_columns = sorted(required_contact_columns - existing_columns)
    migration_row = None
    if "schema_migrations" in tables:
        migration_row = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (MIGRATION_VERSION,),
        ).fetchone()

    return {
        "contact_count": connection.execute("SELECT COUNT(*) FROM contact_persons").fetchone()[0],
        "company_count": connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        "dossier_count": connection.execute("SELECT COUNT(*) FROM dossiers").fetchone()[0],
        "event_count": connection.execute("SELECT COUNT(*) FROM dossier_events").fetchone()[0],
        "dossier_contact_reference_count": connection.execute(
            "SELECT COUNT(*) FROM dossiers WHERE primary_contact_person_id IS NOT NULL"
        ).fetchone()[0] if "primary_contact_person_id" in table_columns(connection, "dossiers") else 0,
        "event_contact_reference_count": connection.execute(
            "SELECT COUNT(*) FROM dossier_events WHERE contact_person_id IS NOT NULL"
        ).fetchone()[0] if "contact_person_id" in table_columns(connection, "dossier_events") else 0,
        "missing_contact_columns": missing_columns,
        "already_applied": migration_row is not None,
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
    contact_columns = table_columns(connection, "contact_persons")
    if "is_active" not in contact_columns:
        connection.execute(
            "ALTER TABLE contact_persons ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
        )
    if "is_primary" not in contact_columns:
        connection.execute(
            "ALTER TABLE contact_persons ADD COLUMN is_primary INTEGER NOT NULL DEFAULT 0"
        )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS contact_person_active_primary_unique
        ON contact_persons(company_id)
        WHERE is_active = 1 AND is_primary = 1
        """
    )


def validate(connection: sqlite3.Connection, before: dict[str, Any]) -> dict[str, Any]:
    counts = {
        "contact_count": connection.execute("SELECT COUNT(*) FROM contact_persons").fetchone()[0],
        "company_count": connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        "dossier_count": connection.execute("SELECT COUNT(*) FROM dossiers").fetchone()[0],
        "event_count": connection.execute("SELECT COUNT(*) FROM dossier_events").fetchone()[0],
        "dossier_contact_reference_count": connection.execute(
            "SELECT COUNT(*) FROM dossiers WHERE primary_contact_person_id IS NOT NULL"
        ).fetchone()[0],
        "event_contact_reference_count": connection.execute(
            "SELECT COUNT(*) FROM dossier_events WHERE contact_person_id IS NOT NULL"
        ).fetchone()[0],
    }
    invalid_references = connection.execute(
        """
        SELECT COUNT(*)
        FROM dossiers d
        JOIN contact_persons p ON p.id = d.primary_contact_person_id
        WHERE p.company_id != d.company_id
        """
    ).fetchone()[0]
    missing_dossier_contacts = connection.execute(
        """
        SELECT COUNT(*)
        FROM dossiers d
        LEFT JOIN contact_persons p ON p.id = d.primary_contact_person_id
        WHERE d.primary_contact_person_id IS NOT NULL AND p.id IS NULL
        """
    ).fetchone()[0]
    missing_event_contacts = connection.execute(
        """
        SELECT COUNT(*)
        FROM dossier_events e
        LEFT JOIN contact_persons p ON p.id = e.contact_person_id
        WHERE e.contact_person_id IS NOT NULL AND p.id IS NULL
        """
    ).fetchone()[0]
    inactive_primaries = connection.execute(
        "SELECT COUNT(*) FROM contact_persons WHERE is_primary = 1 AND is_active != 1"
    ).fetchone()[0]
    duplicate_primaries = connection.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT company_id FROM contact_persons
            WHERE is_active = 1 AND is_primary = 1
            GROUP BY company_id HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    checks = {
        "contact_count_unchanged": counts["contact_count"] == before["contact_count"],
        "company_count_unchanged": counts["company_count"] == before["company_count"],
        "dossier_count_unchanged": counts["dossier_count"] == before["dossier_count"],
        "event_count_unchanged": counts["event_count"] == before["event_count"],
        "dossier_contact_references_unchanged": counts["dossier_contact_reference_count"] == before["dossier_contact_reference_count"],
        "event_contact_references_unchanged": counts["event_contact_reference_count"] == before["event_contact_reference_count"],
        "dossier_references_exist": missing_dossier_contacts == 0,
        "event_references_exist": missing_event_contacts == 0,
        "dossier_contacts_match_company": invalid_references == 0,
        "all_primary_contacts_are_active": inactive_primaries == 0,
        "one_active_primary_per_company": duplicate_primaries == 0,
    }
    return {"counts_after": counts, "checks": checks, "all_checks_passed": all(checks.values())}


def run(database: Path) -> dict[str, Any]:
    if not database.exists():
        raise RuntimeError(f"Migration refused: database does not exist: {database}")
    backup_path = backup_database(database)
    connection = connect(database)
    try:
        before = preflight(connection)
        if before["already_applied"]:
            return {"migration": MIGRATION_VERSION, "status": "already_applied", "backup_path": str(backup_path), "before": before}
        connection.execute("BEGIN")
        ensure_schema(connection)
        now = datetime.utcnow().isoformat()
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (MIGRATION_VERSION, now),
        )
        after = validate(connection, before)
        if not after["all_checks_passed"]:
            raise RuntimeError(
                "Migration validation failed; transaction will be rolled back: "
                + json.dumps(after, ensure_ascii=False)
            )
        connection.commit()
    finally:
        connection.close()
    return {"migration": MIGRATION_VERSION, "status": "migrated", "backup_path": str(backup_path), "before": before, "after": after}


def main() -> None:
    parser = argparse.ArgumentParser(description="Add active and company-primary contact fields.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.database), indent=2, ensure_ascii=False))
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()