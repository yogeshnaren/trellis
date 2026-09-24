import sqlite3
from pathlib import Path

from src.schema import get_foreign_keys, get_identifier_allowlist, get_schema, table_count


def test_schema_is_compact_and_cached() -> None:
    # Schema text is cached by resolved path; clear so year-sample changes are visible.
    from src.schema import _schema_text

    _schema_text.cache_clear()
    first = get_schema()
    second = get_schema()
    assert first is second
    assert "Artist(" in first
    assert "Foreign keys:" in first
    assert "sample InvoiceDate year:" in first
    assert len(first.split()) < 1_500
    assert table_count() == 11


def test_identifier_allowlist() -> None:
    allowlist = get_identifier_allowlist()
    assert "artist" in allowlist
    assert "name" in allowlist["artist"]


def _assert_edges_resolve(db_path: Path) -> None:
    allowlist = get_identifier_allowlist(db_path)
    for table, column, parent, parent_column in get_foreign_keys(db_path):
        assert column.casefold() in allowlist[table.casefold()], (table, column)
        assert parent_column.casefold() in allowlist[parent.casefold()], (parent, parent_column)
    assert ".None" not in get_schema(db_path)


def test_implicit_composite_duplicate_and_case_mismatched_foreign_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "fk.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Country (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE period (year INTEGER, month INTEGER, PRIMARY KEY (year, month));
        CREATE TABLE sale (
            id INTEGER PRIMARY KEY,
            country_id INTEGER REFERENCES country,
            year INTEGER, month INTEGER,
            FOREIGN KEY (year, month) REFERENCES period,
            FOREIGN KEY (country_id) REFERENCES Country (id)
        );
        """
    )
    conn.close()
    assert get_foreign_keys(db_path) == (
        ("sale", "country_id", "Country", "id"),
        ("sale", "month", "period", "month"),
        ("sale", "year", "period", "year"),
    )
    _assert_edges_resolve(db_path)


def test_every_rendered_foreign_key_resolves_on_real_databases() -> None:
    databases = [Path("data/Chinook.db"), *sorted(Path("data/bird/dev_databases").glob("*/*.sqlite"))]
    for db_path in databases:
        if db_path.exists():
            _assert_edges_resolve(db_path)
