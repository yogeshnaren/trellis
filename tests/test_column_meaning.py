from benchmark.column_meaning import ColumnMeanings, clean, render

ENTRIES = {
    "movie|characters|screentime": "The 'screentime' column in the 'characters' table of the "
    "'movie' database stores the on-screen duration as text formatted 'hh:mm:ss'.",
    "movie|movie|Title": "The 'Title' column in the 'movie' table of the 'movie' database "
    "stores the movie's name.",
    "movie|actor|Height (Inches)": "Height of the actor in inches.",
    "other|t|Title": "Belongs to another database.",
}


def test_clean_drops_preamble_and_clips() -> None:
    assert clean(ENTRIES["movie|movie|Title"]) == "Stores the movie's name."
    assert clean("x " * 400).endswith("…")


def test_select_is_per_database_and_relevance_ranked() -> None:
    meanings = ColumnMeanings(ENTRIES)
    picked = meanings.select("movie", "Which character has the longest screen time?",
                             "movie title 'Batman'", 2)
    # "screen time" matches the compound name `screentime`; the Height column is not picked.
    assert {(t, c) for t, c, _ in picked} == {("characters", "screentime"), ("movie", "Title")}
    assert all(t != "t" for t, _, _ in meanings.select("movie", "title", "", 5))
    assert meanings.select("movie", "zzz", "", 5) == []
    assert render([]) == ""
    assert render(picked).startswith("Notes on possibly relevant columns")
