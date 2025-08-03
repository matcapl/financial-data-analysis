# server/scripts/questions_engine.py

import json
import psycopg2
from datetime import datetime
from decimal import Decimal
from utils import log_event, get_db_connection

# Handler for direct-value questions
def handle_value_direct(metric, template):
    """
    Direct value question: 'What is the value of {{metric}}?'
    """
    question = template['base_question'].replace('{{metric}}', metric['line_item'])
    val = Decimal(metric['value'])
    answer = f"{val:,.2f}"
    return question, answer

# Generic handler for change-based questions
def handle_threshold(metric, template):
    """
    Compute percentage change between metric.value and comparison field based on template settings.
    """
    actual = Decimal(metric['value'])
    comp_field = {
        'Variance vs Budget': 'budget_value',
        'MoM Growth': 'prior_period_value',
        'QoQ Growth': 'prior_period_value',
        'YoY Growth': 'prior_period_value'
    }.get(template['calculation_type'])
    comp_val = metric.get(comp_field)
    if comp_val is None or Decimal(comp_val) == 0:
        return None, None
    comp = Decimal(comp_val)
    change = (actual - comp) / comp * Decimal(100)
    op = template['trigger_operator']
    thresh = Decimal(template['trigger_threshold'])
    conds = {
        '>': change > thresh,
        '<': change < thresh,
        '>=': change >= thresh,
        '<=': change <= thresh,
        '=': change == thresh
    }
    if not conds.get(op, False):
        return None, None
    question = template['base_question'].replace('{change}', f"{change:.1f}")
    answer = f"{change:.1f}%"
    return question, answer

# Registry mapping calculation_type to handler
HANDLERS = {
    'VALUE_DIRECT': handle_value_direct,
    'MoM Growth': handle_threshold,
    'QoQ Growth': handle_threshold,
    'YoY Growth': handle_threshold,
    'Variance vs Budget': handle_threshold,
    # Add new calculation types here
}

def fetch_metrics_and_templates(conn, company_id):
    """
    Retrieve metrics and question templates from the database.
    Attempts full schema then falls back if optional columns are missing.
    """
    full_sql = """
        SELECT fm.id,
               li.name AS line_item,
               fm.value,
               fm.budget_value,
               fm.prior_year_value,
               fm.prior_period_value
        FROM financial_metrics fm
        JOIN line_item_definitions li ON fm.line_item_id = li.id
        WHERE fm.company_id = %s
    """
    minimal_sql = """
        SELECT fm.id,
               li.name AS line_item,
               fm.value
        FROM financial_metrics fm
        JOIN line_item_definitions li ON fm.line_item_id = li.id
        WHERE fm.company_id = %s
    """
    with conn.cursor() as cur:
        try:
            cur.execute(full_sql, (company_id,))
            rows = cur.fetchall()
            metrics = [
                {
                    'id': r[0],
                    'line_item': r[1],
                    'value': r[2],
                    'budget_value': r[3],
                    'prior_year_value': r[4],
                    'prior_period_value': r[5]
                }
                for r in rows
            ]
        except psycopg2.errors.UndefinedColumn:
            conn.rollback()
            cur.execute(minimal_sql, (company_id,))
            rows = cur.fetchall()
            metrics = [
                {
                    'id': r[0],
                    'line_item': r[1],
                    'value': r[2]
                }
                for r in rows
            ]
        # Fetch templates
        cur.execute("""
            SELECT metric, calculation_type, base_question,
                   trigger_threshold, trigger_operator, default_weight
            FROM question_templates
        """)
        templates = [
            {
                'metric': r[0],
                'calculation_type': r[1],
                'base_question': r[2],
                'trigger_threshold': r[3],
                'trigger_operator': r[4],
                'default_weight': r[5]
            }
            for r in cur.fetchall()
        ]
    return metrics, templates

def generate_questions(metrics, templates):
    """
    Yield question/answer dicts for matching metric-template combinations.
    """
    for metric in metrics:
        for tmpl in templates:
            if tmpl['metric'] != metric['line_item'] and tmpl['metric'] != 'ALL':
                continue
            handler = HANDLERS.get(tmpl['calculation_type'])
            if not handler:
                continue
            result = handler(metric, tmpl)
            if not result or not result[0]:
                continue
            question, answer = result
            yield {
                'question_text': question,
                'answer_text': answer,
                'metric_id': metric['id'],
                'calculation_type': tmpl['calculation_type'],
                'default_weight': tmpl['default_weight'],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }

def insert_questions(conn, questions):
    """
    Insert generated questions into the live_questions table.
    """
    with conn.cursor() as cur:
        for q in questions:
            cur.execute("""
                INSERT INTO live_questions (
                    question_text, answer_text, metric_id,
                    calculation_type, default_weight,
                    created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                q['question_text'], q['answer_text'], q['metric_id'],
                q['calculation_type'], q['default_weight'],
                q['created_at'], q['updated_at']
            ))
            log_event("question_created", {
                'metric_id': q['metric_id'],
                'calculation_type': q['calculation_type']
            })

def main(company_id):
    """
    Main entry point: fetch data, generate questions, and insert them.
    """
    log_event("questions_generation_started", {'company_id': company_id})
    conn = get_db_connection()
    try:
        metrics, templates = fetch_metrics_and_templates(conn, company_id)
        questions = list(generate_questions(metrics, templates))
        insert_questions(conn, questions)
        conn.commit()
        log_event("questions_generation_completed", {
            'questions_created': len(questions),
            'company_id': company_id
        })
        print(f"Questions generation completed: {{'questions_created': {len(questions)}, 'total_templates': {len(templates)}, 'total_metrics': {len(metrics)}}}")
    except Exception as e:
        conn.rollback()
        log_event("questions_generation_failed", {'error': str(e)})
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python questions_engine.py <company_id>")
        sys.exit(1)
    main(int(sys.argv[1]))
