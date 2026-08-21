from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


MIGRATION_VERSION = "003_contact_outlook_id"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = REPO_ROOT / "database" / "actions.db"


def run(database: Path) -> dict[str, str]:
    if not database.exists():
        raise RuntimeError(f"Migration refused: database does not exist: {database}")
    backup_dir = REPO_ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{database.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{database.suffix}"
    shutil.copy2(database, backup_path)
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (MIGRATION_VERSION,)).fetchone():
            return {"migration": MIGRATION_VERSION, "status": "already_applied", "backup_path": str(backup_path)}
        connection.execute("BEGIN")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(contact_persons)")}
        if "outlook_contact_id" not in columns:
            connection.execute("ALTER TABLE contact_persons ADD COLUMN outlook_contact_id TEXT NULL")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS contact_person_outlook_id_unique "
            "ON contact_persons(outlook_contact_id) WHERE outlook_contact_id IS NOT NULL"
        )
        connection.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (MIGRATION_VERSION, datetime.utcnow().isoformat()))
        connection.commit()
        return {"migration": MIGRATION_VERSION, "status": "migrated", "backup_path": str(backup_path)}
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    print(json.dumps(run(args.database), indent=2))