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


def test_quote_identifiers_backticks_only_unsafe_names(tmp_path: Path) -> None:
    db_path = tmp_path / "lab.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        'CREATE TABLE lab (id INTEGER PRIMARY KEY, "T-BIL" REAL, "aCL IgM" REAL, ok TEXT);'
    )
    conn.close()
    plain = get_schema(db_path)
    quoted = get_schema(db_path, quote_identifiers=True)
    assert "T-BIL REAL" in plain and "`T-BIL` REAL" not in plain
    assert "`T-BIL` REAL" in quoted and "`aCL IgM` REAL" in quoted and "ok TEXT" in quoted
    assert quoted.startswith("SQLite schema (names in backticks")
    # Databases with only bare names (Chinook) render identically either way.
    assert get_schema() == get_schema(quote_identifiers=True)


def test_dictionary_notes_from_description_csvs(tmp_path: Path) -> None:
    db_path = tmp_path / "shop" / "shop.sqlite"
    db_path.parent.mkdir()
    conn = sqlite3.connect(db_path)
    conn.executescript(
        'CREATE TABLE sales (id INTEGER PRIMARY KEY, "Unit Price" REAL, kind TEXT, qty INTEGER);'
    )
    conn.close()
    notes = db_path.parent / "database_description"
    notes.mkdir()
    (notes / "Sales.csv").write_bytes(
        (
            "original_column_name,column_name,column_description,data_format,value_description\n"
            "id,id,the id of the sales,integer,\n"
            "Unit Price,unit price,price per unit in euros,real,\n"
            'kind,,the product kind,text,"commonsense evidence:\n A = apparel; F = food"\n'
            "qty,quantity,qty,integer,\n"
        ).encode("cp1252")
    )
    plain = get_schema(db_path)
    rich = get_schema(db_path, quote_identifiers=True, dictionary=True)
    assert "about" not in plain
    assert "about `Unit Price`: price per unit in euros" in rich
    assert "about kind: the product kind; values: commonsense evidence: A = apparel; F = food" in rich
    assert "about id" not in rich  # "the id of the sales" only restates the names
    assert "about qty" not in rich  # description equal to the name adds nothing
    assert get_schema() == get_schema(dictionary=True)  # Chinook has no dictionary files
