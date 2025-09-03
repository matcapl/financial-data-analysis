#!/usr/bin/env python3
import yaml
from pathlib import Path
from datetime import datetime

# Paths
YAML_PATH = Path(__file__).resolve().parent.parent / "config" / "periods.yaml"
OUT_PATH = Path(__file__).resolve().parent.parent / "database" / "migrations" / "003a_create_and_seed_periods.sql"

# Load YAML
with open(YAML_PATH) as f:
    cfg = yaml.safe_load(f)
periods = cfg.get("period_aliases", {})

lines = []
lines.append("-- Auto-generated migration to create and seed periods table")
lines.append(f"-- Generated on {datetime.utcnow().isoformat()}Z")
lines.append("BEGIN;")
lines.append("")
lines.append("-- 1. Create table")
lines.append("CREATE TABLE IF NOT EXISTS periods (")
lines.append("  id            SERIAL PRIMARY KEY,")
lines.append("  period_label  TEXT   NOT NULL UNIQUE,")
lines.append("  period_type   TEXT   NOT NULL,")
lines.append("  start_date    DATE   NOT NULL,")
lines.append("  end_date      DATE   NOT NULL,")
lines.append("  created_at    TIMESTAMP NOT NULL DEFAULT now(),")
lines.append("  updated_at    TIMESTAMP NOT NULL DEFAULT now()")
lines.append(");")
lines.append("")
lines.append("-- 2. Seed table from periods.yaml")
# Collect batch inserts in groups of e.g. 100 for readability
insert_prefix = "INSERT INTO periods (period_label, period_type, start_date, end_date) VALUES"
values = []
for label, props in periods.items():
    pt = props["period_type"].replace("'", "''")
    sd = props["start_date"]
    ed = props["end_date"]
    values.append(f"  ('{label}','{pt}','{sd}','{ed}')")

if values:
    # Join with commas and add ON CONFLICT clause
    lines.append(insert_prefix)
    lines.extend([v + "," for v in values[:-1]])
    lines.append(values[-1] + " ON CONFLICT (period_label) DO NOTHING;")
lines.append("")
lines.append("COMMIT;")

# Write to migration file
OUT_PATH.write_text("\n".join(lines))
print(f"Wrote migration to {OUT_PATH} with {len(values)} period rows.")
