from utils import get_line_item_aliases

TARGET_ITEMS = get_line_item_aliases()  # Load all aliases from YAML

def map_and_filter_row(raw_row: dict) -> dict:
    """Map raw row fields to canonical format, handling datetime objects and aliases"""
    # Handle datetime objects in period_label
    period_label = raw_row.get("period_label")
    if hasattr(period_label, 'strftime'):  # datetime object
        period_label = period_label.strftime('%Y-%m-%d')
    elif period_label is None:
        period_label = ""
    else:
        period_label = str(period_label)
    
    # Handle NaN values in notes
    notes = raw_row.get("notes")
    if notes is None or (hasattr(notes, '__name__') and notes.__name__ == 'nan'):
        notes = ""
    else:
        notes = str(notes)
    
    # Map line_item using aliases from YAML
    raw_line_item = raw_row.get("line_item", "").lower()
    line_item = TARGET_ITEMS.get(raw_line_item, raw_line_item)
    
    return {
        "line_item": line_item,
        "period_label": period_label,
        "period_type": raw_row.get("period_type", "Monthly"),
        "value_type": raw_row.get("value_type", "Actual"),
        "frequency": raw_row.get("frequency", "Monthly"),
        "value": raw_row.get("value"),
        "currency": raw_row.get("currency", "USD"),
        "source_file": raw_row.get("source_file"),
        "source_page": raw_row.get("source_page"),
        "notes": notes
    }