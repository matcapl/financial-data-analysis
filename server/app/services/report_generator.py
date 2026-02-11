import os
import sys
import json
import datetime
import logging
import psycopg2
from pathlib import Path
from fpdf import FPDF

# Add proper path for imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'server'))

try:
    from app.utils.utils import get_db_connection
except ImportError:
    # Fallback for standalone execution
    sys.path.insert(0, str(project_root / 'server' / 'app' / 'utils'))
    from utils import get_db_connection


# Setup logging
def setup_logging():
    logging.basicConfig(
       level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("report_generator.log")
        ]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


class Report(FPDF):
    def __init__(self, company_id):
        super().__init__(orientation='L', unit='mm', format='A4')  # Landscape orientation
        self.company_id = company_id
        self.set_auto_page_break(auto=True, margin=15)
        # Register corporate font if provided
        font_path = os.getenv('FONT_PATH')
        if font_path and os.path.isfile(font_path):
            self.add_font('Corporate', '', font_path, uni=True)
            self.set_font('Corporate', '', 10)  # Smaller font for landscape
        else:
            self.set_font('Arial', '', 10)  # Smaller font for landscape

    def _safe_text(self, text: str) -> str:
        try:
            return text.encode('latin-1', 'replace').decode('latin-1')
        except Exception:
            return ''



    def header(self):
        # Title on first page only
        if self.page_no() == 1:
            self.set_font_size(18)
            self.set_text_color(0, 51, 102)
            self.cell(0, 10, self._safe_text(f"Financial Report - Company ID: {self.company_id}"), ln=True, align='C')
            self.ln(5)
            self.set_text_color(0, 0, 0)


    def add_table_with_wrap(self, data, headers, col_widths, max_chars_per_col=None):
        """Add table with text wrapping support - fixed pagination"""
        if max_chars_per_col is None:
            max_chars_per_col = [15] * len(headers)  # Default char limits
        
        # Header row
        self.set_fill_color(0, 51, 102)
        self.set_text_color(255, 255, 255)
        self.set_font(style='B', size=8)
        
        header_height = 6
        for header, w in zip(headers, col_widths):
            self.cell(w, header_height, header, border=1, fill=True, align='C')
        self.ln()
        
        # Data rows with text wrapping
        self.set_text_color(0, 0, 0)
        self.set_font(style='', size=7)
        fill = False
        
        for row in data:
            # Check if we need a page break for this row
            estimated_row_height = 8  # Conservative estimate
            if self.get_y() + estimated_row_height > self.h - self.b_margin:
                self.add_page()
            
            # Prepare row data with text wrapping
            wrapped_row = []
            max_lines = 1
            
            for item, max_chars in zip(row, max_chars_per_col):
                text = self._safe_text(str(item) if item is not None else '')
                
                if len(text) > max_chars:
                    # Simple word wrapping
                    words = text.split(' ')
                    lines = []
                    current_line = ''
                    
                    for word in words:
                        if len(current_line + ' ' + word) <= max_chars:
                            current_line += (' ' + word if current_line else word)
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = word
                    if current_line:
                        lines.append(current_line)
                    
                    wrapped_row.append(lines)
                    max_lines = max(max_lines, len(lines))
                else:
                    wrapped_row.append([text])
            
            # Calculate actual row height
            row_height = max_lines * 4 + 2
            
            # Disable auto page break temporarily to draw complete row
            self.set_auto_page_break(False)
            
            # Draw row background if needed
            if fill:
                self.set_fill_color(245, 245, 245)
                self.rect(self.get_x(), self.get_y(), sum(col_widths), row_height, 'F')
            
            # Draw each cell in the row
            y_start = self.get_y()
            x_start = self.get_x()
            
            for col_idx, (cell_lines, w) in enumerate(zip(wrapped_row, col_widths)):
                x_pos = x_start + sum(col_widths[:col_idx])
                
                # Draw cell border
                self.rect(x_pos, y_start, w, row_height, 'D')
                
                # Draw text lines in cell
                for line_idx, line in enumerate(cell_lines):
                    if line.strip():  # Only draw non-empty lines
                        self.set_xy(x_pos + 1, y_start + 1 + line_idx * 4)
                        # Truncate if still too long
                        if len(line) > max_chars_per_col[col_idx]:
                            line = line[:max_chars_per_col[col_idx]-3] + '...'
                        self.cell(w - 2, 4, self._safe_text(line), border=0, align='L')
            
            # Move to next row
            self.set_xy(x_start, y_start + row_height)
            
            # Re-enable auto page break
            self.set_auto_page_break(True, margin=15)
            
            fill = not fill
        
        self.ln(5)


def generate_report(company_id: int, output_path: str):
    logger.info(f"Starting report generation for company_id={company_id}")
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            # Fetch metrics
            cur.execute(
                """
                SELECT lid.name, p.period_label, fm.value_type, fm.value, fm.currency,
                       fm.source_file, fm.source_page, fm.notes
                  FROM financial_metrics fm
                  JOIN line_item_definitions lid ON fm.line_item_id = lid.id
                  JOIN periods p ON fm.period_id = p.id
                 WHERE fm.company_id = %s
                 ORDER BY p.start_date, lid.name
                """, (company_id,)
            )
            metrics = cur.fetchall()

            def _parse_number(value):
                if value is None:
                    return None
                if isinstance(value, (int, float)):
                    return float(value)
                try:
                    text = str(value).strip()
                    if not text:
                        return None
                    negative = False
                    if text.startswith('(') and text.endswith(')'):
                        negative = True
                        text = text[1:-1]
                    text = text.replace(',', '').replace('£', '').replace('$', '').replace('%', '').strip()
                    if text in {'-', '—'}:
                        return None
                    parsed = float(text)
                    return -parsed if negative else parsed
                except Exception:
                    return None

            def _fmt_gbp(value):
                if value is None:
                    return 'n/a'
                try:
                    return f"£{float(value):,.0f}"
                except Exception:
                    return 'n/a'

            def _pct_change(curr, prev):
                if curr is None or prev is None or prev == 0:
                    return None
                return (float(curr) / float(prev) - 1.0) * 100.0

            def _label_direction(pct, flat_threshold_pct=1.0):
                if pct is None:
                    return 'n/a'
                if abs(pct) <= flat_threshold_pct:
                    return 'flat'
                return 'up' if pct > 0 else 'down'

            def _range_min_max(values):
                vals = [v for v in values if v is not None]
                if not vals:
                    return None
                return (min(vals), max(vals))

            def _metric_quality_score(metric_row) -> float:
                line_item, period_label, value_type, value, currency, source_file, source_page, notes = metric_row

                parsed = _parse_number(value)
                if parsed is None:
                    return -100.0

                score = 0.0
                score += 5.0

                if currency:
                    score += 1.0
                if source_page is not None:
                    score += 1.0

                notes_text = (notes or '').lower()
                if 'ocr' in notes_text or 'fallback' in notes_text:
                    score -= 3.0

                kpi_items = {'Revenue', 'Gross Profit', 'EBITDA', 'Adjusted EBITDA', 'Reported EBITDA'}
                if line_item in kpi_items and value_type in {'Actual', 'Budget', 'Prior Year'}:
                    magnitude = abs(parsed)
                    # Hard gate for headline KPIs: tiny values are almost always extraction noise
                    if magnitude < 1000:
                        return -100.0

                return score

            # Prefer the highest-quality metric per (line_item, period, type)
            best_by_key = {}
            for row in metrics:
                key = (row[0], row[1], row[2])
                score = _metric_quality_score(row)
                existing = best_by_key.get(key)
                if existing is None or score > existing[0]:
                    best_by_key[key] = (score, row)

            metrics = [row for (score, row) in best_by_key.values() if score > -50.0]
            metrics.sort(key=lambda r: (str(r[1]), str(r[0]), str(r[2])))

            try:
                from app.services.fact_selector import (
                    best_metric_candidate as _best_metric_candidate_db,
                    find_latest_usable_month as _find_latest_usable_month_db,
                    list_metric_months as _list_metric_months_db,
                )
            except Exception:
                from fact_selector import (
                    best_metric_candidate as _best_metric_candidate_db,
                    find_latest_usable_month as _find_latest_usable_month_db,
                    list_metric_months as _list_metric_months_db,
                )

            def _best_metric_candidate(company_id_local, line_item, period_label, value_type, min_abs=None):
                return _best_metric_candidate_db(
                    cur,
                    company_id_local,
                    line_item,
                    period_label,
                    value_type,
                    min_abs_value=min_abs,
                )

            # Fetch questions - simplified query that works with current schema
            try:
                cur.execute(
                    """
                    SELECT q.id, q.company_id, q.created_at, q.question_text, q.category, q.priority
                      FROM questions q
                     WHERE q.company_id = %s
                     ORDER BY q.created_at DESC
                     LIMIT 10
                    """, (company_id,)
                )
                questions_data = cur.fetchall()
                # Convert to expected format using actual question text
                questions = []
                for row in questions_data:
                    question_text = row[3]  # question_text is 4th column (index 3)
                    category = row[4]       # category is 5th column (index 4)
                    priority = row[5]       # priority is 6th column (index 5)
                    
                    # Truncate long questions for table display
                    display_text = question_text[:80] + "..." if len(question_text) > 80 else question_text
                    priority_text = {1: "Low", 3: "Medium", 5: "High"}.get(priority, "Medium")
                    
                    questions.append((display_text, "Open", priority_text))
            except Exception as e:
                logger.warning(f"Questions query failed: {e}. Using empty questions list.")
                questions = []

            # Fetch reconciliation findings (deterministic, evidence-first)
            findings = []
            try:
                cur.execute(
                    """
                    SELECT id, finding_type, severity, metric_name, scenario, message, evidence, created_at
                      FROM reconciliation_findings
                     WHERE company_id = %s
                     ORDER BY created_at DESC
                     LIMIT 50
                    """,
                    (company_id,)
                )
                findings = cur.fetchall()
            except Exception as e:
                logger.warning(f"Findings query failed: {e}. Using empty findings list.")
                findings = []

            def _as_dict(evidence):
                import json
                if evidence is None:
                    return {}
                if isinstance(evidence, dict):
                    return evidence
                try:
                    return json.loads(evidence)
                except Exception:
                    return {}

            # Create findings-driven questions (deduped)
            findings_questions = []
            seen = set()
            for (fid, ftype, severity, metric_name, scenario, message, evidence, created_at) in findings:
                ev = _as_dict(evidence)
                period_label = ev.get('period_label')
                ctx = ev.get('context_key')
                key = (ftype, metric_name, scenario, period_label, ctx)
                if key in seen:
                    continue
                seen.add(key)

                citation = ''
                docs = ev.get('documents') or ev.get('occurrences') or []
                if docs:
                    d0 = docs[0]
                    citation = f"doc {d0.get('document_id')} p{d0.get('source_page')} t{d0.get('source_table')} r{d0.get('source_row')} c{d0.get('source_col')}"

                suggested = ev.get('suggested_questions') or []
                if isinstance(suggested, str):
                    suggested = [suggested]

                questions_to_add = []
                if suggested:
                    questions_to_add = [str(qs) for qs in suggested if qs]
                else:
                    if ftype == 'cross_document_restatement':
                        questions_to_add = [f"Goalpost move: {metric_name} ({scenario}) differs across packs for {period_label or ''}. ({citation})"]
                    elif ftype == 'time_rollup_mismatch':
                        questions_to_add = [f"Rollup mismatch: {metric_name} ({scenario}) totals do not reconcile for {period_label or ''}. ({citation})"]
                    elif ftype == 'intra_document_inconsistency':
                        questions_to_add = [f"Inconsistency in-pack: which value is correct for {metric_name} ({scenario}) {period_label or ''}? ({citation})"]
                    else:
                        questions_to_add = [f"Check: {message} ({citation})"]

                pr = 'High' if str(severity).lower() in ('critical', 'high') else 'Medium'
                for q in questions_to_add[:10]:
                    q2 = f"{q} ({citation})" if citation and '(' not in q else q
                    findings_questions.append((q2[:160] + '...' if len(q2) > 160 else q2, 'Open', pr))

            def _finding_score(row):
                # Higher score = more important
                try:
                    _fid, ftype, severity, metric_name, scenario, message, evidence, created_at = row
                    ev = _as_dict(evidence)
                    min_v = ev.get('min_value')
                    max_v = ev.get('max_value')
                    if min_v is not None and max_v is not None:
                        return abs(float(max_v) - float(min_v))
                except Exception:
                    pass
                # Fallback: severity weighting
                sev = str(row[2]).lower()
                return 1e6 if sev in ('critical','high') else 1e3 if sev == 'warning' else 1

            findings_sorted = sorted(findings, key=_finding_score, reverse=True)

            # Generate PDF
            pdf = Report(company_id)
            pdf.add_page()

            # Scope v0.4 Example Output 1: Group Revenue narrative (best-effort)
            try:
                revenue_line_item = 'Revenue'

                # Pull ordered monthly periods (start_date) for this company
                cur.execute(
                    """
                    SELECT p.period_label, p.start_date
                      FROM financial_metrics fm
                      JOIN line_item_definitions lid ON fm.line_item_id = lid.id
                      JOIN periods p ON fm.period_id = p.id
                     WHERE fm.company_id = %s
                       AND lid.name = %s
                       AND fm.value_type = 'Actual'
                       AND p.period_type = 'Monthly'
                     GROUP BY p.period_label, p.start_date
                     ORDER BY p.start_date
                    """,
                    (company_id, revenue_line_item),
                )
                revenue_periods = [(pl, sd) for (pl, sd) in cur.fetchall() if pl]

                # Anchor to the latest monthly period in the DB (not the latest usable Revenue).
                # If Revenue is missing/unreliable for the latest period, we say so explicitly.
                current_period = None
                prev_period = None
                try:
                    cur.execute(
                        """
                        SELECT p.period_label, p.start_date
                          FROM financial_metrics fm
                          JOIN periods p ON fm.period_id = p.id
                         WHERE fm.company_id = %s
                           AND p.period_type = 'Monthly'
                         GROUP BY p.period_label, p.start_date
                         ORDER BY p.start_date DESC NULLS LAST
                         LIMIT 2
                        """,
                        (company_id,),
                    )
                    rows = cur.fetchall()
                    if rows:
                        current_period = rows[0][0]
                        prev_period = rows[1][0] if len(rows) > 1 else None
                except Exception:
                    current_period = None
                    prev_period = None

                latest_usable_period, latest_usable_prev = _find_latest_usable_month_db(
                    cur,
                    company_id,
                    revenue_line_item,
                    min_abs_value=1000,
                )

                def _yoy_label(period_label):
                    if not period_label or len(period_label) < 7 or period_label[4] != '-':
                        return None
                    try:
                        year = int(period_label[0:4])
                        month = period_label[5:7]
                        return f"{year - 1:04d}-{month}"
                    except Exception:
                        return None

                yoy_period = _yoy_label(current_period)

                curr_actual_c = _best_metric_candidate(company_id, revenue_line_item, current_period, 'Actual', min_abs=1000)
                prev_actual_c = _best_metric_candidate(company_id, revenue_line_item, prev_period, 'Actual', min_abs=1000) if prev_period else None
                curr_budget_c = _best_metric_candidate(company_id, revenue_line_item, current_period, 'Budget', min_abs=1000)
                curr_yoy_actual_c = _best_metric_candidate(company_id, revenue_line_item, yoy_period, 'Actual', min_abs=1000) if yoy_period else None

                curr_actual = curr_actual_c.value if curr_actual_c else None
                prev_actual = prev_actual_c.value if prev_actual_c else None
                curr_budget = curr_budget_c.value if curr_budget_c else None
                curr_yoy_actual = curr_yoy_actual_c.value if curr_yoy_actual_c else None

                if curr_actual is None and latest_usable_period is not None and latest_usable_period != current_period:
                    narrative_lines = [
                        f"Insufficient reliable Revenue Actual for latest period {current_period}. "
                        f"Latest usable Revenue Actual is {latest_usable_period}; improve ingestion/normalisation (period + scale) so the latest month is populated." 
                    ]
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 8, pdf._safe_text('Group Revenue (v0.4)'), ln=True)
                    pdf.set_font('Arial', '', 10)
                    pdf.multi_cell(0, 5, pdf._safe_text(' '.join(narrative_lines)))
                    pdf.ln(2)
                    raise StopIteration()

                mom_pct = _pct_change(curr_actual, prev_actual)
                mom_dir = _label_direction(mom_pct)
                mom_abs = (None if curr_actual is None or prev_actual is None else float(curr_actual) - float(prev_actual))

                yoy_pct = _pct_change(curr_actual, curr_yoy_actual)
                yoy_dir = _label_direction(yoy_pct)
                yoy_abs = (None if curr_actual is None or curr_yoy_actual is None else float(curr_actual) - float(curr_yoy_actual))

                bud_pct = _pct_change(curr_actual, curr_budget)
                bud_dir = _label_direction(bud_pct)
                bud_abs = (None if curr_actual is None or curr_budget is None else float(curr_actual) - float(curr_budget))

                # LTM ranges (min/max) for MoM %, YoY %, Budget variance %
                ltm_mom = []
                ltm_yoy = []
                ltm_bud = []
                period_labels = [pl for (pl, _sd) in revenue_periods]

                if current_period and current_period in period_labels:
                    end_idx = period_labels.index(current_period)
                    start_idx = max(0, end_idx - 12)
                    window = period_labels[start_idx : end_idx + 1]

                    for i in range(1, len(window)):
                        a0c = _best_metric_candidate(company_id, revenue_line_item, window[i - 1], 'Actual', min_abs=1000)
                        a1c = _best_metric_candidate(company_id, revenue_line_item, window[i], 'Actual', min_abs=1000)
                        a0 = a0c.value if a0c else None
                        a1 = a1c.value if a1c else None
                        ltm_mom.append(_pct_change(a1, a0))

                    for pl in window:
                        ac = _best_metric_candidate(company_id, revenue_line_item, pl, 'Actual', min_abs=1000)
                        ayc = _best_metric_candidate(company_id, revenue_line_item, _yoy_label(pl), 'Actual', min_abs=1000)
                        a = ac.value if ac else None
                        ay = ayc.value if ayc else None
                        ltm_yoy.append(_pct_change(a, ay))

                        bc = _best_metric_candidate(company_id, revenue_line_item, pl, 'Budget', min_abs=1000)
                        b = bc.value if bc else None
                        ltm_bud.append(_pct_change(a, b))

                mom_range = _range_min_max(ltm_mom)
                yoy_range = _range_min_max(ltm_yoy)
                bud_range = _range_min_max(ltm_bud)

                def _inside_range(pct, rng):
                    if pct is None or rng is None:
                        return 'n/a'
                    return 'inside' if rng[0] <= pct <= rng[1] else 'outside'

                def _fmt_range(rng):
                    if rng is None:
                        return 'n/a'
                    return f"{rng[0]:.1f}-{rng[1]:.1f}%"

                mom_in = _inside_range(mom_pct, mom_range)
                yoy_in = _inside_range(yoy_pct, yoy_range)
                bud_in = _inside_range(bud_pct, bud_range)

                # YTD (current year) actual vs budget and vs last year
                ytd_actual = None
                ytd_budget = None
                ytd_last_year_actual = None

                if current_period and len(current_period) >= 7 and current_period[4] == '-':
                    try:
                        curr_year = int(current_period[0:4])
                        curr_month = int(current_period[5:7])
                        ytd_periods = [f"{curr_year:04d}-{m:02d}" for m in range(1, curr_month + 1)]
                        ytd_last_year_periods = [f"{curr_year - 1:04d}-{m:02d}" for m in range(1, curr_month + 1)]

                        ytd_actual_vals = [
                            (_best_metric_candidate(company_id, revenue_line_item, pl, 'Actual', min_abs=1000).value
                             if _best_metric_candidate(company_id, revenue_line_item, pl, 'Actual', min_abs=1000) is not None else None)
                            for pl in ytd_periods
                        ]
                        ytd_budget_vals = [
                            (_best_metric_candidate(company_id, revenue_line_item, pl, 'Budget', min_abs=1000).value
                             if _best_metric_candidate(company_id, revenue_line_item, pl, 'Budget', min_abs=1000) is not None else None)
                            for pl in ytd_periods
                        ]
                        ytd_last_year_vals = [
                            (_best_metric_candidate(company_id, revenue_line_item, pl, 'Actual', min_abs=1000).value
                             if _best_metric_candidate(company_id, revenue_line_item, pl, 'Actual', min_abs=1000) is not None else None)
                            for pl in ytd_last_year_periods
                        ]

                        if any(v is not None for v in ytd_actual_vals):
                            ytd_actual = sum(v for v in ytd_actual_vals if v is not None)
                        if any(v is not None for v in ytd_budget_vals):
                            ytd_budget = sum(v for v in ytd_budget_vals if v is not None)
                        if any(v is not None for v in ytd_last_year_vals):
                            ytd_last_year_actual = sum(v for v in ytd_last_year_vals if v is not None)
                    except Exception:
                        pass

                ytd_vs_budget_pct = _pct_change(ytd_actual, ytd_budget)
                ytd_vs_budget_dir = _label_direction(ytd_vs_budget_pct)
                ytd_vs_budget_abs = (None if ytd_actual is None or ytd_budget is None else float(ytd_actual) - float(ytd_budget))

                ytd_yoy_pct = _pct_change(ytd_actual, ytd_last_year_actual)
                ytd_yoy_dir = _label_direction(ytd_yoy_pct)
                ytd_yoy_abs = (None if ytd_actual is None or ytd_last_year_actual is None else float(ytd_actual) - float(ytd_last_year_actual))

                narrative_lines = []
                if current_period:
                    narrative_lines.append(
                        f"Group revenue in {current_period} was {_fmt_gbp(curr_actual)}, {mom_dir} {mom_pct:.1f}% ({_fmt_gbp(mom_abs)}) compared to {prev_period or 'previous month'} and this variance is {mom_in} the LTM monthly range of {_fmt_range(mom_range)}."
                        if mom_pct is not None else
                        f"Group revenue in {current_period} was {_fmt_gbp(curr_actual)} (insufficient data for MoM variance)."
                    )
                    narrative_lines.append(
                        f"On a year-on-year basis for {current_period}, group revenue was {yoy_dir} {yoy_pct:.1f}% ({_fmt_gbp(yoy_abs)}) and this variance is {yoy_in} the typical LTM year-on-year range of {_fmt_range(yoy_range)}."
                        if yoy_pct is not None else
                        f"On a year-on-year basis for {current_period}, there is insufficient reliable data to compute YoY variance."
                    )
                    narrative_lines.append(
                        f"Group revenue is {bud_dir} {bud_pct:.1f}% ({_fmt_gbp(bud_abs)}) versus {current_period}'s budget of {_fmt_gbp(curr_budget)}; this variance is {bud_in} the typical LTM budget range of {_fmt_range(bud_range)}."
                        if bud_pct is not None else
                        f"Budget variance for {current_period} could not be computed (missing budget or actual)."
                    )

                    # Evidence: show where the chosen numbers came from
                    evidence_parts = []
                    if curr_actual_c is not None:
                        e = f"Actual source: doc {curr_actual_c.document_id}"
                        if curr_actual_c.source_page is not None:
                            e += f" p{curr_actual_c.source_page}"
                        if curr_actual_c.confidence is not None:
                            e += f" (conf {curr_actual_c.confidence:.2f})"
                        evidence_parts.append(e)
                    if curr_budget_c is not None:
                        e = f"Budget source: doc {curr_budget_c.document_id}"
                        if curr_budget_c.source_page is not None:
                            e += f" p{curr_budget_c.source_page}"
                        if curr_budget_c.confidence is not None:
                            e += f" (conf {curr_budget_c.confidence:.2f})"
                        evidence_parts.append(e)
                    if evidence_parts:
                        narrative_lines.append("Evidence: " + "; ".join(evidence_parts) + ".")

                if ytd_actual is not None:
                    narrative_lines.append(
                        f"YTD to {current_period} group revenue was {_fmt_gbp(ytd_actual)}, {ytd_vs_budget_dir} {ytd_vs_budget_pct:.1f}% ({_fmt_gbp(ytd_vs_budget_abs)}) compared to YTD budget." if ytd_vs_budget_pct is not None else
                        f"YTD to {current_period} group revenue was {_fmt_gbp(ytd_actual)} (insufficient data for YTD vs budget)."
                    )
                    narrative_lines.append(
                        f"Last year for the same period the YTD was {ytd_yoy_dir} {ytd_yoy_pct:.1f}% ({_fmt_gbp(ytd_yoy_abs)}) versus last year." if ytd_yoy_pct is not None else
                        f"Last year comparison for YTD could not be computed (missing last year YTD actuals)."
                    )

                if narrative_lines:
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 8, pdf._safe_text('Group Revenue (v0.4)'), ln=True)
                    pdf.set_font('Arial', '', 10)
                    pdf.multi_cell(0, 5, pdf._safe_text(' '.join(narrative_lines)))
                    pdf.ln(2)

            except StopIteration:
                pass
            except Exception as e:
                logger.warning(f"Revenue narrative failed: {e}")

            # KPI summary (board-pack style) - focuses the output on decisions
            def _to_float(v):
                try:
                    return float(v)
                except Exception:
                    return None

            # Pivot metrics by line item and value_type for the latest (monthly) period
            latest_period = None
            try:
                cur.execute(
                    """
                    SELECT p.period_label
                      FROM financial_metrics fm
                      JOIN periods p ON fm.period_id = p.id
                     WHERE fm.company_id = %s
                       AND p.period_type = 'Monthly'
                     ORDER BY p.start_date DESC NULLS LAST
                     LIMIT 1
                    """,
                    (company_id,),
                )
                r = cur.fetchone()
                latest_period = r[0] if r else None
            except Exception:
                latest_period = None

            if latest_period is None:
                for row in metrics:
                    latest_period = row[1]

            pivot = {}
            for (line_item, period_label, value_type, value, currency, source_file, source_page, notes) in metrics:
                if latest_period is None:
                    latest_period = period_label
                if period_label != latest_period:
                    continue
                pivot.setdefault(line_item, {})[value_type] = value

            def _fmt_money(x):
                if x is None:
                    return ''
                return f"{x:,.0f}"

            def _fmt_delta(a, b):
                if a is None or b is None:
                    return ''
                return _fmt_money(a - b)

            def _fmt_pct(a, b):
                if a is None or b is None or b == 0:
                    return ''
                return f"{((a - b) / abs(b)) * 100:.1f}%"

            key_kpis = [
                'Revenue',
                'Gross Profit',
                'Adjusted EBITDA',
                'EBITDA',
                'Reported EBITDA',
            ]

            summary_rows = []
            for kpi in ['Revenue','Gross Profit','EBITDA']:
                if kpi not in pivot:
                    continue
                actual = _to_float(pivot[kpi].get('Actual'))
                budget = _to_float(pivot[kpi].get('Budget'))
                prior = _to_float(pivot[kpi].get('Prior Year'))
                summary_rows.append((
                    kpi,
                    _fmt_money(actual),
                    _fmt_money(budget),
                    _fmt_delta(actual, budget),
                    _fmt_money(prior),
                    _fmt_delta(actual, prior),
                ))

            if summary_rows:
                pdf.set_font(style='B', size=12)
                pdf.set_text_color(0, 51, 102)
                pdf.cell(0, 8, pdf._safe_text(f"KPI Summary ({latest_period})"), ln=True)
                pdf.set_text_color(0, 0, 0)

                s_headers = ['KPI', 'Actual', 'Budget', 'Vs Budget', 'Prior Year', 'Vs Prior']
                s_widths = [55, 30, 30, 30, 30, 30]
                s_max = [22, 10, 10, 10, 10, 10]
                # KPI trend (v1): show last N periods for key KPIs
                try:
                    periods_sorted = []
                    seen_periods = set()
                    for (line_item, period_label, value_type, value, currency, source_file, source_page, notes) in metrics:
                        if period_label not in seen_periods:
                            seen_periods.add(period_label)
                            periods_sorted.append(period_label)
                    # period_label sorts lexicographically for YYYY-MM / YYYY-QN / YYYY
                    periods_sorted = sorted(periods_sorted)
                    last_periods = periods_sorted[-3:]

                    trend_rows = []
                    for pl in last_periods:
                        for kpi in ['Revenue','Gross Profit','EBITDA']:
                            vals = {}
                            for (li, p_label, vt, v, ccy, sf, sp, n) in metrics:
                                if li == kpi and p_label == pl and v is not None:
                                    vals[vt] = v
                            if not vals:
                                continue
                            act = _to_float(vals.get('Actual'))
                            bud = _to_float(vals.get('Budget'))
                            trend_rows.append((
                                pl,
                                kpi,
                                _fmt_money(act),
                                _fmt_money(bud),
                                _fmt_delta(act, bud),
                            ))

                    if trend_rows:
                        pdf.set_font(style='B', size=12)
                        pdf.set_text_color(0, 51, 102)
                        pdf.cell(0, 8, pdf._safe_text('KPI Trend (Last Periods)'), ln=True)
                        pdf.set_text_color(0, 0, 0)

                        tr_headers = ['Period', 'KPI', 'Actual', 'Budget', 'Vs Budget']
                        tr_widths = [25, 55, 30, 30, 30]
                        tr_max = [10, 18, 10, 10, 10]
                        pdf.add_table_with_wrap(trend_rows, tr_headers, tr_widths, tr_max)
                except Exception:
                    pass

                pdf.add_table_with_wrap(summary_rows, s_headers, s_widths, s_max)

                # Top findings summary (v1): put the most important issues near the front
                top_rows = []
                for (fid, ftype, severity, metric_name, scenario, message, evidence, created_at) in findings_sorted[:3]:
                    ev = _as_dict(evidence)
                    top_rows.append((
                        str(ftype),
                        str(metric_name or ''),
                        str(scenario or ''),
                        str(ev.get('period_label') or ''),
                        str(ev.get('context_key') or ''),
                    ))

                if top_rows:
                    pdf.set_font(style='B', size=12)
                    pdf.set_text_color(0, 51, 102)
                    pdf.cell(0, 8, pdf._safe_text('Top Findings'), ln=True)
                    pdf.set_text_color(0, 0, 0)

                    t_headers = ['Type', 'Metric', 'Scenario', 'Period', 'Context']
                    t_widths = [55, 55, 35, 25, 45]
                    t_max = [22, 18, 12, 10, 16]
                    pdf.add_table_with_wrap(top_rows, t_headers, t_widths, t_max)

                    # Top questions (from findings) on page 1
                    tq = findings_questions[:3]
                    if tq:
                        pdf.set_font(style='B', size=12)
                        pdf.set_text_color(0, 51, 102)
                        pdf.cell(0, 8, pdf._safe_text('Top Questions'), ln=True)
                        pdf.set_text_color(0, 0, 0)
                        tq_headers = ['Question','Priority']
                        tq_widths = [220, 35]
                        tq_max = [120, 8]
                        tq_rows = [(q, pr) for (q, _st, pr) in tq]
                        pdf.add_table_with_wrap(tq_rows, tq_headers, tq_widths, tq_max)


            # Data stored (preview) — avoid dumping the whole DB
            pdf.set_font(style='B', size=12)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 8, pdf._safe_text('Data Stored (Preview)'), ln=True)
            pdf.set_text_color(0, 0, 0)

            try:
                cur.execute("SELECT COUNT(*) FROM financial_metrics WHERE company_id = %s", (company_id,))
                total_metrics = int(cur.fetchone()[0])
            except Exception:
                total_metrics = len(metrics)

            pdf.set_font(style='', size=10)
            pdf.multi_cell(0, 5, pdf._safe_text(
                f"This section shows a small preview of what is currently stored in the database for company {company_id}. "
                f"Total metric rows: {total_metrics}."
            ))

            # Summary by period + type (top 12)
            summary_rows = []
            try:
                cur.execute(
                    """
                    SELECT p.period_label, fm.value_type, COUNT(*)
                      FROM financial_metrics fm
                      JOIN periods p ON fm.period_id = p.id
                     WHERE fm.company_id = %s
                     GROUP BY p.period_label, fm.value_type
                     ORDER BY p.period_label DESC, fm.value_type
                     LIMIT 12
                    """,
                    (company_id,),
                )
                for (pl, vt, cnt) in cur.fetchall():
                    summary_rows.append((str(pl), str(vt), str(cnt)))
            except Exception:
                summary_rows = []

            if summary_rows:
                pdf.set_font(style='B', size=11)
                pdf.cell(0, 7, pdf._safe_text('Counts by Period + Type (top 12)'), ln=True)
                pdf.set_font(style='', size=10)
                pdf.add_table_with_wrap(summary_rows, ['Period', 'Type', 'Rows'], [40, 30, 20], [10, 10, 8])

            # Metrics table preview (capped)
            headers = ['Line Item','Period','Type','Value','Currency','Source','Page','Notes']
            col_widths = [35, 20, 25, 25, 20, 45, 12, 40]
            max_chars = [12, 8, 18, 10, 8, 20, 4, 20]

            max_preview_rows = 80
            metrics_preview = metrics[:max_preview_rows]

            metrics_clean = []
            for row in metrics_preview:
                clean_row = list(row[:8])
                if len(clean_row) > 5 and clean_row[5]:
                    filename = str(clean_row[5])
                    if '.' in filename:
                        name_part = filename.split('.')[0]
                        clean_row[5] = (name_part[:15] + '...') if len(name_part) > 18 else name_part
                metrics_clean.append(clean_row)

            if metrics_clean:
                pdf.set_font(style='B', size=11)
                pdf.cell(0, 7, pdf._safe_text(f"Metric Rows (preview: {len(metrics_clean)} of {total_metrics})"), ln=True)
                pdf.set_font(style='', size=10)
                pdf.add_table_with_wrap(metrics_clean, headers, col_widths, max_chars)

            if total_metrics > max_preview_rows:
                pdf.set_font(style='I', size=9)
                pdf.multi_cell(0, 5, pdf._safe_text(
                    "Note: the full metric table is intentionally not printed to PDF. "
                    "Improve ingestion/normalisation so the front-page findings and KPI sections become decision-grade."
                ))

            # Add page break before questions
            pdf.add_page()
            
            # Findings-driven section (v1): show reconciliation first, then questions
            pdf.set_font(style='B', size=12)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 8, pdf._safe_text('Data Quality & Reconciliation'), ln=True)
            pdf.set_text_color(0, 0, 0)

            f_headers = ['Type', 'Metric', 'Scenario', 'Period', 'Context', 'Message']
            f_widths = [35, 35, 22, 22, 25, 120]
            f_max = [18, 14, 10, 10, 12, 60]

            findings_rows = []
            for (fid, ftype, severity, metric_name, scenario, message, evidence, created_at) in findings:
                ev = _as_dict(evidence)
                findings_rows.append((
                    str(ftype),
                    str(metric_name or ''),
                    str(scenario or ''),
                    str(ev.get('period_label') or ''),
                    str(ev.get('context_key') or ''),
                    str(message or ''),
                ))

            if findings_rows:
                pdf.add_table_with_wrap(findings_rows, f_headers, f_widths, f_max)
            else:
                pdf.set_font(style='', size=10)
                pdf.multi_cell(0, 5, pdf._safe_text('No reconciliation findings for this company yet.'))

            pdf.add_page()
            pdf.set_font(style='B', size=12)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 8, pdf._safe_text('Questions (From Findings)'), ln=True)
            pdf.set_text_color(0, 0, 0)

            q_headers = ['Question','Status','Priority']
            q_col_widths = [180, 40, 35]  # Total: 255mm
            q_max_chars = [90, 12, 8]  # Character limits

            q_source = findings_questions
            if q_source:
                pdf.add_table_with_wrap(q_source, q_headers, q_col_widths, q_max_chars)
            else:
                pdf.multi_cell(0, 5, pdf._safe_text('No findings-driven questions yet. Generate findings first.'))

            pdf.output(output_path)
            logger.info(f"PDF written to {output_path}")

            # Record metadata
            cur.execute(
                "INSERT INTO generated_reports (company_id, report_type, file_path, created_at) VALUES (%s, %s, %s, %s)",
                (company_id, 'financial_analysis', output_path, datetime.datetime.now())
            )
            conn.commit()
            logger.info("Metadata recorded in generated_reports")

    except Exception:
        logger.exception("Error generating report")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python report_generator.py <company_id> <output_path>")
        sys.exit(1)
    company_id = int(sys.argv[1])
    output_path = sys.argv[2]
    generate_report(company_id, output_path)
