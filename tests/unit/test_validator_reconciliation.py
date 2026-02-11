import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server" / "app" / "services"))

from validator import _reconcile_ytd


def test_reconcile_ytd_flags_mismatch():
    period = {
        "2025-01": 10.0,
        "2025-02": 10.0,
        "2025-03": 10.0,
    }
    ytd = {
        "2025-02": 100.0,
    }

    issues = _reconcile_ytd(period_series=period, ytd_series=ytd, tolerance_abs=1.0, tolerance_pct=2.0)
    assert issues
    assert issues[0].code == "revenue_ytd_mismatch"


def test_reconcile_ytd_ok_when_within_tolerance():
    period = {
        "2025-01": 10.0,
        "2025-02": 10.0,
    }
    ytd = {
        "2025-02": 20.0,
    }

    issues = _reconcile_ytd(period_series=period, ytd_series=ytd, tolerance_abs=100.0, tolerance_pct=50.0)
    assert issues == []
