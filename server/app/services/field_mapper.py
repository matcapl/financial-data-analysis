# server/scripts/field_mapper.py
# Enhanced with YAML-driven line item and header mapping

import os
import yaml
import re
from app.utils.utils import log_event

CONFIG_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "config")
FIELDS_YAML = os.path.join(CONFIG_DIR, "fields.yaml")
TAXONOMY_YAML = os.path.join(CONFIG_DIR, "taxonomy.yaml")


def load_yaml(path):
    """Load YAML file, logging on error."""
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        log_event("yaml_load_error", {"file": path, "error": str(e)})
        return {}


def load_line_item_mappings() -> dict:
    """
    Build mapping of every alias and canonical line_item name from fields.yaml.
    """
    config = load_yaml(FIELDS_YAML)
    mappings = {}
    for item in config.get("line_items", []):
        name = item.get("name", "")
        canonical = name.strip()
        if not canonical:
            continue
        # map canonical lowercase → canonical
        mappings[canonical.lower()] = canonical
        # map each alias lowercase → canonical
        for alias in item.get("aliases", []):
            mappings[alias.lower().strip()] = canonical
    log_event("line_item_mappings_loaded", {
        "config_file": "fields.yaml",
        "mapping_count": len(mappings),
        "line_items": [i.get("name") for i in config.get("line_items", [])]
    })
    return mappings


def load_taxonomy_patterns() -> list:
    """
    Load header-pattern rules from taxonomy.yaml to augment field mapping.
    Returns list of tuples (field_key, compiled_regex, canonical_field_name).
    """
    patterns = []
    config = load_yaml(TAXONOMY_YAML)
    for entry in config.get("taxonomies", []):
        key = entry.get("name")
        for pat in entry.get("patterns", []):
            try:
                patterns.append((key, re.compile(pat, re.IGNORECASE)))
            except re.error:
                log_event("regex_compile_error", {"pattern": pat})
    return patterns


# Load once for performance
LINE_ITEM_MAP = load_line_item_mappings()
TAXONOMY_PATTERNS = load_taxonomy_patterns()


def map_and_filter_row(raw_row: dict) -> dict:
    """
    Map raw row fields to canonical values:
     - Normalize datetime period_label
     - Map line_item via YAML-driven mapping
     - Optionally infer unmapped headers via taxonomy patterns
    """
    # Normalize period_label
    pl = raw_row.get("period_label")
    if hasattr(pl, "strftime"):
        period_label = pl.strftime("%Y-%m-%d")
    else:
        period_label = str(pl or "").strip()

    # Normalize notes
    notes = raw_row.get("notes")
    if notes is None:
        notes = ""
    else:
        notes = str(notes).strip()

    # Map line_item
    raw_li = str(raw_row.get("line_item", "")).lower().strip()
    canonical_li = LINE_ITEM_MAP.get(raw_li, raw_row.get("line_item"))
    if raw_li in LINE_ITEM_MAP:
        log_event("line_item_mapped", {
            "original": raw_row.get("line_item"),
            "canonical": canonical_li
        })

    # Optionally map unknown headers (e.g. period_type) via taxonomy
    mapped_fields = {}
    for k, v in raw_row.items():
        kl = k.lower().strip()
        mapped_key = None
        # exact synonyms from fields.yaml
        from_fields = load_yaml(FIELDS_YAML).get("fields", {})
        for field_name, meta in from_fields.items():
            if kl in [s.lower() for s in meta.get("synonyms", [])]:
                mapped_key = field_name
                break
        # fallback via taxonomy regex
        if not mapped_key:
            for tax, rx in TAXONOMY_PATTERNS:
                if rx.match(k):
                    mapped_key = tax + "_headers"
                    break
        if mapped_key:
            mapped_fields[mapped_key] = v

    # Build final mapped row
    return {
        "line_item": canonical_li,
        "period_label": period_label,
        "period_type": raw_row.get("period_type", mapped_fields.get("period_type_headers", "Monthly")),
        "value_type": raw_row.get("value_type", mapped_fields.get("scenario_headers", "Actual")),
        "frequency": raw_row.get("frequency", mapped_fields.get("period_type_headers", "Monthly")),
        "value": raw_row.get("value"),
        "currency": raw_row.get("currency", mapped_fields.get("currency_headers", "USD")),
        "source_file": raw_row.get("source_file"),
        "source_page": raw_row.get("source_page"),
        "source_table": raw_row.get("source_table"),
        "source_row": raw_row.get("source_row"),
        "source_col": raw_row.get("source_col"),
        "extraction_method": raw_row.get("extraction_method"),
        "confidence": raw_row.get("confidence"),
        "notes": notes
    }


def get_available_line_items() -> list:
    """Return sorted list of all canonical line items."""
    return sorted(set(LINE_ITEM_MAP.values()))


def reload_mappings():
    """Reload mappings from YAML (for tests or dynamic config)."""
    global LINE_ITEM_MAP, TAXONOMY_PATTERNS
    LINE_ITEM_MAP = load_line_item_mappings()
    TAXONOMY_PATTERNS = load_taxonomy_patterns()
    return LINE_ITEM_MAP


if __name__ == "__main__":
    # Quick sanity check
    print("Line Item Mappings:")
    for alias, canon in sorted(LINE_ITEM_MAP.items()):
        print(f"  '{alias}' → '{canon}'")
    print("\nSample Mapping:")
    sample = {"line_item": "total revenue", "period_label": "Feb 2025"}
    print(map_and_filter_row(sample))
    print("\nAvailable Items:", get_available_line_items())
