import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BIRD_DATA = ROOT / "data" / "bird"

# The code and tests use repo-relative paths (data/Chinook.db), as the CLI does.
os.chdir(ROOT)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if BIRD_DATA.is_dir():
        return
    skip = pytest.mark.skip(reason="BIRD data not downloaded (./scripts/setup_bird_minidev.sh)")
    for item in items:
        if "bird_data" in item.keywords:
            item.add_marker(skip)
