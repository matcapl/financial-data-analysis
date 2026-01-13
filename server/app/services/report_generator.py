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

                if ftype == 'cross_document_restatement':
                    q = f"Goalpost move: {metric_name} ({scenario}) differs across packs for {period_label or ''}. ({citation})"
                elif ftype == 'time_rollup_mismatch':
                    q = f"Rollup mismatch: {metric_name} ({scenario}) totals do not reconcile for {period_label or ''}. ({citation})"
                elif ftype == 'intra_document_inconsistency':
                    q = f"Inconsistency in-pack: which value is correct for {metric_name} ({scenario}) {period_label or ''}? ({citation})"
                else:
                    q = f"Check: {message} ({citation})"

                pr = 'High' if str(severity).lower() in ('critical', 'high') else 'Medium'
                findings_questions.append((q[:160] + '...' if len(q) > 160 else q, 'Open', pr))

            # Generate PDF
            pdf = Report(company_id)
            pdf.add_page()

            # KPI summary (board-pack style) - focuses the output on decisions
            def _to_float(v):
                try:
                    return float(v)
                except Exception:
                    return None

            # Pivot metrics by line item and value_type for the latest period
            latest_period = None
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
            for kpi in key_kpis:
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
                pdf.add_table_with_wrap(summary_rows, s_headers, s_widths, s_max)


            # Metrics table - optimized for landscape A4 (297mm width, ~270mm usable)
            headers = ['Line Item','Period','Type','Value','Currency','Source','Page','Notes']
            col_widths = [35, 20, 25, 25, 20, 45, 12, 40]  # Total: 222mm
            max_chars = [12, 8, 18, 10, 8, 20, 4, 20]  # Character limits per column
            
            # Remove 'Status' column and truncate source filenames in data
            metrics_clean = []
            for row in metrics:
                clean_row = list(row[:8])  # Remove status column (take first 8 columns)
                # Truncate source filename
                if len(clean_row) > 5 and clean_row[5]:  # Source column
                    filename = str(clean_row[5])
                    if '.' in filename:
                        name_part = filename.split('.')[0]
                        if len(name_part) > 18:
                            clean_row[5] = name_part[:15] + '...'
                        else:
                            clean_row[5] = name_part
                metrics_clean.append(clean_row)
            
            pdf.add_table_with_wrap(metrics_clean, headers, col_widths, max_chars)

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

            q_source = findings_questions if findings_questions else questions
            pdf.add_table_with_wrap(q_source, q_headers, q_col_widths, q_max_chars)

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
