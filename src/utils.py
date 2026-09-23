"""Small dependency-free helpers for ad hoc SQLite exploration."""

import sqlite3
from pathlib import Path
from typing import Any


def load_db(db_path: str = "data/Chinook.db") -> sqlite3.Connection:
    """Open a SQLite database."""
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Database file not found: {db_path}\nRun ./scripts/setup_chinook.sh first."
        )
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def query_db(
    conn: sqlite3.Connection,
    query: str,
    params: tuple[Any, ...] | None = None,
    *,
    return_as_df: bool = False,
) -> list[dict[str, Any]]:
    """Execute a query and return dictionaries.

    ``return_as_df`` is retained for source compatibility, but pandas is intentionally
    kept out of this project's dependency list.
    """
    if return_as_df:
        raise ValueError("DataFrame output is unavailable; use return_as_df=False")
    cursor = conn.execute(query, params or ())
    columns = [description[0] for description in cursor.description or ()]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def get_schema(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Return table and column metadata."""
    tables = query_db(
        conn,
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
    )
    return {
        str(table["name"]): query_db(conn, f'PRAGMA table_info("{table["name"]}")')
        for table in tables
    }


def print_table_schema(conn: sqlite3.Connection, table_name: str | None = None) -> None:
    """Print a compact schema summary."""
    schema = get_schema(conn)
    selected = {table_name: schema[table_name]} if table_name else schema
    for name, columns in selected.items():
        rendered = ", ".join(f"{column['name']} {column['type']}" for column in columns)
        print(f"{name}({rendered})")
