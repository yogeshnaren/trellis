from benchmark.bank import majority_correct, pass_at_k


def test_majority_vote_and_ties() -> None:
    assert majority_correct([("a", True), ("b", False), ("a", True)])
    assert not majority_correct([("b", False), ("a", True), ("b", False)])
    assert majority_correct([("a", True), ("b", False)])  # tie: first-listed wins
    assert not majority_correct([(None, False), (None, True)])  # no result, no vote


def test_pass_at_k_over_subsets() -> None:
    bank = [("a", True), ("b", False), ("c", False), ("d", False)]
    assert pass_at_k(bank, 1) == 0.25
    assert pass_at_k(bank, 4) == 1.0
    assert pass_at_k(bank, 2) == 0.5  # 3 of 6 pairs contain the correct candidate
