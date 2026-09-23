from src.schema import get_identifier_allowlist, get_schema, table_count


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
