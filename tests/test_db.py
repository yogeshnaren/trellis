import sqlite3
from pathlib import Path

import pytest

from src.db import connect_readonly, execute, is_safe, validate

DB_PATH = Path("data/Chinook.db")


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = connect_readonly(DB_PATH)
    yield connection
    connection.close()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT Name FROM Artist LIMIT 2",
        (
            "WITH counts AS (SELECT GenreId, COUNT(*) AS n FROM Track GROUP BY GenreId) "
            "SELECT GenreId, n FROM counts"
        ),
        "SELECT ';' AS Name",
        "SELECT Name FROM Artist -- harmless comment",
        # Shadowed CTE alias: outer c is CTE, inner c is Customer — must not overwrite.
        (
            "WITH counts AS ("
            "SELECT c.CustomerId, COUNT(*) AS genre_count FROM Customer c GROUP BY c.CustomerId"
            ") SELECT c.CustomerId FROM counts c WHERE c.genre_count > 1"
        ),
        # Derived subquery alias columns.
        (
            "SELECT t.Name FROM Track t JOIN ("
            "SELECT TrackId, COUNT(*) AS n FROM PlaylistTrack GROUP BY TrackId"
            ") pt ON t.TrackId = pt.TrackId WHERE pt.n > 1"
        ),
    ],
)
def test_safe_queries(sql: str) -> None:
    assert is_safe(sql, db_path=DB_PATH)[0]


def test_shadowed_cte_alias_is_executable(conn: sqlite3.Connection) -> None:
    sql = (
        "WITH counts AS ("
        "SELECT c.CustomerId, COUNT(*) AS genre_count FROM Customer c GROUP BY c.CustomerId"
        ") SELECT c.CustomerId FROM counts c WHERE c.genre_count >= 1 LIMIT 1"
    )
    assert is_safe(sql, db_path=DB_PATH) == (True, "")
    assert validate(conn, sql) == (True, "")
    columns, rows, _ = execute(conn, sql, limit=1)
    assert columns == ["CustomerId"]
    assert rows


def test_derived_subquery_alias_is_executable(conn: sqlite3.Connection) -> None:
    sql = (
        "SELECT t.Name FROM Track t JOIN ("
        "SELECT TrackId, COUNT(*) AS n FROM PlaylistTrack GROUP BY TrackId"
        ") pt ON t.TrackId = pt.TrackId WHERE pt.n > 1 LIMIT 1"
    )
    assert is_safe(sql, db_path=DB_PATH) == (True, "")
    assert validate(conn, sql) == (True, "")
    columns, rows, _ = execute(conn, sql, limit=1)
    assert columns == ["Name"]
    assert rows


def test_correlated_subquery_outer_alias_is_safe() -> None:
    sql = (
        "SELECT a.Name FROM Artist a WHERE NOT EXISTS ("
        "SELECT 1 FROM Album al WHERE al.ArtistId = a.ArtistId"
        ")"
    )
    assert is_safe(sql, db_path=DB_PATH) == (True, "")


def test_unaliased_scalar_derived_table_is_safe() -> None:
    sql = (
        "SELECT t.Name FROM Track t JOIN PlaylistTrack pt ON t.TrackId = pt.TrackId "
        "GROUP BY t.TrackId, t.Name HAVING COUNT(pt.PlaylistId) > ("
        "SELECT AVG(playlist_count) FROM ("
        "SELECT COUNT(pt2.PlaylistId) AS playlist_count "
        "FROM Track t2 LEFT JOIN PlaylistTrack pt2 ON t2.TrackId = pt2.TrackId "
        "GROUP BY t2.TrackId"
        ")"
        ")"
    )
    assert is_safe(sql, db_path=DB_PATH) == (True, "")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM Artist",
        "SELECT Name FROM Artist; SELECT Name FROM Album",
        "SELECT Name FROM Imaginary",
        "SELECT FakeColumn FROM Artist",
        "PRAGMA table_info(Artist)",
        "SELECT load_extension('bad')",
    ],
)
def test_unsafe_queries(sql: str) -> None:
    assert not is_safe(sql, db_path=DB_PATH)[0]


def test_validate_and_execute(conn: sqlite3.Connection) -> None:
    assert validate(conn, "SELECT Name FROM Artist LIMIT 2") == (True, "")
    assert not validate(conn, "SELECT Missing FROM Artist")[0]
    columns, rows, truncated = execute(conn, "SELECT Name FROM Artist", limit=2)
    assert columns == ["Name"]
    assert len(rows) == 2
    assert truncated


def test_sqlite_authorizer_denies_writes(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM Artist")


def test_execute_candidate_needs_no_gold_and_keeps_safety() -> None:
    from src.db import execute_candidate

    conn = connect_readonly()
    try:
        full = execute_candidate(conn, "SELECT TrackId FROM Track")
        assert full.ok and full.row_count > 200  # no product row cap
        reordered = execute_candidate(conn, "SELECT TrackId FROM Track ORDER BY TrackId DESC")
        assert reordered.signature == full.signature
        rejected = execute_candidate(conn, "DELETE FROM Track")
        assert not rejected.ok and rejected.error and rejected.error.startswith("safety-rejected")
        assert rejected.signature is None
        broken = execute_candidate(conn, "SELECT Nope FROM Track")
        assert not broken.ok and broken.signature is None
    finally:
        conn.close()


def test_score_bird_keeps_candidate_signature_when_gold_fails() -> None:
    from benchmark.evaluate import score_bird

    conn = connect_readonly()
    try:
        score = score_bird(conn, "q", "SELECT Nope FROM Track", "SELECT 1", delivered=True)
        assert score.signature is not None and not score.official_ex
    finally:
        conn.close()
