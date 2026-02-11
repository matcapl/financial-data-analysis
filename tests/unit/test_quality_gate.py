import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server" / "app" / "services"))

from quality_gate import assess_revenue_analyst_quality


def test_quality_gate_blocks_without_revenue_monthly_series():
    qr = assess_revenue_analyst_quality(normalized_rows=[])
    assert qr.ok_for_revenue_analyst is False
    assert any('Missing monthly Revenue Actual series' in b for b in qr.blockers)


def test_quality_gate_ok_with_two_months_revenue_actuals():
    rows = [
        {"line_item": "Revenue", "period_label": "2025-09", "value_type": "Actual", "value": 1},
        {"line_item": "Revenue", "period_label": "2025-10", "value_type": "Actual", "value": 2},
    ]

    qr = assess_revenue_analyst_quality(normalized_rows=rows, ltm_months=2)
    assert qr.ok_for_revenue_analyst is True
    assert qr.latest_month == "2025-10"
    assert qr.coverage["Revenue"].months_missing == 0


def test_quality_gate_warns_when_budget_missing_for_latest():
    rows = [
        {"line_item": "Revenue", "period_label": "2025-10", "value_type": "Actual", "value": 2},
    ]
    qr = assess_revenue_analyst_quality(normalized_rows=rows, ltm_months=1)
    assert qr.ok_for_revenue_analyst is True
    assert any('Budget' in w for w in qr.warnings)
