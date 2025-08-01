TARGET_ITEMS = {
    "revenue": "Revenue",
    "sales": "Revenue",
    "gross profit": "Gross Profit",
    "ebitda": "EBITDA",
    "cashflow": "EBITDA"
}

def map_and_filter_row(raw_row: dict) -> dict | None:
    """
    Given a raw_row dict with arbitrary keys, return a cleaned dict
    only if the line_item matches one of TARGET_ITEMS. Otherwise None.
    """
    # Normalize raw line_item text
    item_raw = str(
        raw_row.get("line_item") or
        raw_row.get("category") or
        raw_row.get("statement_type", "")
    ).strip().lower()

    for key, canonical in TARGET_ITEMS.items():
        if key in item_raw:
            # Build cleaned row
            return {
                "period_label": raw_row.get("period_label"),
                "period_type": raw_row.get("period_type"),
                "value_type": raw_row.get("value_type"),
                "frequency": raw_row.get("frequency"),
                "line_item": canonical,
                "value": raw_row.get("value"),
                "currency": raw_row.get("currency"),
                "source_file": raw_row.get("source_file"),
                "source_page": raw_row.get("source_page"),
                "notes": raw_row.get("notes")
            }
    return None