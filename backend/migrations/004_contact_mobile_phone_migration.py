from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


MIGRATION_VERSION = "004_contact_mobile_phone"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = REPO_ROOT / "database" / "actions.db"


def connect(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


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
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    required = {"contact_persons", "schema_migrations"}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError(f"Preflight refused: required tables are missing: {missing}")
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(contact_persons)")}
    ids = [row[0] for row in connection.execute("SELECT id FROM contact_persons ORDER BY rowid")]
    applied = connection.execute(
        "SELECT version, applied_at FROM schema_migrations WHERE version = ?",
        (MIGRATION_VERSION,),
    ).fetchone()
    return {
        "contact_count": len(ids),
        "contact_ids": ids,
        "mobile_phone_exists": "mobile_phone" in columns,
        "mobile_phone_not_nullable": columns.get("mobile_phone", (None, None, None, 1))[3] == 1 if "mobile_phone" in columns else None,
        "migration_record": dict(applied) if applied else None,
    }


def validate(connection: sqlite3.Connection, before: dict[str, Any]) -> dict[str, Any]:
    ids_after = [row[0] for row in connection.execute("SELECT id FROM contact_persons ORDER BY rowid")]
    mobile_column = next((row for row in connection.execute("PRAGMA table_info(contact_persons)") if row[1] == "mobile_phone"), None)
    migration_record = connection.execute(
        "SELECT version, applied_at FROM schema_migrations WHERE version = ?",
        (MIGRATION_VERSION,),
    ).fetchone()
    checks = {
        "contact_count_unchanged": len(ids_after) == before["contact_count"],
        "all_contact_ids_preserved": ids_after == before["contact_ids"],
        "mobile_phone_exists": mobile_column is not None,
        "mobile_phone_not_nullable": mobile_column is not None and mobile_column[3] == 1,
        "migration_recorded": migration_record is not None,
    }
    return {
        "contact_count_after": len(ids_after),
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def run(database: Path) -> dict[str, Any]:
    if not database.exists():
        raise RuntimeError(f"Migration refused: database does not exist: {database}")
    backup_path = backup_database(database)
    connection = connect(database)
    try:
        before = preflight(connection)
        if before["migration_record"] is not None:
            return {"migration": MIGRATION_VERSION, "status": "already_applied", "backup_path": str(backup_path), "before": before}
        connection.execute("BEGIN")
        if not before["mobile_phone_exists"]:
            connection.execute("ALTER TABLE contact_persons ADD COLUMN mobile_phone TEXT NOT NULL DEFAULT ''")
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (MIGRATION_VERSION, datetime.utcnow().isoformat()),
        )
        after = validate(connection, before)
        if not after["all_checks_passed"]:
            raise RuntimeError("Migration validation failed; transaction will be rolled back: " + json.dumps(after))
        connection.commit()
        return {"migration": MIGRATION_VERSION, "status": "migrated", "backup_path": str(backup_path), "before": before, "after": after}
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add mobile phone to contact persons.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.database), indent=2, ensure_ascii=False))
    except Exception as exc:
        raise SystemExit(str(exc)) from exc