import csv
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_tracker_path() -> Path:
    return FIXTURE_DIR / "sample_tracker.csv"


@pytest.fixture
def sample_tracker_rows(sample_tracker_path: Path) -> list[dict[str, str]]:
    with open(sample_tracker_path, "r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
