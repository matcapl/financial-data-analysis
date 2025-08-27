#!/usr/bin/env python3
"""
generate_periods_yaml.py

Generates a comprehensive `config/periods.yaml` with:
  • ISO 8601 canonicals (Monthly, Quarterly, Yearly) over a multi-year range
  • Rich alias variants per period, matching or exceeding existing manual lists
  • Fallback regex patterns, cleaning rules, and validation

Run this once; check in the generated YAML for CI and reference.
"""

import yaml
from datetime import date, timedelta
from pathlib import Path

# === CONFIGURATION ===
START_YEAR = date.today().year - 10
END_YEAR   = date.today().year + 5

OUTPUT = Path(__file__).resolve().parent.parent / "config" / "Yperiods.yaml"

MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
MONTH_FULL = ["January","February","March","April","May","June","July","August","September","October","November","December"]

# Alias templates for each period type
ALIASES = {
    "Monthly": [
        "{iso}",              # 2025-02
        "{iso_slash}",        # 02/2025
        "{iso_dot}",          # 2025.02
        "{abbr} {year}",      # Feb 2025
        "{full} {year}",      # February 2025
        "{abbr}-{year}",      # Feb-2025
        "{abbr} '{yy}",       # Feb '25
        "{month}/{yy}",       # 2/25
        "{abbr_year}",        # 2025 Feb
        "{yy_abbr}",          # 25-Feb
    ],
    "Quarterly": [
        "{iso}",              # 2025-Q1
        "Q{q} {year}",        # Q1 2025
        "{year} Q{q}",        # 2025 Q1
        "{q}Q{yy}",           # 1Q25
        "{abbr_start}-{abbr_end} {year}",  # Jan-Mar 2025
    ],
    "Yearly": [
        "{iso}",              # 2025
        "FY{yy}",             # FY25
        "FY {year}",          # FY 2025
        "CY{yy}",             # CY25
        "Year {year}",        # Year 2025
    ],
}

periods = {}

# === GENERATE MONTHLY ===
for y in range(START_YEAR, END_YEAR + 1):
    for m in range(1, 13):
        iso        = f"{y}-{m:02d}"
        iso_slash  = f"{m}/{y}"
        iso_dot    = f"{y}.{m:02d}"
        yy         = str(y)[2:]
        abbr       = MONTH_ABBR[m-1]
        full       = MONTH_FULL[m-1]
        abbr_year  = f"{y} {abbr}"
        yy_abbr    = f"{yy}-{abbr}"
        key        = iso
        start_date = f"{iso}-01"
        end_date   = (date(y, m, 1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        entry = {
            "period_type": "Monthly",
            "start_date": start_date,
            "end_date":   end_date.strftime("%Y-%m-%d"),
            "aliases": []
        }
        for tpl in ALIASES["Monthly"]:
            alias = tpl.format(
                iso=iso, iso_slash=iso_slash, iso_dot=iso_dot,
                abbr=abbr, full=full, year=y, yy=yy,
                month=m, abbr_year=abbr_year, yy_abbr=yy_abbr
            )
            entry["aliases"].append(alias)
        periods[key] = entry

# === GENERATE QUARTERLY ===
for y in range(START_YEAR, END_YEAR + 1):
    yy = str(y)[2:]
    for q in range(1, 5):
        iso         = f"{y}-Q{q}"
        abbr_start  = MONTH_ABBR[(q-1)*3]
        abbr_end    = MONTH_ABBR[(q-1)*3 + 2]
        key         = iso
        start_month = (q-1)*3 + 1
        start_date  = f"{y}-{start_month:02d}-01"
        end_month   = start_month + 2
        end_date    = (date(y, end_month, 1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        entry = {
            "period_type": "Quarterly",
            "start_date": start_date,
            "end_date":   end_date.strftime("%Y-%m-%d"),
            "aliases": []
        }
        for tpl in ALIASES["Quarterly"]:
            alias = tpl.format(
                iso=iso, q=q, year=y, yy=yy,
                abbr_start=abbr_start, abbr_end=abbr_end
            )
            entry["aliases"].append(alias)
        periods[key] = entry

# === GENERATE YEARLY ===
for y in range(START_YEAR, END_YEAR + 1):
    iso     = f"{y}"
    yy      = str(y)[2:]
    start   = f"{iso}-01-01"
    end     = f"{iso}-12-31"
    entry = {
        "period_type": "Yearly",
        "start_date": start,
        "end_date":   end,
        "aliases": []
    }
    for tpl in ALIASES["Yearly"]:
        alias = tpl.format(iso=iso, year=y, yy=yy)
        entry["aliases"].append(alias)
    periods[iso] = entry

# === COMPOSE FINAL CONFIG ===
cfg = {
    "metadata": {
        "version":     "3.0",
        "description": "Auto-generated periods.yaml",
        "author":      "generate_periods_yaml.py",
        "timestamp":   date.today().isoformat(),
        "iso_compliant": True
    },
    "canonical_formats": {
        "monthly":   "YYYY-MM",
        "quarterly": "YYYY-QN",
        "yearly":    "YYYY"
    },
    "period_aliases": periods,
    "parsing": {
        "patterns": {
            "monthly":   [r"^\d{4}[-/]\d{2}$", r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}$"],
            "quarterly": [r"^\d{4}-Q[1-4]$", r"^(Q[1-4]|[1-4]Q)\s*\d{4}$"],
            "yearly":    [r"^\d{4}$", r"^(FY|CY)\d{2,4}$"]
        }
    },
    "validation": {
        "strict_alias_uniqueness": True,
        "unknown_period_action":   "log"
    },
    "cleaning": {
        "remove_prefixes":       ["period:", "pd:", "time:"],
        "normalize_whitespace":  True,
        "normalize_punctuation": {"–":"-","—":"-"},
        "case_insensitive":      True
    }
}

# === WRITE TO FILE ===
with open(OUTPUT, "w") as f:
    yaml.safe_dump(cfg, f, sort_keys=False)

print(f"Wrote {OUTPUT} with {len(periods)} canonical periods, each with {len(ALIASES['Monthly'])}+ aliases for months.")
