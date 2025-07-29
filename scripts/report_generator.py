import psycopg2
import json
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import sys
print(f"Script started with args: {sys.argv}")

def generate_report(company_id, output_path):
    print(f"Generating report for company_id: {company_id}, output_path: {output_path}")
    try:
        # Use context manager for database connection
        with psycopg2.connect(
            dbname="finance",
            user="a",
            host="localhost",
            port="5432"
        ) as conn:
            with conn.cursor() as cur:
                # Fetch financial metrics
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

                # Fetch live questions
                cur.execute(
                    """
                    SELECT lq.question_text, lq.status, lq.composite_score
                    FROM live_questions lq
                    JOIN derived_metrics dm ON lq.derived_metric_id = dm.id
                    WHERE dm.company_id = %s AND lq.status = 'Open'
                    ORDER BY lq.composite_score DESC
                    """,
                    (company_id,)
                )
                questions = cur.fetchall()

                # Generate PDF
                doc = SimpleDocTemplate(output_path, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []

                elements.append(Paragraph(f"Financial Report - Company ID: {company_id}", styles['Title']))
                elements.append(Spacer(1, 12))

                # Metrics table
                data = [['Line Item', 'Period', 'Type', 'Value', 'Currency', 'Source', 'Page', 'Notes', 'Status']]
                for metric in metrics:
                    data.append(list(metric))
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)
                elements.append(Spacer(1, 12))

                # Questions table
                elements.append(Paragraph("Open Questions", styles['Heading2']))
                data = [['Question', 'Status', 'Score']]
                for question in questions:
                    data.append(list(question))
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)

                # Build the PDF
                doc.build(elements)

                # Save metadata to generated_reports
                cur.execute(
                    """
                    INSERT INTO generated_reports (generated_on, filter_type, parameters, output_summary, report_file_path, company_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (datetime.datetime.now(), "Top 35 Questions", json.dumps({"company_id": company_id}),
                     f"Summary for company_id {company_id}", output_path, company_id)
                )
                conn.commit()
        print(f"PDF generated successfully at: {output_path}")

    except Exception as e:
        print(f"Error generating report: {e}")
        raise

if __name__ == "__main__":
    company_id = sys.argv[1]
    output_path = sys.argv[2]
    generate_report(company_id, output_path)
    generate_report(1, "reports/financial_report.pdf")