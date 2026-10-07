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


def test_prose_in_sql_field_is_rejected_not_raised() -> None:
    # A model once put an English sentence with a stray quote in the sql field; the
    # tokenizer error crashed the benchmark instead of becoming a (repairable) rejection.
    safe, reason = is_safe("The database returns zero rows when nothing matches. 'x", db_path=DB_PATH)
    assert not safe and reason.startswith("SQL parse failed")


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
        "SELECT readfile('/etc/passwd')",
        "SELECT * FROM pragma_table_info('Artist')",
        "ATTACH DATABASE 'other.db' AS other",
        "DETACH DATABASE main",
        "VACUUM INTO 'copy.db'",
        "WITH x AS (SELECT 1) INSERT INTO Artist (Name) SELECT * FROM x",
        "INSERT INTO Artist (Name) VALUES ('x') RETURNING ArtistId",
        "REPLACE INTO Artist VALUES (1, 'x')",
        "UPDATE Artist SET Name = 'x'",
        "CREATE TABLE copy AS SELECT * FROM Artist",
        "EXPLAIN DELETE FROM Artist",
        "BEGIN; DELETE FROM Artist; COMMIT",
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


def test_execute_caps_rows_by_default(conn: sqlite3.Connection) -> None:
    _, rows, truncated = execute(conn, "SELECT TrackId FROM Track")
    assert len(rows) == 200 and truncated
    _, rows, truncated = execute(conn, "SELECT TrackId FROM Track", limit=None)
    assert len(rows) == 3503 and not truncated


# The connection has three independent write defenses (read-only open, PRAGMA query_only,
# and an authorizer). Each test below switches the others off so it fails if its layer goes.


@pytest.mark.parametrize(
    "sql", ["DELETE FROM Artist", "CREATE TEMP TABLE scratch (x)", "PRAGMA table_info(Artist)"]
)
def test_authorizer_denies_writes_and_pragmas(conn: sqlite3.Connection, sql: str) -> None:
    # The read-only open would also stop DELETE, but with "attempt to write a readonly
    # database"; "not authorized" can only come from the authorizer.
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        conn.execute(sql)


def test_extension_loading_is_disabled(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.OperationalError, match="not authorized"):
        conn.load_extension("bad")


def test_query_only_blocks_temp_writes_that_a_read_only_open_allows(
    conn: sqlite3.Connection,
) -> None:
    conn.set_authorizer(None)
    assert conn.execute("PRAGMA query_only").fetchone() == (1,)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("CREATE TEMP TABLE scratch (x)")


def test_read_only_open_blocks_writes_without_the_other_layers(conn: sqlite3.Connection) -> None:
    conn.set_authorizer(None)
    conn.execute("PRAGMA query_only = OFF")
    conn.execute("CREATE TEMP TABLE scratch (x)")  # only the main database is read-only
    with pytest.raises(sqlite3.OperationalError, match="readonly database"):
        conn.execute("DELETE FROM Artist")


def test_runaway_query_is_interrupted_at_the_timeout() -> None:
    import threading
    import time

    conn = connect_readonly(DB_PATH, timeout_seconds=0.2)
    # Watchdog: if the timeout is broken, stop the query after 3s so the test fails, not hangs.
    watchdog = threading.Timer(3.0, conn.interrupt)
    watchdog.start()
    started = time.monotonic()
    try:
        with pytest.raises(sqlite3.OperationalError, match="interrupted"):
            execute(conn, "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) "
                          "SELECT COUNT(*) FROM n")
    finally:
        watchdog.cancel()
        conn.close()
    assert time.monotonic() - started < 2


def test_result_signature_matches_bird_set_equality() -> None:
    from src.db import result_signature

    cases = [
        ([(1, "a")], [(1.0, "a")]),  # set equality ignores int vs integer-valued float
        ([(0,)], [(-0.0,)]),
        ([(2,), (1,), (1,)], [(1.0,), (2.0,)]),  # order and duplicates too
    ]
    for left, right in cases:
        assert set(left) == set(right)
        assert result_signature(left) == result_signature(right)
    # Results BIRD scores as different must stay different.
    assert result_signature([(1.5,)]) != result_signature([(1,)])
    assert result_signature([("1",)]) != result_signature([(1,)])
    assert result_signature([(None,)]) != result_signature([(0,)])


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
