from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


MIGRATION_VERSION = "005_contact_sync_state"
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

    existing_marker = connection.execute(
        "SELECT version, applied_at FROM schema_migrations WHERE version = ?",
        (MIGRATION_VERSION,),
    ).fetchone()
    return {
        "required_tables": required_tables,
        "missing_tables": missing_tables,
        "contact_sync_state_exists": table_exists(connection, "contact_sync_state"),
        "migration_record": dict(existing_marker) if existing_marker else None,
    }


def validate(connection: sqlite3.Connection) -> dict[str, Any]:
    columns = [row[1] for row in connection.execute("PRAGMA table_info(contact_sync_state)")]
    migration_record = connection.execute(
        "SELECT version, applied_at FROM schema_migrations WHERE version = ?",
        (MIGRATION_VERSION,),
    ).fetchone()
    expected_columns = {
        "local_contact_id",
        "outlook_contact_id",
        "last_synced_at",
        "synced_name",
        "synced_company",
        "synced_email",
        "synced_phone",
        "synced_mobile_phone",
        "outlook_last_modified",
    }
    checks = {
        "table_exists": table_exists(connection, "contact_sync_state"),
        "all_columns_present": expected_columns.issubset(set(columns)),
        "row_count_is_zero": connection.execute("SELECT COUNT(*) FROM contact_sync_state").fetchone()[0] == 0,
        "migration_recorded": migration_record is not None,
    }
    return {"columns": columns, "checks": checks, "all_checks_passed": all(checks.values())}


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
        if not before["contact_sync_state_exists"]:
            connection.execute(
                """
                CREATE TABLE contact_sync_state (
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
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (MIGRATION_VERSION, datetime.utcnow().isoformat()),
        )
        after = validate(connection)
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
