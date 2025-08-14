# server/scripts/field_mapper.py - Enhanced with YAML-driven line item mapping
import yaml
from utils import log_event


def load_line_item_mappings() -> dict:
    """Load line item aliases from existing config/fields.yaml instead of hard-coded TARGET_ITEMS"""
    try:
        with open('config/fields.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Extract line item mappings from the line_items section
        mappings = {}
        line_items = config.get('line_items', [])
        
        for item in line_items:
            name = item.get('name', '')
            aliases = item.get('aliases', [])
            
            # Map canonical name to itself (lowercase)
            canonical_lower = name.lower()
            mappings[canonical_lower] = name
            
            # Map all aliases to canonical name (lowercase keys)
            for alias in aliases:
                alias_lower = alias.lower()
                mappings[alias_lower] = name
                
        log_event("line_item_mappings_loaded", {
            "config_file": "config/fields.yaml",
            "mapping_count": len(mappings),
            "line_items": [item.get('name') for item in line_items]
        })
        
        return mappings
        
    except Exception as e:
        log_event("line_item_mappings_error", {"error": str(e)})
        # Fallback to minimal mappings if YAML fails
        return {
            "revenue": "Revenue",
            "sales": "Revenue",
            "gross profit": "Gross Profit", 
            "ebitda": "EBITDA",
            "cashflow": "EBITDA"
        }


# Load mappings once at module level for performance
TARGET_ITEMS = load_line_item_mappings()


def map_and_filter_row(raw_row: dict) -> dict:
    """
    Map raw row fields to canonical format, handling datetime objects
    Now uses YAML-driven line item mapping instead of hard-coded TARGET_ITEMS
    """
    
    # Handle datetime objects in period_label
    period_label = raw_row.get("period_label")
    if hasattr(period_label, 'strftime'): # datetime object
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
    
    # Map line item using YAML-driven mappings instead of hard-coded
    raw_line_item = raw_row.get("line_item", "").lower().strip()
    canonical_line_item = TARGET_ITEMS.get(raw_line_item, raw_row.get("line_item"))
    
    # Log if mapping occurred
    if raw_line_item in TARGET_ITEMS and TARGET_ITEMS[raw_line_item] != raw_row.get("line_item"):
        log_event("line_item_mapped", {
            "original": raw_row.get("line_item"),
            "canonical": canonical_line_item,
            "yaml_driven": True
        })
    
    mapped_row = {
        "line_item": canonical_line_item,
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
    
    return mapped_row


def get_available_line_items() -> list:
    """Get list of all available canonical line items from YAML config"""
    unique_items = set(TARGET_ITEMS.values())
    return sorted(list(unique_items))


def reload_mappings():
    """Reload mappings from YAML file (useful for testing or config changes)"""
    global TARGET_ITEMS
    TARGET_ITEMS = load_line_item_mappings()
    return TARGET_ITEMS


if __name__ == "__main__":
    # Test the YAML-driven mapping
    print("YAML-driven Line Item Mappings:")
    for alias, canonical in sorted(TARGET_ITEMS.items()):
        print(f"  '{alias}' -> '{canonical}'")
    
    print(f"\nTotal mappings: {len(TARGET_ITEMS)}")
    print(f"Canonical line items: {get_available_line_items()}")
    
    # Test sample row
    test_row = {
        "line_item": "total revenue",
        "period_label": "Feb 2025",
        "value": "1,000,000",
        "value_type": "Actual"
    }
    
    print(f"\nTest mapping:")
    print(f"Input: {test_row}")
    mapped = map_and_filter_row(test_row)
    print(f"Output: {mapped}")