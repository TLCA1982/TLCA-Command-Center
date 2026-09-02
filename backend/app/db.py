from __future__ import annotations

import sqlite3
import re
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection

from app.config import get_settings


DB_PATH = Path(__file__).resolve().parents[2] / "database" / "actions.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_settings = get_settings()
BACKEND = _settings.resolved_database_backend
DATABASE_URL = _settings.database_url or f"sqlite:///{DB_PATH.as_posix()}"
engine = create_engine(DATABASE_URL, future=True)


def is_sqlite() -> bool:
    return BACKEND == "sqlite"


def is_postgresql() -> bool:
    return BACKEND == "postgresql"


def require_tables(table_names: tuple[str, ...]) -> None:
    if is_sqlite():
        return
    if not is_postgresql():
        raise RuntimeError(f"Unsupported database backend: {BACKEND}")
    if not table_names:
        return
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name) for table_name in table_names):
        raise ValueError("Invalid table name")

    with engine.connect() as connection:
        inspector = inspect(connection)
        missing_tables = [table_name for table_name in table_names if not inspector.has_table(table_name)]
    if missing_tables:
        raise RuntimeError(
            "PostgreSQL schema is missing required table(s): " + ", ".join(missing_tables)
        )


def has_column(connection: Any, table_name: str, column_name: str) -> bool:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise ValueError("Invalid table name")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", column_name):
        raise ValueError("Invalid column name")
    if is_postgresql():
        row = connection.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = :table_name AND column_name = :column_name"
            ),
            {"table_name": table_name, "column_name": column_name},
        ).fetchone()
    else:
        row = connection.execute(f'PRAGMA table_info("{table_name}")')
        row = next((item for item in row if item[1] == column_name), None)
    return row is not None


class _CompatRow:
    def __init__(self, row: Any) -> None:
        self._values = tuple(row)
        self._mapping = dict(row._mapping)

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def keys(self):
        return self._mapping.keys()


class _CompatResult:
    def __init__(self, result: Any) -> None:
        self._result = result
        self.rowcount = result.rowcount

    def fetchone(self) -> _CompatRow | None:
        row = self._result.fetchone()
        return _CompatRow(row) if row is not None else None

    def fetchall(self) -> list[_CompatRow]:
        return [_CompatRow(row) for row in self._result.fetchall()]

    def __iter__(self) -> Iterator[_CompatRow]:
        return iter(self.fetchall())


def _statement_and_params(statement: Any, parameters: Any) -> tuple[Any, Any]:
    if not isinstance(statement, str) or "?" not in statement or not isinstance(parameters, (tuple, list)):
        return statement, parameters
    names = []
    index = 0

    def replace(_match: re.Match[str]) -> str:
        nonlocal index
        name = f"param_{index}"
        names.append(name)
        index += 1
        return f":{name}"

    converted = re.sub(r"\?", replace, statement)
    return text(converted), dict(zip(names, parameters))


class _CompatConnection(AbstractContextManager["_CompatConnection"]):
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def execute(self, statement: Any, parameters: Any = None) -> _CompatResult:
        statement, parameters = _statement_and_params(statement, parameters)
        if isinstance(statement, str):
            statement = text(statement)
        if parameters is None:
            result = self._connection.execute(statement)
        else:
            result = self._connection.execute(statement, parameters)
        return _CompatResult(result)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "_CompatConnection":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


def get_conn() -> _CompatConnection:
    return _CompatConnection(engine.connect())
