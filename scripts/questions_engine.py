import psycopg2
import json
from datetime import datetime, timedelta
from utils import get_db_connection, log_event

def main():
    """
    Fixed Questions Engine - Phase 1 Critical Fix
    
    Key fixes implemented:
    1. Lower composite score threshold from 0.5 to 0.1
    2. Fix calculation logic: abs(value) * weight * 10 instead of / 100
    3. Replace pd.Timedelta with datetime.timedelta
    4. Add better error handling and logging
    5. Lower trigger thresholds to generate more questions
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get all question templates
            cur.execute("SELECT id, metric, calculation_type, base_question, trigger_threshold, trigger_operator, default_weight FROM question_templates")
            templates = cur.fetchall()
            
            # Get all derived metrics with their values
            cur.execute(
                """
                SELECT dm.id, dm.base_metric_id, dm.calculation_type, dm.company_id, dm.period_id, 
                       dm.calculated_value, lid.name
                FROM derived_metrics dm
                JOIN line_item_definitions lid ON dm.base_metric_id = lid.id
                WHERE dm.calculated_value IS NOT NULL
                """
            )
            metrics = cur.fetchall()
            
            created_count = 0
            skipped_count = 0
            
            for m in metrics:
                derived_id, base_metric_id, calc_type, company_id, period_id, value, metric_name = m
                
                if value is None:
                    log_event("metric_skipped", {"reason": "Null value", "derived_id": derived_id})
                    skipped_count += 1
                    continue
                
                for t in templates:
                    tpl_id, tpl_metric, tpl_calc, base_q, threshold, op, weight = t
                    
                    # Match metric and calculation type
                    if metric_name == tpl_metric and calc_type == tpl_calc:
                        # Apply dynamic threshold reduction for better question generation
                        adjusted_threshold = threshold * 0.5  # Reduce by 50%
                        
                        # Check if metric value exceeds adjusted threshold  
                        if eval(f"{abs(value)} {op} {adjusted_threshold}"):
                            # Check if question already exists
                            cur.execute("SELECT id FROM live_questions WHERE derived_metric_id = %s AND template_id = %s", 
                                      (derived_id, tpl_id))
                            if cur.fetchone():
                                skipped_count += 1
                                continue
                            
                            # Generate question text
                            direction = "increase" if value > 0 else "decrease" if value < 0 else "stay flat"
                            question_text = base_q.replace("{change}", f"{abs(value):.2f}")
                            
                            # Calculate composite score with improved logic
                            magnitude = abs(value)
                            composite_score = magnitude * weight * 10  # Multiply by 10 instead of divide by 100
                            
                            # Lower threshold from 0.5 to 0.1 for more questions
                            if composite_score < 0.1:
                                log_event("question_threshold_not_met", {
                                    "composite_score": composite_score,
                                    "threshold": 0.1,
                                    "metric": metric_name,
                                    "value": value
                                })
                                skipped_count += 1
                                continue
                            
                            # Create scorecard with enhanced metrics
                            scorecard = {
                                "magnitude": magnitude,
                                "weight": weight,
                                "composite_score": composite_score,
                                "threshold_used": adjusted_threshold,
                                "direction": direction,
                                "created_at": datetime.now().isoformat()
                            }
                            
                            # Set deadline to 7 days from now (fixed timedelta usage)
                            deadline = datetime.now() + timedelta(days=7)
                            
                            # Insert the question
                            cur.execute(
                                """
                                INSERT INTO live_questions (
                                    derived_metric_id, template_id, question_text, category, composite_score, scorecard,
                                    owner, deadline, created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                                """,
                                (
                                    derived_id, tpl_id, question_text, "Financial", composite_score,
                                    json.dumps(scorecard), "Finance Team", deadline,
                                    datetime.now(), datetime.now()
                                )
                            )
                            question_id = cur.fetchone()[0]
                            
                            # Log the question creation
                            cur.execute(
                                """
                                INSERT INTO question_logs (
                                    live_question_id, change_type, changed_by, new_value, change_note
                                ) VALUES (%s, %s, %s, %s, %s)
                                """,
                                (question_id, "Question Created", "System", question_text, 
                                 f"Auto-generated based on {metric_name} {calc_type} metric with composite score {composite_score:.2f}")
                            )
                            
                            created_count += 1
                            
                            log_event("question_created", {
                                "question_id": question_id,
                                "metric": metric_name,
                                "calculation_type": calc_type,
                                "composite_score": composite_score,
                                "value": value
                            })
            
            conn.commit()
            
            # Final summary logging
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