#!/usr/bin/env python3
"""
questions_generator.py - ID-based YAML-driven Question Generator

PURPOSE:
Replaces the old template_key approach with a clean ID-based system that:
1. Reads observations.yaml and questions.yaml configurations 
2. Computes observations from derived_metrics in the database
3. Filters observations by materiality thresholds
4. Generates live questions using ID-based templates
5. Ranks and selects questions by importance and magnitude

USAGE:
    python questions_generator.py <company_id>

FLOW:
    derived_metrics → observations → materiality_filter → questions → live_questions

This script uses IDs (not template_keys) and integrates observations.yaml fully
into the question generation pipeline as requested.
"""

import sys
import yaml
import json
import psycopg2
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from jinja2 import Template
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# Import existing utilities
sys.path.append(str(Path(__file__).parent))
from utils import get_db_connection, log_event


@dataclass
class Observation:
    """Represents a computed financial observation"""
    id: int
    name: str
    description: str
    value: float
    magnitude: float
    materiality_threshold: float
    is_material: bool
    metric_context: Dict[str, Any]
    calculation_type: str


@dataclass  
class QuestionTemplate:
    """Represents a question template linked to an observation"""
    id: int
    observation_id: int
    importance: int
    template: str
    weight: float


class YAMLDrivenQuestionGenerator:
    """
    Main class for YAML-driven, ID-based question generation.
    Replaces the old template_key system with proper observation-driven logic.
    """

    def __init__(self, company_id: int):
        self.company_id = company_id
        self.base_path = Path(__file__).parent.parent

        # Load YAML configurations
        self.observations_config = self._load_yaml("config/observations.yaml")
        self.questions_config = self._load_yaml("config/questions.yaml")

        # Extract configuration
        self.observations_meta = self.observations_config.get("metadata", {})
        self.questions_meta = self.questions_config.get("metadata", {})

        self.default_materiality = self.observations_meta.get("default_materiality_threshold", 0.05)
        self.materiality_by_metric = self.observations_meta.get("materiality_by_metric", {})
        self.importance_weights = self.observations_meta.get("importance_weights", {})

        log_event("yaml_question_generator_initialized", {
            "company_id": company_id,
            "observations_count": len(self.observations_config.get("observations", [])),
            "questions_count": len(self.questions_config.get("questions", [])),
            "default_materiality": self.default_materiality
        })

    def _load_yaml(self, relative_path: str) -> Dict[str, Any]:
        """Load YAML configuration file"""
        try:
            yaml_path = self.base_path / relative_path
            with open(yaml_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            log_event("yaml_load_error", {"file": relative_path, "error": str(e)})
            return {}

    def compute_observations(self, conn) -> List[Observation]:
        """
        Compute all observations from derived_metrics table.
        This is where the magic happens - converting raw metrics to insights.
        """
        observations = []

        with conn.cursor() as cur:
            # Get all derived metrics for this company
            cur.execute("""
                SELECT dm.id, dm.base_metric_id, dm.calculation_type,
                       dm.calculated_value, dm.unit, dm.period_label,
                       dm.company_id, li.name as line_item_name,
                       fm.value as base_value, fm.value_type, fm.frequency
                FROM derived_metrics dm
                JOIN financial_metrics fm ON dm.base_metric_id = fm.id  
                JOIN line_item_definitions li ON fm.line_item_id = li.id
                WHERE dm.company_id = %s
                ORDER BY dm.created_at DESC
            """, (self.company_id,))

            derived_metrics = cur.fetchall()

            log_event("derived_metrics_loaded", {
                "company_id": self.company_id,
                "metrics_count": len(derived_metrics)
            })

            # Process each derived metric against observation definitions
            for metric_row in derived_metrics:
                (dm_id, base_metric_id, calc_type, calc_value, unit, period_label,
                 company_id, line_item_name, base_value, value_type, frequency) = metric_row

                # Find matching observation definition
                obs_config = self._find_observation_for_metric(calc_type)
                if not obs_config:
                    continue

                # Determine materiality threshold  
                line_item_lower = line_item_name.lower().replace(' ', '_')
                materiality = (
                    obs_config.get("materiality") or 
                    self.materiality_by_metric.get(line_item_lower) or
                    self.default_materiality
                )

                # Calculate magnitude and materiality check
                value = float(calc_value) if calc_value else 0.0
                magnitude = abs(value)
                is_material = magnitude >= materiality

                # Build observation object
                observation = Observation(
                    id=obs_config["id"],
                    name=obs_config["name"], 
                    description=obs_config["description"],
                    value=value,
                    magnitude=magnitude,
                    materiality_threshold=materiality,
                    is_material=is_material,
                    calculation_type=calc_type,
                    metric_context={
                        "derived_metric_id": dm_id,
                        "base_metric_id": base_metric_id,
                        "line_item_name": line_item_name,
                        "period_label": period_label,
                        "base_value": float(base_value) if base_value else None,
                        "value_type": value_type,
                        "frequency": frequency,
                        "unit": unit,
                        "company_id": company_id
                    }
                )

                observations.append(observation)

        log_event("observations_computed", {
            "total_observations": len(observations),
            "material_observations": len([o for o in observations if o.is_material])
        })

        return observations

    def _find_observation_for_metric(self, calculation_type: str) -> Optional[Dict[str, Any]]:
        """Find observation definition that matches a calculation type"""
        for obs_config in self.observations_config.get("observations", []):
            params = obs_config.get("params", {})
            if params.get("calculation_type") == calculation_type:
                return obs_config
        return None

    def filter_material_observations(self, observations: List[Observation]) -> List[Observation]:
        """Filter observations by materiality threshold"""
        material_obs = [obs for obs in observations if obs.is_material]

        log_event("materiality_filtering", {
            "total_observations": len(observations),
            "material_observations": len(material_obs),
            "filtered_out": len(observations) - len(material_obs)
        })

        return material_obs

    def generate_questions_from_observations(self, observations: List[Observation]) -> List[Dict[str, Any]]:
        """
        Generate live questions from material observations using ID-based templates.
        This is the core improvement - using IDs not template_keys.
        """
        questions = []
        question_templates = self.questions_config.get("questions", [])

        for observation in observations:
            # Find all question templates for this observation_id
            matching_templates = [
                qt for qt in question_templates 
                if qt.get("observation_id") == observation.id
            ]

            for template_config in matching_templates:
                try:
                    # Render question using Jinja2 template
                    rendered_question = self._render_question_template(
                        template_config, observation
                    )

                    if rendered_question:
                        questions.append(rendered_question)

                except Exception as e:
                    log_event("question_rendering_error", {
                        "template_id": template_config.get("id"),
                        "observation_id": observation.id,
                        "error": str(e)
                    })

        # Rank questions by importance and magnitude
        questions = self._rank_questions(questions)

        log_event("questions_generated", {
            "total_questions": len(questions),
            "observations_processed": len(observations)
        })

        return questions

    def _render_question_template(self, template_config: Dict[str, Any], 
                                  observation: Observation) -> Optional[Dict[str, Any]]:
        """Render a question template with observation context"""

        template_str = template_config.get("template", "")
        if not template_str:
            return None

        # Build template context from observation and metrics
        context = {
            "metric_name": observation.metric_context["line_item_name"],
            "current_value": observation.metric_context.get("base_value", 0),
            "period_label": observation.metric_context["period_label"],
            "value_type": observation.metric_context["value_type"],
            "frequency": observation.metric_context["frequency"],
            "observation_value": observation.value,
            "observation_magnitude": observation.magnitude,
            "materiality_threshold": observation.materiality_threshold,

            # Helper functions for templates
            "percent": lambda current, prior: round((current - prior) / prior * 100, 1) if prior and prior != 0 else 0,
            "format_currency": lambda val: f"${val:,.2f}" if val else "$0.00",
            "format_abs": lambda val: f"+{val:,.2f}" if val > 0 else f"{val:,.2f}",
            "round_smart": lambda val, decimals: round(val, decimals) if val else 0,
            "conditional": lambda condition, true_text, false_text: true_text if condition else false_text
        }

        try:
            # Render template
            template = Template(template_str)
            rendered_text = template.render(**context)

            return {
                "question_id": template_config["id"],
                "observation_id": observation.id,
                "derived_metric_id": observation.metric_context["derived_metric_id"],
                "question_text": rendered_text.strip(),
                "importance": template_config.get("importance", 1),
                "weight": template_config.get("weight", 1.0),
                "magnitude": observation.magnitude,
                "line_item": observation.metric_context["line_item_name"],
                "period_label": observation.metric_context["period_label"],
                "created_at": datetime.now(),
                "metadata": {
                    "observation_name": observation.name,
                    "calculation_type": observation.calculation_type,
                    "materiality_threshold": observation.materiality_threshold,
                    "template_id": template_config["id"]
                }
            }

        except Exception as e:
            log_event("template_rendering_failed", {
                "template_id": template_config.get("id"), 
                "error": str(e)
            })
            return None

    def _rank_questions(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank questions by importance and magnitude"""
        return sorted(questions, key=lambda q: (
            -q["importance"],      # Higher importance first
            -q["magnitude"],       # Higher magnitude first  
            -q["weight"]           # Higher weight first
        ))

    def persist_live_questions(self, questions: List[Dict[str, Any]], conn) -> Dict[str, int]:
        """
        Persist generated questions to live_questions table.
        Uses proper ID-based approach instead of template_key.
        """
        results = {"inserted": 0, "updated": 0, "errors": 0}

        with conn.cursor() as cur:
            for question in questions:
                try:
                    # Check if question already exists for this derived_metric
                    cur.execute("""
                        SELECT id FROM live_questions 
                        WHERE derived_metric_id = %s 
                        AND question_text = %s
                    """, (question["derived_metric_id"], question["question_text"]))

                    existing = cur.fetchone()

                    if existing:
                        # Update existing question
                        cur.execute("""
                            UPDATE live_questions SET
                                status = 'active',
                                updated_at = %s,
                                metadata = %s
                            WHERE id = %s
                        """, (
                            question["created_at"],
                            json.dumps(question["metadata"]),
                            existing[0]
                        ))
                        results["updated"] += 1
                    else:
                        # Insert new question  
                        cur.execute("""
                            INSERT INTO live_questions (
                                derived_metric_id, question_text, importance, 
                                weight, magnitude, status, created_at, updated_at,
                                metadata
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            question["derived_metric_id"],
                            question["question_text"],
                            question["importance"],
                            question["weight"], 
                            question["magnitude"],
                            'active',
                            question["created_at"],
                            question["created_at"],
                            json.dumps(question["metadata"])
                        ))
                        results["inserted"] += 1

                except Exception as e:
                    results["errors"] += 1
                    log_event("question_persistence_error", {
                        "question_id": question.get("question_id"),
                        "error": str(e)
                    })

        return results

    def generate_questions(self) -> Dict[str, Any]:
        """
        Main orchestration method - the new ID-based pipeline.
        Replaces the old template_key approach completely.
        """

        log_event("id_based_question_generation_started", {
            "company_id": self.company_id,
            "timestamp": datetime.now().isoformat()
        })

        try:
            with get_db_connection() as conn:
                # Step 1: Compute observations from derived_metrics  
                observations = self.compute_observations(conn)

                # Step 2: Filter by materiality thresholds
                material_observations = self.filter_material_observations(observations)

                # Step 3: Generate questions using ID-based templates
                questions = self.generate_questions_from_observations(material_observations)

                # Step 4: Persist to live_questions table
                persistence_results = self.persist_live_questions(questions, conn)
                conn.commit()

                # Final results
                results = {
                    "status": "completed",
                    "company_id": self.company_id,
                    "total_observations": len(observations),
                    "material_observations": len(material_observations),
                    "generated_questions": len(questions),
                    "persistence_results": persistence_results,
                    "timestamp": datetime.now().isoformat(),
                    "yaml_driven": True,
                    "id_based": True  # This is the key improvement
                }

                log_event("id_based_question_generation_completed", results)
                return results

        except Exception as e:
            log_event("question_generation_failed", {
                "company_id": self.company_id,
                "error": str(e)
            })
            raise


def main():
    """Main entry point for the new ID-based question generator"""

    if len(sys.argv) != 2:
        print("Usage: python questions_generator.py <company_id>")
        print("Example: python questions_generator.py 1")
        sys.exit(1)

    try:
        company_id = int(sys.argv[1])
    except ValueError:
        print("Error: company_id must be an integer")
        sys.exit(1)

    print(f"🎯 Starting ID-based YAML-driven question generation for company {company_id}")
    print("📝 Using observations.yaml and questions.yaml configurations")
    print("🔄 Pipeline: derived_metrics → observations → materiality_filter → questions → live_questions")
    print()

    try:
        generator = YAMLDrivenQuestionGenerator(company_id)
        results = generator.generate_questions()

        print("✅ ID-based question generation completed successfully!")
        print(f"   📊 Total observations computed: {results['total_observations']}")
        print(f"   🎯 Material observations: {results['material_observations']}")  
        print(f"   ❓ Questions generated: {results['generated_questions']}")
        print(f"   💾 Questions inserted: {results['persistence_results']['inserted']}")
        print(f"   🔄 Questions updated: {results['persistence_results']['updated']}")

        if results['persistence_results']['errors'] > 0:
            print(f"   ⚠️ Errors during persistence: {results['persistence_results']['errors']}")

        print(f"   ⏱️ Completed at: {results['timestamp']}")

    except Exception as e:
        print(f"❌ Question generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
