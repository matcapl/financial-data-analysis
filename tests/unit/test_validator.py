import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server" / "app" / "services"))

from validator import ValidationReport


def test_validation_report_shape():
    r = ValidationReport(ok=True, issues=[], metrics_checked=["Revenue"]).to_dict()
    assert r["ok"] is True
    assert isinstance(r["issues"], list)
    assert r["metrics_checked"] == ["Revenue"]
