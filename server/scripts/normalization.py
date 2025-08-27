import os
import re
import yaml
import hashlib
import pandas as pd
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from utils import log_event, get_db_connection

# Load periods.yaml
BASE = Path(__file__).resolve().parent.parent.parent
PERIODS_CFG = yaml.safe_load((BASE / "config" / "periods.yaml").read_text())

# Validate alias uniqueness
if PERIODS_CFG.get("validation", {}).get("strict_alias_uniqueness"):
    seen = {}
    for canon, cfg in PERIODS_CFG["period_aliases"].items():
        for alias in cfg["aliases"]:
            key = alias.lower()
            if key in seen and seen[key] != canon:
                raise ValueError(f"Alias '{alias}' in '{canon}' also in '{seen[key]}'")
            seen[key] = canon

def clean_period_string(raw: Any) -> str:
    s = str(raw).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("–", "-").replace("—", "-")
    return s

def normalize_period_label(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, None
    cleaned = clean_period_string(raw)
    low = cleaned.lower()
    for canon, cfg in PERIODS_CFG["period_aliases"].items():
        if any(low == a.lower() for a in cfg["aliases"]):
            log_event("normalize_alias", {"raw": cleaned, "canonical": canon})
            return canon, cfg["period_type"]
    for section, pats in PERIODS_CFG.get("parsing", {}).get("patterns", {}).items():
        for pat in pats:
            log_event("normalize_pattern_check", {"raw": cleaned, "pattern": pat, "section": section})
            if re.search(pat, cleaned, re.IGNORECASE):
                return _derive_canonical_from_section(cleaned, section)
    log_event("period_normalization_failed", {"raw": cleaned})
    return None, None

def _derive_canonical_from_section(clean: str, section: str) -> Tuple[str, str]:
    if section == "monthly":
        y = re.search(r"(\d{4})", clean).group(1)
        m = re.search(r"\d{1,2}", clean).group(0)
        return f"{y}-{int(m):02d}", "Monthly"
    if section == "quarterly":
        y = re.search(r"(\d{4})", clean).group(1)
        q = re.search(r"[1-4]", clean).group(0)
        return f"{y}-Q{q}", "Quarterly"
    if section == "yearly":
        y = re.search(r"(\d{4})", clean).group(1)
        return y, "Yearly"
    return clean, "Custom"

def normalize_value(raw: Any) -> Optional[Decimal]:
    if raw is None or pd.isna(raw):
        return None
    s = re.sub(r"[$€£¥,\s]", "", str(raw).strip())
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").lstrip("-")
    try:
        val = Decimal(s)
        return -val if neg else val
    except (InvalidOperation, ValueError):
        log_event("value_normalization_failed", {"raw": raw, "clean": s})
        return None

def normalize_text(raw: Any) -> Optional[str]:
    if raw is None or pd.isna(raw):
        return None
    t = str(raw).strip()
    return t if t and t.lower() not in {"nan","none","null"} else None

def create_hash(company_id: int, period_id: int, line_item_id: int,
                value_type: str, source_file: str) -> str:
    """
    Create a unique hash including source_file to allow
    multiple file ingestions of identical data.
    """
    inp = f"{company_id}_{period_id}_{line_item_id}_{value_type}_{source_file}"
    return hashlib.md5(inp.encode()).hexdigest()

def _lookup_or_create_period(label: str, ptype: str) -> Optional[int]:
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM periods WHERE period_label=%s AND period_type=%s",
                (label, ptype)
            )
            r = cur.fetchone()
            if r:
                return r[0]
            if ptype == "Monthly":
                y, m = label.split("-")
                start = f"{y}-{m}-01"
                end = pd.to_datetime(start) + pd.offsets.MonthEnd(1)
            elif ptype == "Quarterly":
                y, q = label.split("-Q")
                q = int(q)
                start = f"{y}-{(q-1)*3+1:02d}-01"
                end = pd.to_datetime(start) + pd.offsets.QuarterEnd(1)
            elif ptype == "Yearly":
                start = f"{label}-01-01"
                end = f"{label}-12-31"
            cur.execute(
                "INSERT INTO periods (period_label,period_type,start_date,end_date,created_at,updated_at)"
                " VALUES (%s,%s,%s,%s,NOW(),NOW()) RETURNING id",
                (label, ptype, start, str(end)[:10])
            )
            pid = cur.fetchone()[0]
            conn.commit()
            return pid
    except Exception as e:
        log_event("period_db_error", {"label": label, "error": str(e)})
        return None

def _lookup_line_item_id(name: str) -> Optional[int]:
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM line_item_definitions WHERE name=%s", (name,))
            r = cur.fetchone()
            if r:
                return r[0]
            cur.execute("SELECT id FROM line_item_definitions WHERE %s = ANY(aliases)", (name,))
            r = cur.fetchone()
            return r[0] if r else None
    except Exception as e:
        log_event("line_item_db_error", {"name": name, "error": str(e)})
        return None

def normalize_data(mapped: List[Dict[str, Any]], src: str) -> Tuple[List[Dict[str, Any]], int]:
    normalized_rows = []
    error_count = 0
    log_event("normalization_started", {"rows": len(mapped), "source": src})

    for idx, row in enumerate(mapped, start=1):
        if not row.get("line_item") or not row.get("period_label") or row.get("value") is None:
            log_event("skip_incomplete", {"row": idx, "data": row})
            error_count += 1
            continue

        canon, ptype = normalize_period_label(row["period_label"])
        if not canon:
            log_event("skip_period", {"row": idx, "raw": row["period_label"]})
            error_count += 1
            continue

        pid = _lookup_or_create_period(canon, ptype)
        if not pid:
            log_event("skip_period_id", {"row": idx, "canon": canon})
            error_count += 1
            continue

        lid = _lookup_line_item_id(row["line_item"])
        if not lid:
            log_event("skip_line_item", {"row": idx, "item": row["line_item"]})
            error_count += 1
            continue

        val = normalize_value(row["value"])
        if val is None:
            log_event("skip_value", {"row": idx, "raw": row["value"]})
            error_count += 1
            continue

        source_file = os.path.basename(src)
        hsh = create_hash(1, pid, lid, row.get("value_type") or "Actual", source_file)

        normalized_rows.append({
            "company_id": 1,
            "period_id": pid,
            "line_item_id": lid,
            "value": float(val),
            "value_type": normalize_text(row.get("value_type")) or "Actual",
            "frequency": normalize_text(row.get("frequency")) or ptype,
            "currency": normalize_text(row.get("currency")) or "USD",
            "source_file": source_file,
            "source_page": row.get("source_page") or row.get("_sheet_name"),
            "notes": normalize_text(row.get("notes")),
            "hash": hsh,
            "_row": idx
        })

    log_event("normalization_completed", {
        "output_rows": len(normalized_rows),
        "errors": error_count
    })
    return normalized_rows, error_count
