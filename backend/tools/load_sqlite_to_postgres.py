from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, Text, create_engine, inspect, insert, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT / "database" / "actions.db"
EXPECTED_TABLES = (
    "schema_migrations",
    "companies",
    "contact_persons",
    "dossiers",
    "dossier_events",
    "manual_actions",
    "microsoft_metadata",
    "communicator_import_rows",
)
PRIMARY_KEYS = {
    "schema_migrations": ("version",),
    "companies": ("id",),
    "contact_persons": ("id",),
    "dossiers": ("id",),
    "dossier_events": ("id",),
    "manual_actions": ("id",),
    "microsoft_metadata": ("ms_id",),
    "communicator_import_rows": ("source_row_hash",),
}

metadata = MetaData()
schema_migrations = Table(
    "schema_migrations", metadata,
    Column("version", Text, primary_key=True), Column("applied_at", Text, nullable=False),
)
companies = Table(
    "companies", metadata,
    Column("id", Text, primary_key=True), Column("name", Text, nullable=False),
    Column("normalized_name", Text, nullable=False), Column("relationship_type", Text),
    Column("street", Text, nullable=False), Column("house_number", Text, nullable=False),
    Column("postal_code", Text, nullable=False), Column("city", Text, nullable=False),
    Column("country", Text, nullable=False), Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)
contact_persons = Table(
    "contact_persons", metadata,
    Column("id", Text, primary_key=True), Column("company_id", Text, ForeignKey("companies.id"), nullable=False),
    Column("name", Text, nullable=False), Column("normalized_name", Text, nullable=False),
    Column("email", Text, nullable=False), Column("phone", Text, nullable=False),
    Column("job_title", Text, nullable=False), Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False), Column("is_active", Integer, nullable=False),
    Column("is_primary", Integer, nullable=False), Column("outlook_contact_id", Text),
    Column("mobile_phone", Text, nullable=False),
)
dossiers = Table(
    "dossiers", metadata,
    Column("id", Text, primary_key=True), Column("customer", Text), Column("contact", Text),
    Column("subject", Text), Column("status", Text), Column("follow_up_date", Text),
    Column("source", Text), Column("external_id", Text), Column("created_at", Text),
    Column("updated_at", Text), Column("company_id", Text), Column("primary_contact_person_id", Text),
)
dossier_events = Table(
    "dossier_events", metadata,
    Column("id", Text, primary_key=True), Column("dossier_id", Text), Column("event_date", Text),
    Column("event_type", Text), Column("notes", Text), Column("follow_up_date", Text),
    Column("status_change", Text), Column("created_at", Text), Column("contact_person_id", Text),
)
manual_actions = Table(
    "manual_actions", metadata,
    Column("id", Text, primary_key=True), Column("title", Text, nullable=False), Column("customer", Text),
    Column("contact", Text), Column("type", Text), Column("priority", Text),
    Column("dueDate", Text, quote=True), Column("status", Text), Column("notes", Text),
    Column("createdDate", Text, quote=True), Column("lastModifiedDate", Text, quote=True),
    Column("source", Text), Column("adsolutCustomerId", Text, quote=True),
    Column("visitReportId", Text, quote=True), Column("communicatorId", Text, quote=True),
    Column("quotationId", Text, quote=True),
)
microsoft_metadata = Table(
    "microsoft_metadata", metadata,
    Column("ms_id", Text, primary_key=True), Column("source", Text), Column("customer", Text),
    Column("contact", Text), Column("action_type", Text), Column("lastModifiedDate", Text, quote=True),
)
communicator_import_rows = Table(
    "communicator_import_rows", metadata,
    Column("source_row_hash", Text, primary_key=True), Column("source", Text, nullable=False),
    Column("source_file", Text, nullable=False), Column("source_row_number", Integer, nullable=False),
    Column("dossier_id", Text, nullable=False), Column("event_ids", Text, nullable=False),
    Column("imported_at", Text, nullable=False),
)
TABLES = {table.name: table for table in metadata.tables.values()}


def sanitized_message(error: Exception) -> str:
    message = str(error).strip() or "No error message provided"
    message = re.sub(r"(?i)(?:postgres(?:ql)?(?:\+[^:/\s]+)?://)\S+", "<redacted-database-url>", message)
    return re.sub(r"(?i)\b(password|passwd|pwd|username|user|host|port|dbname|database)\s*=\s*[^\s,;]+", r"\1=<redacted>", message)


def require_target_url() -> str:
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is required")
    if make_url(value).drivername != "postgresql+psycopg":
        raise RuntimeError("DATABASE_URL must use the postgresql+psycopg SQLAlchemy driver")
    return value


def source_connection(path: Path) -> sqlite3.Connection:
    if not path.exists() or not path.is_file():
        raise RuntimeError("SQLite source file does not exist")
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def source_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')]


def duplicate_count(values: Iterable[tuple[Any, ...]]) -> int:
    seen: set[tuple[Any, ...]] = set()
    duplicates = 0
    for value in values:
        if value in seen:
            duplicates += 1
        seen.add(value)
    return duplicates


def source_preflight(connection: sqlite3.Connection) -> dict[str, Any]:
    tables = source_tables(connection)
    missing = sorted(set(EXPECTED_TABLES) - tables)
    if missing:
        raise RuntimeError("SQLite source is missing tables: " + ", ".join(missing))
    data = {table: rows(connection, table) for table in EXPECTED_TABLES}
    checks: dict[str, Any] = {"missing_tables": missing, "row_counts": {table: len(data[table]) for table in EXPECTED_TABLES}}
    for table, key_columns in PRIMARY_KEYS.items():
        checks[f"duplicate_primary_keys_{table}"] = duplicate_count(tuple(row[column] for column in key_columns) for row in data[table])
        if any(any(row[column] is None for column in key_columns) for row in data[table]):
            raise RuntimeError(f"SQLite source contains NULL primary key in {table}")
    checks["duplicate_company_normalized_names"] = duplicate_count((row["normalized_name"],) for row in data["companies"])
    checks["duplicate_contact_company_names"] = duplicate_count((row["company_id"], row["normalized_name"]) for row in data["contact_persons"])
    checks["duplicate_outlook_contact_ids"] = duplicate_count((row["outlook_contact_id"],) for row in data["contact_persons"] if row["outlook_contact_id"] is not None)
    checks["duplicate_active_primaries"] = duplicate_count((row["company_id"],) for row in data["contact_persons"] if row["is_active"] == 1 and row["is_primary"] == 1)
    company_ids = {row["id"] for row in data["companies"]}
    contact_by_id = {row["id"]: row for row in data["contact_persons"]}
    dossier_by_id = {row["id"]: row for row in data["dossiers"]}
    checks["orphan_contact_companies"] = sum(row["company_id"] not in company_ids for row in data["contact_persons"])
    checks["orphan_dossier_companies"] = sum(row["company_id"] is not None and row["company_id"] not in company_ids for row in data["dossiers"])
    checks["orphan_dossier_primary_contacts"] = sum(row["primary_contact_person_id"] is not None and row["primary_contact_person_id"] not in contact_by_id for row in data["dossiers"])
    checks["orphan_event_dossiers"] = sum(row["dossier_id"] is not None and row["dossier_id"] not in dossier_by_id for row in data["dossier_events"])
    checks["orphan_event_contacts"] = sum(row["contact_person_id"] is not None and row["contact_person_id"] not in contact_by_id for row in data["dossier_events"])
    checks["orphan_communicator_dossiers"] = sum(row["dossier_id"] not in dossier_by_id for row in data["communicator_import_rows"])
    invalid_json = 0
    for row in data["communicator_import_rows"]:
        try:
            json.loads(row["event_ids"])
        except (TypeError, json.JSONDecodeError):
            invalid_json += 1
    checks["invalid_event_ids_json"] = invalid_json
    required_markers = {
        "001_company_contact_structure", "002_contact_status_primary",
        "003_contact_outlook_id", "004_contact_mobile_phone",
    }
    marker_set = {row["version"] for row in data["schema_migrations"]}
    checks["migration_versions"] = sorted(marker_set)
    checks["migration_markers_valid"] = marker_set == required_markers
    failures = [key for key, value in checks.items() if key.startswith("duplicate_") and value != 0]
    failures += [key for key, value in checks.items() if key.startswith("orphan_") and value != 0]
    failures += ["invalid_event_ids_json"] if invalid_json else []
    if failures or not checks["migration_markers_valid"]:
        raise RuntimeError("SQLite source preflight failed: " + ", ".join(failures or ["migration_markers_valid"]))
    return {"checks": checks, "data": data}


def inspect_target(connection: Any) -> dict[str, Any]:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    missing = sorted(set(EXPECTED_TABLES) - tables)
    unexpected = sorted(tables - set(EXPECTED_TABLES))
    if missing:
        raise RuntimeError("PostgreSQL target is missing tables: " + ", ".join(missing))
    if unexpected:
        raise RuntimeError("PostgreSQL target contains unexpected tables: " + ", ".join(unexpected))
    counts = {table: connection.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one() for table in EXPECTED_TABLES}
    if any(counts.values()):
        raise RuntimeError("PostgreSQL target is not empty")
    return {"tables": sorted(tables), "row_counts": counts}


def row_key(table: str, row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row[column] for column in PRIMARY_KEYS[table])


def compare_data(connection: Any, source_data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    for table in EXPECTED_TABLES:
        target_rows = [dict(row) for row in connection.execute(TABLES[table].select()).mappings().all()]
        source_by_key = {row_key(table, row): row for row in source_data[table]}
        target_by_key = {row_key(table, row): row for row in target_rows}
        if source_by_key != target_by_key:
            raise RuntimeError(f"PostgreSQL data mismatch in {table}")
    return {"row_counts_match": True, "primary_keys_match": True, "complete_rows_match": True}


def run(source_path: Path, execute: bool) -> dict[str, Any]:
    if execute and source_path.resolve() == DEFAULT_SOURCE.resolve():
        raise RuntimeError("--execute requires an explicit source path that is not the live database/actions.db")
    source = source_connection(source_path)
    try:
        preflight = source_preflight(source)
    finally:
        source.close()
    target_url = require_target_url()
    engine = create_engine(target_url, future=True)
    try:
        with engine.connect() as connection:
            target = inspect_target(connection)
            if not execute:
                return {"mode": "dry_run", "source_read_only": True, "target": target, "preflight": preflight["checks"], "load": {"executed": False, "committed": False}}
        with engine.begin() as connection:
            target = inspect_target(connection)
            for table in EXPECTED_TABLES:
                source_rows = preflight["data"][table]
                if source_rows:
                    connection.execute(insert(TABLES[table]), source_rows)
            validation = compare_data(connection, preflight["data"])
        return {"mode": "execute", "source_read_only": True, "target": target, "preflight": preflight["checks"], "load": {"executed": True, "committed": True}, "validation": validation}
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a read-only SQLite snapshot into an empty PostgreSQL shadow schema.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--execute", action="store_true", help="Insert data; without this flag the tool is dry-run only")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.source, args.execute), indent=2, ensure_ascii=False))
    except Exception as error:
        print(
            f"SQLite-to-PostgreSQL load failed; exception={type(error).__name__}; message={sanitized_message(error)}",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
