# Canonical module: server/app/services/extraction.py
import pandas as pd
import openpyxl
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Path insert not needed, utils is in same directory
from app.utils.utils import log_event


def _clean_header_cell(value: Any, col_idx: int) -> str:
    if value is None:
        return f"col_{col_idx}"
    text = str(value).strip().replace('\n', ' ').replace('\r', ' ')
    if not text or text.lower().startswith('unnamed:'):
        return f"col_{col_idx}"
    return text


def _make_unique_headers(headers: List[str]) -> List[str]:
    """Ensure column headers are unique so df[col] is scalar, not a Series."""
    seen: dict[str, int] = {}
    out: List[str] = []
    for h in headers:
        base = str(h)
        n = seen.get(base, 0)
        if n == 0:
            out.append(base)
        else:
            out.append(f"{base}__{n}")
        seen[base] = n + 1
    return out


def _row_score_for_header(row_values: List[Any]) -> Tuple[int, int, int, int]:
    """Return a score tuple (datelike, texty, non_empty, negative_numeric).

    We prefer header rows that look like period axes (many date-like cells) plus
    some text labels, and we actively avoid choosing a dense numeric data row.
    """

    non_empty = 0
    texty = 0
    datelike = 0
    numeric = 0

    for v in row_values:
        if v is None:
            continue
        s = str(v).strip()
        if not s or s.lower() in {'nan', 'none', 'null'}:
            continue

        non_empty += 1

        is_numeric = False
        try:
            float(s.replace(',', ''))
            is_numeric = True
        except Exception:
            is_numeric = False

        if is_numeric:
            numeric += 1

        if any(ch.isalpha() for ch in s) and not is_numeric:
            texty += 1

        try:
            dt = pd.to_datetime(s, errors='coerce')
            if pd.notna(dt):
                datelike += 1
        except Exception:
            pass

    return datelike, texty, non_empty, -numeric


def _infer_header_row(df_raw: pd.DataFrame, *, scan_rows: int = 30) -> Optional[int]:
    """Choose a header row index for df_raw (header=None sheet)."""
    if df_raw.empty:
        return None

    best_idx: Optional[int] = None
    best_score: Tuple[int, int, int, int] = (0, 0, 0, 0)

    limit = min(scan_rows, len(df_raw))
    for i in range(limit):
        row_vals = df_raw.iloc[i].tolist()
        score = _row_score_for_header(row_vals)
        if score > best_score:
            best_score = score
            best_idx = i

    # Require at least 2 date-like columns (period axis) OR a decent texty header.
    if best_idx is None:
        return None

    datelike, texty, non_empty, _neg_numeric = best_score
    if datelike < 2 and texty < 3:
        return None

    if non_empty < 2:
        return None

    return best_idx

def _is_date_column(col_name: str) -> bool:
    try:
        dt = pd.to_datetime(str(col_name), errors='coerce')
        return pd.notna(dt)
    except Exception:
        return False


def _choose_text_label_column(df: pd.DataFrame, non_date_cols: List[str]) -> Optional[str]:
    """Pick a likely "metric/label" column in a wide timeseries sheet."""
    best_col = None
    best_score = -1

    sample = df.head(25)

    for c in non_date_cols:
        s = sample[c].astype(str)
        non_empty = (s.str.strip() != '').sum()
        # score: text density (letters) minus numeric density
        has_alpha = s.str.contains(r"[A-Za-z]", regex=True, na=False).sum()
        looks_numeric = s.str.replace(',', '', regex=False).str.match(r"^-?\d+(\.\d+)?$", na=False).sum()
        score = int(has_alpha) * 3 + int(non_empty) - int(looks_numeric) * 2
        if score > best_score:
            best_score = score
            best_col = c

    return best_col


def _explode_wide_timeseries(df: pd.DataFrame, *, sheet_name: str, file_path: Path) -> Optional[List[Dict[str, Any]]]:
    """Explode a sheet shaped as: label + many period columns into long rows."""

    if df.empty:
        return None

    cols = list(df.columns)
    date_cols = [c for c in cols if _is_date_column(c)]
    if len(date_cols) < 6:
        return None

    non_date_cols = [c for c in cols if c not in date_cols]
    label_col = _choose_text_label_column(df, non_date_cols)
    if not label_col:
        return None

    # Optionally pick scenario column (common: first column)
    scenario_col = None
    for c in non_date_cols:
        if c == label_col:
            continue
        sample = df[c].astype(str).str.strip().str.lower()
        if any(sample.isin(['actual', 'budget', 'prior', 'forecast'])):
            scenario_col = c
            break

    out: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        label = str(row.get(label_col) or '').strip()
        if not label or len(label) < 2:
            continue

        # Skip obvious instruction/prose rows
        if len(label) > 120 and ('instructions' in label.lower() or 'take' in label.lower()):
            continue

        scenario = None
        if scenario_col:
            scenario = str(row.get(scenario_col) or '').strip()

        for c in date_cols:
            v = row.get(c)
            if v is None or str(v).strip() == '':
                continue

            out.append(
                {
                    'line_item': label,
                    'period_label': str(c),
                    'value': v,
                    'value_type': scenario or None,
                    'source_file': file_path.name,
                    '_sheet_name': sheet_name,
                    '_row_index': int(idx) + 2,
                }
            )

    if len(out) < 10:
        return None

    return out


def extract_data(file_path: str) -> List[Dict[str, Any]]:
    """Extract tabular data from Excel/CSV into row dicts.

    This repo ingests messy real-world workbooks. A common failure mode is
    "blank first row" or "merged headers" which causes pandas to emit
    `Unnamed: n` columns.

    When a sheet's header row appears unusable, we re-read it with `header=None`
    and heuristically select a better header row from the top of the sheet.
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        extension = file_path.suffix.lower()
        if extension not in ['.xlsx', '.xls', '.csv']:
            raise ValueError(f"Unsupported file type: {extension}")
        
        log_event("extraction_started", {
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size,
            "file_type": extension
        })
        
        all_data = []
        
        if extension == '.csv':
            # Handle CSV files
            try:
                # Read CSV with multiple encoding attempts
                encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                df = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(
                            file_path,
                            encoding=encoding,
                            dtype=str,  # Read everything as string initially
                            na_filter=False,  # Don't convert empty cells to NaN
                            keep_default_na=False
                        )
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df is None:
                    raise ValueError("Unable to read CSV file with any supported encoding")
                
                if not df.empty:
                    # Clean column names + ensure uniqueness
                    cleaned_cols = [str(col).strip().replace('\n', ' ').replace('\r', ' ') for col in df.columns]
                    df.columns = _make_unique_headers(cleaned_cols)

                    # Convert to list of dictionaries
                    for idx, row in df.iterrows():
                        row_dict = {}
                        for col in df.columns:
                            value = row[col]
                            # Clean and normalize cell values
                            if pd.isna(value) or value == '':
                                row_dict[col] = None
                            else:
                                row_dict[col] = str(value).strip()
                        
                        # Skip completely empty rows
                        if any(v is not None and v != '' for v in row_dict.values()):
                            row_dict['_source_sheet'] = 'CSV'
                            all_data.append(row_dict)
                
                log_event("csv_processed", {"rows_extracted": len(all_data)})
                
            except Exception as e:
                log_event("csv_error", {"error": str(e)})
                raise ValueError(f"Failed to process CSV file: {str(e)}")
        
        else:
            # Handle Excel files
            excel_file = pd.ExcelFile(file_path, engine='openpyxl' if extension == '.xlsx' else 'xlrd')

            for sheet_name in excel_file.sheet_names:
                try:
                    # First attempt: assume row 0 is header
                    df = pd.read_excel(
                        file_path,
                        sheet_name=sheet_name,
                        header=0,
                        dtype=str,
                        na_filter=False,
                    )

                    if df.empty:
                        log_event("sheet_empty", {"sheet": sheet_name})
                        continue

                    unnamed_cols = [c for c in df.columns if str(c).lower().startswith('unnamed:')]
                    unnamed_ratio = (len(unnamed_cols) / max(len(df.columns), 1))

                    header_row_index = 0

                    # Heuristic: if most columns are unnamed, try to infer a better header row
                    if unnamed_ratio >= 0.6:
                        df_raw = pd.read_excel(
                            file_path,
                            sheet_name=sheet_name,
                            header=None,
                            dtype=str,
                            na_filter=False,
                        )
                        inferred = _infer_header_row(df_raw)
                        if inferred is not None:
                            header_row_index = inferred
                            headers = [_clean_header_cell(v, j) for j, v in enumerate(df_raw.iloc[inferred].tolist())]
                            headers = _make_unique_headers(headers)
                            df = df_raw.iloc[inferred + 1 :].copy()
                            df.columns = headers
                        else:
                            # keep the original df and continue
                            pass

                    # Clean column names + ensure uniqueness
                    cleaned_cols = [str(col).strip().replace('\n', ' ').replace('\r', ' ') for col in df.columns]
                    df.columns = _make_unique_headers(cleaned_cols)

                    # Convert DataFrame to list of dictionaries
                    exploded = _explode_wide_timeseries(df, sheet_name=sheet_name, file_path=file_path)
                    if exploded is not None:
                        all_data.extend(exploded)
                        log_event(
                            'sheet_extracted_wide_exploded',
                            {
                                'sheet': sheet_name,
                                'rows': len(exploded),
                                'header_row': header_row_index + 1,
                            },
                        )
                    else:
                        sheet_data = []
                        for idx, row in df.iterrows():
                            row_dict = {}
                            for col in df.columns:
                                value = row[col]
                                if pd.isna(value) or value == '':
                                    row_dict[col] = None
                                else:
                                    cleaned_value = str(value).strip()
                                    if cleaned_value == '' or cleaned_value.lower() in ['nan', 'none', 'null']:
                                        row_dict[col] = None
                                    else:
                                        row_dict[col] = cleaned_value

                            if any(v is not None for v in row_dict.values()):
                                row_dict['_sheet_name'] = sheet_name
                                # Excel rows are 1-indexed; add 1 for header row
                                row_dict['_row_index'] = int(idx) + header_row_index + 2
                                sheet_data.append(row_dict)

                        all_data.extend(sheet_data)

                    log_event(
                        "sheet_extracted",
                        {
                            "sheet": sheet_name,
                            "rows": len(sheet_data),
                            "columns": list(df.columns),
                            "header_row": header_row_index + 1,
                            "unnamed_ratio": unnamed_ratio,
                        },
                    )

                except Exception as e:
                    log_event("sheet_extraction_error", {"sheet": sheet_name, "error": str(e)})
                    continue
        
        if not all_data:
            raise ValueError("No data extracted from file")
        
        log_event("extraction_completed", {
            "file_path": str(file_path),
            "total_rows": len(all_data),
            "file_type": extension
        })
        
        return all_data
        
    except Exception as e:
        log_event("extraction_failed", {
            "file_path": str(file_path) if 'file_path' in locals() else 'unknown',
            "error": str(e)
        })
        raise