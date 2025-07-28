from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import psycopg2
from datetime import datetime
from utils import get_db_connection, log_event

def generate_report(company_id: int, output_path: str):
    log_event("report_generation_started", {"company_id": company_id, "output_path": output_path})
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Fetch company details
                cur.execute("SELECT name FROM companies WHERE id = %s", (company_id,))
                company_name = cur.fetchone()[0]

                # Fetch metrics
                cur.execute(
                    """
                    SELECT lid.name, p.period_label, fm.value_type, fm.value, fm.currency,
                           fm.source_file, fm.source_page, fm.notes, fm.corroboration_status
                    FROM financial_metrics fm
                    JOIN line_item_definitions lid ON fm.line_item_id = lid.id
                    JOIN periods p ON fm.period_id = p.id
                    WHERE fm.company_id = %s
                    ORDER BY p.start_date, lid.name
                    """,
                    (company_id,)
                )
                metrics = cur.fetchall()

                # Fetch derived metrics
                cur.execute(
                    """
                    SELECT lid.name, p.period_label, dm.calculation_type, dm.calculated_value, dm.unit,
                           dm.source_ids, dm.calculation_note, dm.corroboration_status
                    FROM derived_metrics dm
                    JOIN line_item_definitions lid ON dm.base_metric_id = lid.id
                    JOIN periods p ON dm.period_id = p.id
                    WHERE dm.company_id = %s
                    ORDER BY dm.calculated_value DESC
                    """,
                    (company_id,)
                )
                derived_metrics = cur.fetchall()

                # Fetch top questions
                cur.execute(
                    """
                    SELECT lq.question_text, lq.composite_score, lq.owner, lq.deadline
                    FROM live_questions lq
                    WHERE lq.company_id = %s AND lq.status = 'Open'
                    ORDER BY lq.composite_score DESC LIMIT 35
                    """,
                    (company_id,)
                )
                questions = cur.fetchall()

        # Generate PDF
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph(f"{company_name} Financial Report - {datetime.now().strftime('%Y-%m-%d')}", styles["Title"]))
        elements.append(Spacer(1, 12))

        # Executive Summary
        top_findings = derived_metrics[:5]
        elements.append(Paragraph("Executive Summary", styles["Heading1"]))
        for finding in top_findings:
            metric, period, calc_type, value, unit, _, note, status = finding
            text = f"{metric} ({period}): {calc_type} = {value:.2f}{unit}. {note}. Status: {status}"
            elements.append(Paragraph(text, styles["BodyText"]))
        elements.append(Spacer(1, 12))

        # Data Inventory
        elements.append(Paragraph("Data Inventory", styles["Heading1"]))
        data = [["Metric", "Period", "Value Type", "Value", "Currency", "Source", "Notes", "Status"]]
        for metric in metrics:
            name, period, v_type, value, currency, src_file, src_page, notes, status = metric
            src = f"{src_file}, p.{src_page}" if src_page else src_file
            data.append([name, period, v_type, f"{value:.2f}" if value else "N/A", currency, src, notes or "", status])
        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # Prioritized Observations
        elements.append(Paragraph("Prioritized Observations", styles["Heading1"]))
        for obs in derived_metrics:
            metric, period, calc_type, value, unit, _, note, status = obs
            text = f"{metric} ({period}): {calc_type} = {value:.2f}{unit}. {note}. Status: {status}"
            elements.append(Paragraph(text, styles["BodyText"]))
        elements.append(Spacer(1, 12))

        # Management Questions
        elements.append(Paragraph("Management Questions", styles["Heading1"]))
        data = [["Question", "Score", "Owner", "Deadline"]]
        for q in questions:
            text, score, owner, deadline = q
            data.append([text, f"{score:.2f}", owner, deadline.strftime("%Y-%m-%d") if deadline else "TBD"])
        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)

        doc.build(elements)
        cur.execute(
            """
            INSERT INTO generated_reports (
                generated_on, filter_type, parameters, output_summary, report_file_path, company_id,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                datetime.now(), "Top 35 Questions", json.dumps({"company_id": company_id}),
                f"Generated report for {company_name}", output_path, company_id,
                datetime.now(), datetime.now()
            )
        )
        conn.commit()
        log_event("report_generated", {"output_path": output_path})
    except Exception as e:
        log_event("report_generation_failed", {"error": str(e)})
        raise

if __name__ == "__main__":
    generate_report(1, "reports/financial_report.pdf")