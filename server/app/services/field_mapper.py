# Canonical module: server/app/services/field_mapper.py
# Enhanced with YAML-driven line item and header mapping

import os
import yaml
import re
from pathlib import Path
from app.utils.utils import log_event

# Config lives at repo root: <repo>/config
BASE = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = BASE / "config"
FIELDS_YAML = str(CONFIG_DIR / "fields.yaml")
TAXONOMY_YAML = str(CONFIG_DIR / "taxonomy.yaml")
COMPANY_OVERRIDES_YAML = str(CONFIG_DIR / "company_overrides.yaml")


def load_yaml(path):
    """Load YAML file, logging on error."""
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        log_event("yaml_load_error", {"file": path, "error": str(e)})
        return {}


def load_line_item_mappings() -> dict:
    """Build mapping of alias->canonical from fields.yaml."""
    config = load_yaml(FIELDS_YAML)
    mappings = {}
    for item in config.get("line_items", []):
        name = item.get("name", "")
        canonical = name.strip()
        if not canonical:
            continue
        mappings[canonical.lower()] = canonical
        for alias in item.get("aliases", []):
            if not isinstance(alias, str):
                continue
            mappings[alias.lower().strip()] = canonical
    log_event(
        "line_item_mappings_loaded",
        {
            "config_file": "fields.yaml",
            "mapping_count": len(mappings),
            "line_items": [i.get("name") for i in config.get("line_items", [])],
        },
    )
    return mappings


def load_company_overrides() -> dict:
    """Load per-company alias overrides (best-effort)."""
    overrides = load_yaml(COMPANY_OVERRIDES_YAML) or {}
    if not isinstance(overrides, dict):
        return {}
    return overrides


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
FIELDS_CONFIG = load_yaml(FIELDS_YAML).get("fields", {})
LINE_ITEM_MAP = load_line_item_mappings()
TAXONOMY_PATTERNS = load_taxonomy_patterns()
COMPANY_OVERRIDES = load_company_overrides()


def map_and_filter_row(raw_row: dict) -> dict:
    """
    Map raw row fields to canonical values:
     - Normalize datetime period_label
     - Map line_item via YAML-driven mapping
     - Optionally infer unmapped headers via taxonomy patterns
    """
    # Normalize raw keys for synonym lookup
    raw_by_key = {str(k).lower().strip(): v for k, v in raw_row.items()}

    def _get_field(field_name: str):
        meta = FIELDS_CONFIG.get(field_name, {})
        for syn in meta.get("synonyms", []):
            k = str(syn).lower().strip()
            if k in raw_by_key and raw_by_key[k] not in (None, ""):
                return raw_by_key[k]
        # Also allow exact canonical key
        if field_name in raw_row and raw_row[field_name] not in (None, ""):
            return raw_row[field_name]
        return None

    # Normalize period_label (supports synonyms)
    pl = _get_field("period_label")
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

    # Map line_item (supports synonyms like "Metric Name")
    raw_li = str(_get_field("line_item") or "").strip()
    raw_li_low = raw_li.lower()

    # Drop obvious non-line-items early (prevents DB pollution)
    if not raw_li or len(raw_li) < 2:
        return None

    if raw_li_low.startswith('*') or raw_li_low.startswith('•'):
        return None

    # Common junk patterns from board pack prose/footers
    if any(x in raw_li_low for x in [
        'safety', 'disclaimer', 'copyright', 'confidential', 'contents', 'agenda',
        'prepared by', 'page ', 'source:', 'note:', 'notes:', 'total for',
        'education:',
    ]):
        return None

    # Must contain at least one letter (avoid stray numeric tokens)
    if not re.search(r"[a-zA-Z]", raw_li):
        return None

    canonical_li = LINE_ITEM_MAP.get(raw_li_low)

    # Apply per-company overrides (Companies House number preferred)
    if canonical_li is None and COMPANY_OVERRIDES:
        co_house = None
        # allow callers to pass through company context
        if isinstance(raw_row.get("companies_house_number"), str):
            co_house = raw_row.get("companies_house_number")
        elif raw_row.get("company") and isinstance(raw_row.get("company"), str):
            co_house = raw_row.get("company")

        if co_house:
            try:
                aliases = (
                    COMPANY_OVERRIDES.get("companies_house", {})
                    .get(str(co_house), {})
                    .get("line_item_aliases", {})
                )
                if isinstance(aliases, dict):
                    canonical_li = aliases.get(raw_li_low)
            except Exception:
                pass

    # For v0.x: only persist canonical line items we explicitly know.
    if canonical_li is None:
        return None

    # Hard guard: never allow obviously non-financial phrases through even if they collide with aliases.
    if canonical_li in {'Revenue', 'Gross Profit', 'EBITDA'} and raw_li_low not in LINE_ITEM_MAP:
        # If it mapped indirectly (shouldn't happen), drop it.
        return None

    log_event("line_item_mapped", {
        "original": raw_row.get("line_item"),
        "canonical": canonical_li
    })

    # Optionally map unknown headers (e.g. period_type) via taxonomy
    mapped_fields = {}
    from_fields = FIELDS_CONFIG
    for k, v in raw_row.items():
        kl = k.lower().strip()
        mapped_key = None
        # exact synonyms from fields.yaml
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
        "period_type": raw_row.get("period_type", mapped_fields.get("period_type_headers", _get_field("period_type") or "Monthly")),
        "period_scope": raw_row.get("period_scope"),
        "value_type": raw_row.get("value_type", mapped_fields.get("scenario_headers", _get_field("value_type") or "Actual")),
        "frequency": raw_row.get("frequency", mapped_fields.get("period_type_headers", _get_field("frequency") or "Monthly")),
        "value": raw_row.get("value") if raw_row.get("value") is not None else _get_field("value"),
        "currency": raw_row.get("currency", mapped_fields.get("currency_headers", _get_field("currency") or "USD")),
        "source_file": raw_row.get("source_file") or _get_field("source_file"),
        "source_page": raw_row.get("source_page") or _get_field("source_page"),
        "context_key": raw_row.get("context_key"),
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
