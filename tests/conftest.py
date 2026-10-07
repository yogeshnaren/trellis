import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BIRD_DATA = ROOT / "data" / "bird"

# The code and tests use repo-relative paths (data/Chinook.db), as the CLI does.
os.chdir(ROOT)


@pytest.fixture(autouse=True)
def isolated_database_hash_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # database_fingerprint() defaults to data/bird/.db_hash_cache.json; a test writing there
    # would create data/bird on a machine without BIRD data and un-skip the bird_data tests.
    from benchmark.bird import database_fingerprint

    monkeypatch.setattr(database_fingerprint, "__defaults__", (tmp_path / "db_hash_cache.json",))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if BIRD_DATA.is_dir():
        return
    skip = pytest.mark.skip(reason="BIRD data not downloaded (./scripts/setup_bird_minidev.sh)")
    for item in items:
        if "bird_data" in item.keywords:
            item.add_marker(skip)
