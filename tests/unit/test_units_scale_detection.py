import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server" / "app" / "services"))

from normalization import _detect_value_scale
from ingest_pdf import _detect_units_label


def test_detect_units_label_handles_pound_thousands_variants():
    assert _detect_units_label("All figures in £000") == "£000"
    assert _detect_units_label("All figures in £'000") == "£000"


def test_detect_value_scale_handles_pound_thousands_variants():
    row = {"notes": "[units=£000]"}
    assert _detect_value_scale(row) == 1000

    row2 = {"notes": "All figures in £'000"}
    assert _detect_value_scale(row2) == 1000
