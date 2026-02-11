import sys
from pathlib import Path

# Allow direct import of services modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server" / "app" / "services"))

from ingest_pdf import _extract_month_matrix_table


def test_extract_month_matrix_table_emits_monthly_facts():
    table = [
        ["", "Jan 25", "Feb 25", "Mar 25"],
        ["", "Actual", "Actual", "Actual"],
        ["Revenue", "5,000", "6,000", "7,000"],
        ["Closing Cash", "1,000", "2,000", "3,000"],
    ]

    rows = _extract_month_matrix_table(table, page_index=0, tbl_idx=0)

    # Expect at least revenue + cash across 3 months
    assert len(rows) >= 6

    # Spot-check that a specific month is emitted
    jan_rev = [r for r in rows if r["line_item"] == "Revenue" and r["period_label"] == "2025-01"]
    assert jan_rev
    assert jan_rev[0]["value_type"] == "Actual"

    feb_cash = [r for r in rows if r["line_item"].lower().startswith("closing cash") and r["period_label"] == "2025-02"]
    assert feb_cash


def test_extract_month_matrix_table_ignores_non_month_tables():
    table = [
        ["Metric", "Value"],
        ["Revenue", "5,000"],
    ]

    assert _extract_month_matrix_table(table, page_index=0, tbl_idx=0) == []
