#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi
: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "06 | Validating calculated metrics..."

# Assumes data already ingested, run calc_metrics
python server/scripts/calc_metrics.py 1

# Assert specific calculated values
REVENUE_MOM=$(psql "$DATABASE_URL" -t -c "
  SELECT ROUND(metric_value, 2) 
  FROM derived_metrics dm
  JOIN line_item_definitions li ON dm.base_metric_id=li.id
  WHERE li.name='Revenue' AND dm.calculation_type='MoM'
  LIMIT 1;
" | tr -d '[:space:]')

if [[ "$REVENUE_MOM" != "19.52" ]]; then
  echo "06 | Metric validation FAILED: Revenue MoM expected 19.52, got $REVENUE_MOM"
  exit 1
fi

echo "06 | Metric validation passed: Revenue MoM=$REVENUE_MOM"