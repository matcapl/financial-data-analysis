import psycopg2
import json
from datetime import datetime
from utils import get_db_connection, log_event

def main():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, metric, calculation_type, base_question, trigger_threshold, trigger_operator, default_weight FROM question_templates")
            templates = cur.fetchall()
            cur.execute(
                """
                SELECT dm.id, dm.base_metric_id, dm.calculation_type, dm.company_id, dm.period_id, dm.calculated_value, lid.name
                FROM derived_metrics dm
                JOIN line_item_definitions lid ON dm.base_metric_id = lid.id
                """
            )
            metrics = cur.fetchall()
            created_count = 0
            for m in metrics:
                derived_id, base_metric_id, calc_type, company_id, period_id, value, metric_name = m
                if value is None:
                    log_event("metric_skipped", {"reason": "Null value", "derived_id": derived_id})
                    continue
                for t in templates:
                    tpl_id, tpl_metric, tpl_calc, base_q, threshold, op, weight = t
                    if metric_name == tpl_metric and calc_type == tpl_calc:
                        if eval(f"{value} {op} {threshold}"):
                            cur.execute("SELECT id FROM live_questions WHERE derived_metric_id = %s AND template_id = %s", (derived_id, tpl_id))
                            if cur.fetchone():
                                continue
                            direction = "increase" if value > 0 else "decrease" if value < 0 else "stay flat"
                            question_text = base_q.replace("{change}", f"{abs(value):.2f}")
                            scorecard = {"magnitude": abs(value), "weight": weight, "composite_score": abs(value) * weight / 100}
                            if scorecard["composite_score"] < 0.5:
                                continue
                            cur.execute(
                                """
                                INSERT INTO live_questions (
                                    derived_metric_id, template_id, question_text, category, composite_score, scorecard,
                                    owner, deadline, created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                                """,
                                (
                                    derived_id, tpl_id, question_text, "Financial", scorecard["composite_score"],
                                    json.dumps(scorecard), "Finance Team", datetime.now() + pd.Timedelta(days=7),
                                    datetime.now(), datetime.now()
                                )
                            )
                            question_id = cur.fetchone()[0]
                            cur.execute(
                                """
                                INSERT INTO question_logs (
                                    live_question_id, change_type, changed_by, new_value, change_note
                                ) VALUES (%s, %s, %s, %s, %s)
                                """,
                                (question_id, "Question Created", "System", question_text, "Auto-generated based on metric")
                            )
                            created_count += 1
            conn.commit()
            log_event("questions_generated", {"count": created_count})

if __name__ == "__main__":
    main()