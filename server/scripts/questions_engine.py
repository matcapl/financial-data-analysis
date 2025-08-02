# server/scripts/questions_engine.py

import psycopg2
import json
from datetime import datetime, timedelta
from decimal import Decimal
from utils import get_db_connection, log_event


def main():
    """
    Fixed Questions Engine - FINAL VERSION

    Key fixes implemented:
    1. Fix Decimal * float operations by casting to float
    2. Lower composite score threshold from 0.5 to 0.1
    3. Consistent Decimal handling
    4. Better error handling and logging
    5. Generate sufficient questions per run
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Load all templates
            cur.execute("""
                SELECT id, metric, calculation_type, base_question, trigger_threshold,
                       trigger_operator, default_weight
                FROM question_templates
            """)
            templates = cur.fetchall()

            # Load all derived metrics
            cur.execute("""
                SELECT dm.id, dm.base_metric_id, dm.calculation_type,
                       dm.company_id, dm.period_id, dm.calculated_value, lid.name
                FROM derived_metrics dm
                JOIN line_item_definitions lid
                  ON dm.base_metric_id = lid.id
                WHERE dm.calculated_value IS NOT NULL
            """)
            metrics = cur.fetchall()

            created_count = 0
            skipped_count = 0

            # Process each derived metric
            for derived_id, base_metric_id, calc_type, company_id, period_id, value, metric_name in metrics:
                if value is None:
                    log_event("metric_skipped", {
                        "reason": "Null value", "derived_id": derived_id
                    })
                    skipped_count += 1
                    continue

                # Convert value to float
                value_float = float(value) if isinstance(value, Decimal) else value

                for tpl_id, tpl_metric, tpl_calc, base_q, threshold, op, weight in templates:
                    # Match on metric name and calculation type
                    if metric_name != tpl_metric or calc_type != tpl_calc:
                        continue

                    # Prepare threshold as float
                    threshold_val = float(threshold) if isinstance(threshold, Decimal) else threshold
                    # Apply initial trigger threshold (reduce by 50% for sensitivity)
                    trigger_value = threshold_val * 0.5

                    # Check trigger condition
                    try:
                        if not eval(f"abs({value_float}) {op} {trigger_value}"):
                            skipped_count += 1
                            log_event("trigger_not_met", {
                                "derived_id": derived_id,
                                "metric": metric_name,
                                "calc_type": calc_type,
                                "value": value_float,
                                "threshold": trigger_value,
                                "operator": op
                            })
                            continue
                    except Exception as e:
                        log_event("trigger_eval_error", {
                            "error": str(e),
                            "expression": f"abs({value_float}) {op} {trigger_value}"
                        })
                        skipped_count += 1
                        continue

                    # Check for existing question
                    cur.execute("""
                        SELECT id
                        FROM live_questions
                        WHERE derived_metric_id = %s AND template_id = %s
                    """, (derived_id, tpl_id))
                    if cur.fetchone():
                        skipped_count += 1
                        continue

                    # Generate question text
                    direction = ("increase" if value_float > 0
                                 else "decrease" if value_float < 0
                                 else "stay flat")
                    question_text = base_q.replace("{change}", f"{abs(value_float):.2f}")

                    # Compute composite score
                    weight_val = float(weight) if isinstance(weight, Decimal) else weight
                    magnitude = abs(value_float)
                    composite_score = magnitude * weight_val * 10  # boost for visibility

                    # Enforce lower threshold for composite_score
                    if composite_score < 0.1:
                        skipped_count += 1
                        log_event("score_threshold_not_met", {
                            "derived_id": derived_id,
                            "composite_score": composite_score,
                            "min_required": 0.1
                        })
                        continue

                    # Build scorecard
                    scorecard = {
                        "magnitude": magnitude,
                        "weight": weight_val,
                        "composite_score": composite_score,
                        "trigger_value": trigger_value,
                        "direction": direction,
                        "created_at": datetime.now().isoformat()
                    }

                    # Deadline set 7 days ahead
                    deadline = datetime.now() + timedelta(days=7)

                    # Insert live question
                    cur.execute("""
                        INSERT INTO live_questions (
                            derived_metric_id, template_id, question_text, category,
                            composite_score, scorecard, owner, deadline,
                            created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        derived_id, tpl_id, question_text, "Financial",
                        composite_score, json.dumps(scorecard), "Analytics Team",
                        deadline, datetime.now(), datetime.now()
                    ))
                    question_id = cur.fetchone()[0]

                    # Log question creation
                    cur.execute("""
                        INSERT INTO question_logs (
                            live_question_id, change_type, changed_by,
                            new_value, change_note
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (
                        question_id, "Question Created", "System",
                        question_text,
                        f"Auto-generated for {metric_name} ({calc_type}), score {composite_score:.2f}"
                    ))

                    created_count += 1
                    log_event("question_created", {
                        "question_id": question_id,
                        "metric": metric_name,
                        "calculation_type": calc_type,
                        "composite_score": composite_score,
                        "value": value_float
                    })

            # Commit all inserts
            conn.commit()

            # Final summary
            summary = {
                "questions_created": created_count,
                "questions_skipped": skipped_count,
                "total_templates": len(templates),
                "total_metrics": len(metrics)
            }
            log_event("questions_generation_completed", summary)
            print(f"Questions generation completed: {summary}")


if __name__ == "__main__":
    main()
