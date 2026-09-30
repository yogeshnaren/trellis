import sqlite3
from pathlib import Path

import pytest

from src.db_profile import build_profile, retrieve_values, text_format


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE studio (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE film (id INTEGER PRIMARY KEY, studio_id INTEGER REFERENCES studio(id),
                           title TEXT, budget TEXT, runtime TEXT, released TEXT);
        CREATE TABLE award (film_id INTEGER REFERENCES film(id), label TEXT);
        INSERT INTO studio VALUES (1, 'Toho'), (2, 'Warner Bros');
        INSERT INTO film VALUES
          (1, 1, 'Godzilla', '$1,000,000.00', '1:36:00', '1954-11-03'),
          (2, 2, 'Bruce Almighty', '$81,000,000.00', NULL, '2003-05-23'),
          (3, 2, 'The Matrix', '$63,000,000.00', '2:16:00', '1999-03-31'),
          (4, 1, 'Mothra', NULL, '1:41:00', '1961-07-30');
        INSERT INTO award VALUES (1, 'Best Effects'), (3, 'Best Editing');
        """
    )
    conn.commit()
    conn.close()
    return path


def test_text_format_needs_a_clear_majority() -> None:
    assert text_format(["$1.00", "$20,000,000.00", "$3"]) == "money"
    assert text_format(["0:17:30", "1:02:00", "0:05:10"]) == "duration"
    assert text_format(["12", "7", "300"]) == "integer-text"
    assert text_format(["$1.00", "Toho", "Warner", "Mothra"]) is None  # mixed: no claim
    assert text_format([]) is None


def test_profile_flags_formats_joins_and_indexes_values(db: Path, tmp_path: Path) -> None:
    profile = build_profile(db, tmp_path / "cache")
    formats = {(c.table, c.column): c.text_format for c in profile.text_formatted()}
    assert formats[("film", "budget")] == "money"  # despite a NULL
    assert formats[("film", "runtime")] == "duration"
    assert formats[("film", "released")] == "date"
    assert ("film", "title") not in formats
    joins = {(j.table, j.column): j.cardinality for j in profile.joins}
    assert joins[("film", "studio_id")] == "1:N"  # a studio has several films
    assert joins[("award", "film_id")] == "1:1"
    assert profile.indexed_values > 0
    # Cached by content: a second build returns the stored profile.
    assert build_profile(db, tmp_path / "cache").build_seconds == profile.build_seconds


def test_retrieve_values_prefers_quoted_phrases(db: Path, tmp_path: Path) -> None:
    profile = build_profile(db, tmp_path / "cache")
    hits = retrieve_values(profile, "Which studio made 'Bruce Almighty'?", k=3)
    assert hits[0] == ("film", "title", "Bruce Almighty")
    assert ("studio", "name", "Toho") in retrieve_values(profile, "films by toho", k=5)
    assert retrieve_values(profile, "?!", k=5) == []


def test_numbers_with_separators_only_on_large_values_are_thousands() -> None:
    from src.db_profile import text_format

    mixed = ["1,963.10", "781.22", "2,004.50", "12", "3,000"] * 4
    assert text_format(mixed) == "thousands"
    assert text_format(["781.22", "12.5", "3.0"] * 4) == "decimal-text"  # no separators: unchanged
    assert text_format(["1,963.10", "abc", "def", "ghi"] * 4) is None  # mostly not numbers
