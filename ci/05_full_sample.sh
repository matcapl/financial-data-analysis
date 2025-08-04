#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "05 | Running full-sample ingestion report..."
for file in data/*; do
  count_before=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM financial_metrics;")
  curl -fs -F "file=@$file" http://localhost:4000/api/upload
  count_after=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM financial_metrics;")
  added=$((count_after - count_before))
  echo "05 | File $file: added $added row(s)"
done
echo "05 | Full-sample ingestion report complete."
