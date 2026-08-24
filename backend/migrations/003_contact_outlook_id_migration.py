from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


MIGRATION_VERSION = "003_contact_outlook_id"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = REPO_ROOT / "database" / "actions.db"


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def preflight(connection: sqlite3.Connection) -> dict[str, Any]:
    required_tables = ["contact_persons", "schema_migrations"]
    missing_tables = [table for table in required_tables if not table_exists(connection, table)]
    if missing_tables:
        raise RuntimeError(f"Preflight refused: required tables are missing: {missing_tables}")

    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(contact_persons)")}
    contact_ids = [row[0] for row in connection.execute("SELECT id FROM contact_persons ORDER BY rowid")]
    existing_marker = connection.execute(
        "SELECT version, applied_at FROM schema_migrations WHERE version = ?",
        (MIGRATION_VERSION,),
    ).fetchone()
    outlook_values = None
    if "outlook_contact_id" in columns:
        outlook_values = [
            row[0]
            for row in connection.execute(
                "SELECT outlook_contact_id FROM contact_persons ORDER BY rowid"
            )
        ]
    return {
        "required_tables": required_tables,
        "missing_tables": missing_tables,
        "contact_count": len(contact_ids),
        "contact_ids": contact_ids,
        "migration_record": dict(existing_marker) if existing_marker else None,
        "outlook_contact_id_exists": "outlook_contact_id" in columns,
        "outlook_contact_id_not_null": bool(columns.get("outlook_contact_id", (None, None, None, 0))[3]) if "outlook_contact_id" in columns else None,
        "outlook_contact_id_values": outlook_values,
    }


def validate(connection: sqlite3.Connection, before: dict[str, Any]) -> dict[str, Any]:
    after_ids = [row[0] for row in connection.execute("SELECT id FROM contact_persons ORDER BY rowid")]
    contact_column = next(
        (row for row in connection.execute("PRAGMA table_info(contact_persons)") if row[1] == "outlook_contact_id"),
        None,
    )
    index = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        ("contact_person_outlook_id_unique",),
    ).fetchone()
    duplicate_count = connection.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT outlook_contact_id FROM contact_persons
            WHERE outlook_contact_id IS NOT NULL
            GROUP BY outlook_contact_id HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    migration_record = connection.execute(
        "SELECT version, applied_at FROM schema_migrations WHERE version = ?",
        (MIGRATION_VERSION,),
    ).fetchone()
    index_sql = index[1] if index else ""
    checks = {
        "contact_count_unchanged": len(after_ids) == before["contact_count"],
        "all_contact_ids_preserved": after_ids == before["contact_ids"],
        "outlook_contact_id_exists": contact_column is not None,
        "outlook_contact_id_nullable": contact_column is not None and contact_column[3] == 0,
        "unique_partial_index_exists": "UNIQUE INDEX" in index_sql.upper() and "WHERE outlook_contact_id IS NOT NULL" in index_sql,
        "no_duplicate_non_null_outlook_ids": duplicate_count == 0,
        "migration_recorded": migration_record is not None,
    }
    return {
        "counts_after": {"contact_persons": len(after_ids)},
        "duplicate_non_null_outlook_ids": duplicate_count,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def run(database: Path) -> dict[str, Any]:
    if not database.exists():
        raise RuntimeError(f"Migration refused: database does not exist: {database}")
    backup_dir = REPO_ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{database.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{database.suffix}"
    shutil.copy2(database, backup_path)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        before = preflight(connection)
        if before["migration_record"] is not None:
            return {
                "migration": MIGRATION_VERSION,
                "status": "already_applied",
                "backup_path": str(backup_path),
                "before": before,
            }
        connection.execute("BEGIN")
        if not before["outlook_contact_id_exists"]:
            connection.execute("ALTER TABLE contact_persons ADD COLUMN outlook_contact_id TEXT NULL")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS contact_person_outlook_id_unique "
            "ON contact_persons(outlook_contact_id) WHERE outlook_contact_id IS NOT NULL"
        )
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (MIGRATION_VERSION, datetime.utcnow().isoformat()),
        )
        after = validate(connection, before)
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
            "after": after,
        }
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    print(json.dumps(run(args.database), indent=2))