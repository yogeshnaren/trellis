from pathlib import Path

from benchmark import profile_context
from src.db_profile import ColumnProfile, DatabaseProfile, JoinFact


def test_profile_facts_are_bounded_and_require_relevant_exact_values(monkeypatch) -> None:
    profile = DatabaseProfile(
        fingerprint="sample",
        version=2,
        columns=[
            ColumnProfile(
                table="actor",
                column="NetWorth",
                declared="TEXT",
                storage={"text": 1.0},
                null_rate=0.0,
                distinct=2,
                text_format="money",
                examples=("$20,000.00",),
            ),
            ColumnProfile(
                table="actor",
                column="Unrelated",
                declared="TEXT",
                storage={"text": 1.0},
                null_rate=0.0,
                distinct=2,
                text_format="date",
                examples=("2026-01-01",),
            ),
        ],
        joins=[
            JoinFact(
                table="actor",
                column="movie_id",
                parent_table="movie",
                parent_column="id",
                parent_unique=False,
                max_children=3,
                cardinality="N:M",
            ),
        ],
        build_seconds=0.1,
        index_path=str(Path("/unused")),
    )
    monkeypatch.setattr(
        profile_context,
        "retrieve_values",
        lambda _profile, _text, k: [
            ("actor", "Name", "Tom Cruise"),
            ("characters", "Name", "Tom"),
        ],
    )
    facts = profile_context.render_profile_facts(
        profile, "What is Tom Cruise's net worth?", "actor 'Tom Cruise'"
    )
    assert "actor.NetWorth: stored as text with money formatting" in facts
    assert "actor.Name" in facts
    assert "Stored value 'Tom' " not in facts
    assert "Unrelated" not in facts
    assert facts.count("\n- ") <= 4

    assert profile_context.render_profile_facts(profile, "How many rows?", "") == ""


def test_subgroup_rates_keep_half_correct_repeat_scores() -> None:
    from benchmark.analyze import _flip_rows

    row = _flip_rows("sample", [1, 2], {1: 1.0, 2: 0.5}, {1: 1.0, 2: 1.0})
    assert "| 75.0% | 100.0% | +25.0 |" in row


def test_profile_facts_do_not_substitute_case_or_ambiguous_locations(monkeypatch) -> None:
    profile = DatabaseProfile(
        fingerprint="sample",
        version=2,
        columns=[],
        joins=[],
        build_seconds=0.0,
        index_path="/unused",
    )
    monkeypatch.setattr(
        profile_context,
        "retrieve_values",
        lambda _profile, _text, k: [
            ("location", "street_name", "19th st"),
            ("location", "city", "sunnyvale"),
            ("generalinfo", "city", "sunnyvale"),
        ],
    )
    facts = profile_context.render_profile_facts(
        profile, "Which restaurant is on '19th St'?", "city = 'sunnyvale'"
    )
    assert facts == ""


def test_profile_facts_default_to_benchmark_only(monkeypatch) -> None:
    import sys

    from benchmark.run_bird import parse_args

    monkeypatch.setattr(sys, "argv", ["run_bird", "--prompt-profile", "benchmark"])
    assert parse_args().profile_facts is True
    monkeypatch.setattr(
        sys, "argv", ["run_bird", "--prompt-profile", "benchmark", "--no-profile-facts"]
    )
    assert parse_args().profile_facts is False
    monkeypatch.setattr(sys, "argv", ["run_bird", "--prompt-profile", "product"])
    assert parse_args().profile_facts is False
