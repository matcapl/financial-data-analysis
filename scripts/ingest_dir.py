#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure imports work when run from repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'server'))

from server.app.services.pipeline_processor import FinancialDataProcessor


def _iter_files(input_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in sorted(input_dir.rglob('*')):
        if p.is_file() and p.suffix.lower() in {'.pdf', '.xlsx', '.xls', '.csv'}:
            files.append(p)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description='Ingest all supported files in a directory')
    ap.add_argument('input_dir', help='Directory to scan (recursively)')
    ap.add_argument('--company-id', type=int, required=True)
    args = ap.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f'Not a directory: {input_dir}')

    processor = FinancialDataProcessor()

    files = _iter_files(input_dir)
    if not files:
        print('No supported files found')
        return 0

    results: List[Dict[str, Any]] = []
    ok = 0
    fail = 0

    for f in files:
        res = processor.ingest_file(str(f), company_id=args.company_id, document_id=None)
        results.append({"file": str(f), **res.to_dict()})
        if res.success:
            ok += 1
        else:
            fail += 1

    print(f'Files: {len(files)} ok={ok} fail={fail}')
    for r in results:
        status = 'OK' if r.get('success') else 'FAIL'
        msg = r.get('message') or ''
        print(f"[{status}] {Path(r['file']).name}: {msg}")

    if fail:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
