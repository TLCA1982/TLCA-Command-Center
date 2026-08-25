from __future__ import annotations

import os
import re
import sys
import json
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.schema import Index


EXPECTED_TABLES = {
    "schema_migrations",
    "companies",
    "contact_persons",
    "dossiers",
    "dossier_events",
    "manual_actions",
    "microsoft_metadata",
    "communicator_import_rows",
}


class PhaseError(RuntimeError):
    def __init__(self, phase: str, cause: Exception) -> None:
        super().__init__(phase)
        self.phase = phase
        self.cause = cause


def _run_phase(phase: str, operation: Any) -> Any:
    try:
        return operation()
    except PhaseError:
        raise
    except Exception as error:
        raise PhaseError(phase, error) from error


def _sqlstate(error: Exception) -> str | None:
    for candidate in (error, getattr(error, "orig", None)):
        if candidate is not None:
            value = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
            if value:
                return str(value)
    return None


def _sanitized_message(error: Exception) -> str:
    message = str(error).strip() or "No error message provided"
    message = re.sub(r"(?i)(?:postgres(?:ql)?(?:\+[^:/\s]+)?://)\S+", "<redacted-database-url>", message)
    message = re.sub(
        r"(?i)\b(password|passwd|pwd|username|user|host|port|dbname|database)\s*=\s*[^\s,;]+",
        r"\1=<redacted>",
        message,
    )
    message = re.sub(
        r"(?i)\b(password|passwd|pwd|username|user|role)\s+[\"']?[^\"'\s,;]+[\"']?",
        r"\1 <redacted>",
        message,
    )
    return message


def _diagnostic(error: PhaseError) -> str:
    state = _sqlstate(error.cause)
    sqlstate = f", sqlstate={state}" if state else ""
    return (
        f"PostgreSQL shadow schema creation failed; phase={error.phase}; "
        f"exception={type(error.cause).__name__}{sqlstate}; "
        f"message={_sanitized_message(error.cause)}"
    )

metadata = MetaData()

schema_migrations = Table(
    "schema_migrations",
    metadata,
    Column("version", Text, primary_key=True),
    Column("applied_at", Text, nullable=False),
)

companies = Table(
    "companies",
    metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("normalized_name", Text, nullable=False),
    Column("relationship_type", Text, nullable=True),
    Column("street", Text, nullable=False, server_default=text("''")),
    Column("house_number", Text, nullable=False, server_default=text("''")),
    Column("postal_code", Text, nullable=False, server_default=text("''")),
    Column("city", Text, nullable=False, server_default=text("''")),
    Column("country", Text, nullable=False, server_default=text("''")),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    CheckConstraint(
        "relationship_type IN ('Klant', 'Prospect', 'Leverancier')",
        name="companies_relationship_type_check",
    ),
)

contact_persons = Table(
    "contact_persons",
    metadata,
    Column("id", Text, primary_key=True),
    Column("company_id", Text, ForeignKey("companies.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("normalized_name", Text, nullable=False),
    Column("email", Text, nullable=False, server_default=text("''")),
    Column("phone", Text, nullable=False, server_default=text("''")),
    Column("job_title", Text, nullable=False, server_default=text("''")),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("is_active", Integer, nullable=False, server_default=text("1")),
    Column("is_primary", Integer, nullable=False, server_default=text("0")),
    Column("outlook_contact_id", Text, nullable=True),
    Column("mobile_phone", Text, nullable=False, server_default=text("''")),
)

# Legacy mixed-case names are intentionally quoted for PostgreSQL compatibility.
manual_actions = Table(
    "manual_actions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("title", Text, nullable=False),
    Column("customer", Text),
    Column("contact", Text),
    Column("type", Text),
    Column("priority", Text),
    Column("dueDate", Text, quote=True),
    Column("status", Text),
    Column("notes", Text),
    Column("createdDate", Text, quote=True),
    Column("lastModifiedDate", Text, quote=True),
    Column("source", Text),
    Column("adsolutCustomerId", Text, quote=True),
    Column("visitReportId", Text, quote=True),
    Column("communicatorId", Text, quote=True),
    Column("quotationId", Text, quote=True),
)

dossiers = Table(
    "dossiers",
    metadata,
    Column("id", Text, primary_key=True),
    Column("customer", Text),
    Column("contact", Text),
    Column("subject", Text),
    Column("status", Text),
    Column("follow_up_date", Text),
    Column("source", Text),
    Column("external_id", Text),
    Column("created_at", Text),
    Column("updated_at", Text),
    Column("company_id", Text),
    Column("primary_contact_person_id", Text),
)

dossier_events = Table(
    "dossier_events",
    metadata,
    Column("id", Text, primary_key=True),
    Column("dossier_id", Text),
    Column("event_date", Text),
    Column("event_type", Text),
    Column("notes", Text),
    Column("follow_up_date", Text),
    Column("status_change", Text),
    Column("created_at", Text),
    Column("contact_person_id", Text),
)

microsoft_metadata = Table(
    "microsoft_metadata",
    metadata,
    Column("ms_id", Text, primary_key=True),
    Column("source", Text),
    Column("customer", Text),
    Column("contact", Text),
    Column("action_type", Text),
    Column("lastModifiedDate", Text, quote=True),
)

communicator_import_rows = Table(
    "communicator_import_rows",
    metadata,
    Column("source_row_hash", Text, primary_key=True),
    Column("source", Text, nullable=False),
    Column("source_file", Text, nullable=False),
    Column("source_row_number", Integer, nullable=False),
    Column("dossier_id", Text, nullable=False),
    Column("event_ids", Text, nullable=False),
    Column("imported_at", Text, nullable=False),
)

Index(
    "companies_normalized_name_unique",
    companies.c.normalized_name,
    unique=True,
)
Index(
    "contact_person_company_name_unique",
    contact_persons.c.company_id,
    contact_persons.c.normalized_name,
    unique=True,
)
Index(
    "contact_person_active_primary_unique",
    contact_persons.c.company_id,
    unique=True,
    postgresql_where=text("is_active = 1 AND is_primary = 1"),
)
Index(
    "contact_person_outlook_id_unique",
    contact_persons.c.outlook_contact_id,
    unique=True,
    postgresql_where=text("outlook_contact_id IS NOT NULL"),
)


def require_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    url = make_url(database_url)
    if url.drivername != "postgresql+psycopg":
        raise RuntimeError("DATABASE_URL must use the postgresql+psycopg SQLAlchemy driver")
    return database_url


def create_schema_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True)


def _application_tables(connection: Any) -> set[str]:
    inspector = inspect(connection)
    return set(inspector.get_table_names()) & EXPECTED_TABLES


def _type_signature(type_: Any, dialect: Any) -> str:
    return re.sub(r"\s+", " ", type_.compile(dialect=dialect).upper()).strip()


def refuse_non_empty_target(connection: Any) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    unexpected_tables = existing_tables - EXPECTED_TABLES
    application_tables = existing_tables & EXPECTED_TABLES
    if application_tables or unexpected_tables:
        names = sorted(application_tables | unexpected_tables)
        raise RuntimeError("Target PostgreSQL database is not empty: " + ", ".join(names))
    if inspector.get_view_names():
        raise RuntimeError("Target PostgreSQL database contains views")
    if connection.execute(
        text("SELECT COUNT(*) FROM pg_catalog.pg_trigger WHERE NOT tgisinternal")
    ).scalar_one():
        raise RuntimeError("Target PostgreSQL database contains user triggers")
    if connection.execute(
        text("SELECT COUNT(*) FROM pg_catalog.pg_class WHERE relkind = 'S'")
    ).scalar_one():
        raise RuntimeError("Target PostgreSQL database contains sequences")


def _normalized_default(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("::text", "").replace("::integer", "").replace(" ", "")


def validate_schema(connection: Any) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if tables != EXPECTED_TABLES:
        raise RuntimeError(f"Unexpected application table set: {sorted(tables)}")

    expected_columns = {table.name: [column.name for column in table.columns] for table in metadata.tables.values()}
    for table_name, columns in expected_columns.items():
        actual_columns = inspector.get_columns(table_name)
        actual_names = [column["name"] for column in actual_columns]
        if actual_names != columns:
            raise RuntimeError(f"Unexpected columns for {table_name}: {actual_names}")
        for expected, actual in zip(metadata.tables[table_name].columns, actual_columns):
            if _type_signature(actual["type"], connection.dialect) != _type_signature(expected.type, connection.dialect):
                raise RuntimeError(f"Unexpected type for {table_name}.{expected.name}")
            if bool(actual["nullable"]) != bool(expected.nullable):
                raise RuntimeError(f"Unexpected nullability for {table_name}.{expected.name}")
            expected_default = _normalized_default(str(expected.server_default.arg) if expected.server_default else None)
            actual_default = _normalized_default(actual.get("default"))
            if expected_default != actual_default:
                raise RuntimeError(f"Unexpected default for {table_name}.{expected.name}")

    expected_primary_keys = {
        table.name: [column.name for column in table.primary_key.columns]
        for table in metadata.tables.values()
    }
    for table_name, expected_columns_for_key in expected_primary_keys.items():
        actual = inspector.get_pk_constraint(table_name)["constrained_columns"]
        if actual != expected_columns_for_key:
            raise RuntimeError(f"Unexpected primary key for {table_name}: {actual}")

    foreign_keys = [
        (table_name, fk["constrained_columns"], fk["referred_table"], fk["referred_columns"])
        for table_name in EXPECTED_TABLES
        for fk in inspector.get_foreign_keys(table_name)
    ]
    if foreign_keys != [("contact_persons", ["company_id"], "companies", ["id"])]:
        raise RuntimeError(f"Unexpected foreign keys: {foreign_keys}")

    expected_indexes = {
        "companies": {"companies_normalized_name_unique", "companies_pkey"},
        "contact_persons": {
            "contact_person_company_name_unique",
            "contact_person_active_primary_unique",
            "contact_person_outlook_id_unique",
            "contact_persons_pkey",
        },
    }
    for table_name, names in expected_indexes.items():
        actual_names = {index["name"] for index in inspector.get_indexes(table_name)} | {
            inspector.get_pk_constraint(table_name)["name"]
        }
        if actual_names != names:
            raise RuntimeError(f"Unexpected indexes for {table_name}: {sorted(actual_names)}")

    if connection.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar_one() != 0:
        raise RuntimeError("schema_migrations is not empty")
    for table_name in EXPECTED_TABLES - {"schema_migrations"}:
        if connection.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one() != 0:
            raise RuntimeError(f"{table_name} is not empty")


def inspect_target(connection: Any) -> dict[str, Any]:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    views = set(inspector.get_view_names())
    sequences = {
        row[0]
        for row in connection.execute(
            text("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = current_schema()")
        )
    }
    triggers = {
        row[0]
        for row in connection.execute(
            text(
                "SELECT trigger_name FROM information_schema.triggers "
                "WHERE event_object_schema = current_schema()"
            )
        )
    }
    row_counts = {}
    for table_name in sorted(tables & EXPECTED_TABLES):
        row_counts[table_name] = connection.execute(
            text(f'SELECT COUNT(*) FROM "{table_name}"')
        ).scalar_one()
    return {
        "application_tables": sorted(tables & EXPECTED_TABLES),
        "application_views": sorted(views & EXPECTED_TABLES),
        "application_sequences": sorted(sequences & EXPECTED_TABLES),
        "application_triggers": sorted(triggers & EXPECTED_TABLES),
        "row_counts": row_counts,
    }


def run() -> None:
    database_url = _run_phase("configuration validation", require_database_url)
    engine = _run_phase("PostgreSQL connection", lambda: create_schema_engine(database_url))
    connection = None
    transaction = None
    try:
        connection = _run_phase("PostgreSQL connection", engine.connect)
        transaction = _run_phase("PostgreSQL connection", connection.begin)
        _run_phase("target emptiness inspection", lambda: refuse_non_empty_target(connection))
        _run_phase("schema creation", lambda: metadata.create_all(connection, checkfirst=False))
        _run_phase("schema validation", lambda: validate_schema(connection))
        _run_phase("transaction commit", transaction.commit)
    finally:
        if transaction is not None and transaction.is_active:
            transaction.rollback()
        if connection is not None:
            connection.close()
        engine.dispose()
    print("PostgreSQL shadow schema created and validated successfully")


def inspect_only() -> None:
    database_url = _run_phase("configuration validation", require_database_url)
    engine = _run_phase("PostgreSQL connection", lambda: create_schema_engine(database_url))
    try:
        with engine.connect() as connection:
            report = _run_phase("target read-only inspection", lambda: inspect_target(connection))
        print(json.dumps(report, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    inspect_mode = "--inspect" in sys.argv[1:]
    try:
        inspect_only() if inspect_mode else run()
    except PhaseError as error:
        print(_diagnostic(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception as error:
        print(
            "PostgreSQL shadow schema creation failed; phase=unknown; "
            f"exception={type(error).__name__}; message={_sanitized_message(error)}",
            file=sys.stderr,
        )
        raise SystemExit(1)
