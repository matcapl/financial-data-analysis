#!/usr/bin/env python3
"""
scripts/generate_questions.py - YAML-driven Question Templates SQL Generator

PURPOSE:
Generates schema/002_question_templates.sql from config/questions.yaml
Supports the new ID-based system with proper observation_id linking.

FEATURES:
- Reads questions.yaml with ID-based question templates
- Links questions to observations via observation_id foreign keys
- Generates proper SQL schema with all required fields
- Validates YAML structure before generation
- Handles metadata and configuration sections

USAGE:
python scripts/generate_questions.py

FLOW:
config/questions.yaml → scripts/generate_questions.py → schema/002_question_templates.sql
"""

import yaml
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Set up paths
BASE = Path(__file__).parent.parent
CONFIG_PATH = BASE / "config"
QUESTIONS_YAML = CONFIG_PATH / "questions.yaml"
OBSERVATIONS_YAML = CONFIG_PATH / "observations.yaml"
SCHEMA_PATH = BASE / "schema"
OUT_SQL = SCHEMA_PATH / "002_question_templates.sql"


class QuestionTemplateGenerator:
    """
    Generates SQL schema for question templates from YAML configuration.
    Supports the new ID-based system with observation linking.
    """
    
    def __init__(self):
        self.questions_config: Dict[str, Any] = {}
        self.observations_config: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        
    def load_configurations(self) -> bool:
        """Load and validate YAML configurations"""
        try:
            # Load questions configuration
            if QUESTIONS_YAML.exists():
                with open(QUESTIONS_YAML, 'r') as f:
                    self.questions_config = yaml.safe_load(f) or {}
                print(f"✅ Loaded questions config: {QUESTIONS_YAML}")
            else:
                print(f"⚠️  Questions YAML not found: {QUESTIONS_YAML}")
                return False
            
            # Load observations configuration for validation
            if OBSERVATIONS_YAML.exists():
                with open(OBSERVATIONS_YAML, 'r') as f:
                    self.observations_config = yaml.safe_load(f) or {}
                print(f"✅ Loaded observations config: {OBSERVATIONS_YAML}")
            else:
                print(f"⚠️  Observations YAML not found: {OBSERVATIONS_YAML}")
            
            # Extract metadata
            self.metadata = self.questions_config.get("metadata", {})
            
            return True
            
        except yaml.YAMLError as e:
            print(f"❌ YAML parsing error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error loading configurations: {e}")
            return False
    
    def validate_questions(self) -> bool:
        """Validate question structure and references"""
        questions = self.questions_config.get("questions", [])
        observations = self.observations_config.get("observations", [])
        
        if not questions:
            print("⚠️  No questions found in configuration")
            return True  # Not an error, just empty
        
        # Get valid observation IDs for validation
        valid_obs_ids = {obs["id"] for obs in observations}
        
        errors = []
        warnings = []
        
        for i, question in enumerate(questions):
            q_id = question.get("id")
            obs_id = question.get("observation_id")
            
            # Required fields validation
            if not q_id:
                errors.append(f"Question #{i}: Missing 'id' field")
            if not obs_id:
                errors.append(f"Question #{i}: Missing 'observation_id' field")
            if not question.get("template"):
                errors.append(f"Question #{i}: Missing 'template' field")
            if not question.get("category"):
                errors.append(f"Question #{i}: Missing 'category' field")
            if not question.get("priority"):
                errors.append(f"Question #{i}: Missing 'priority' field")
            if not question.get("importance"):
                errors.append(f"Question #{i}: Missing 'importance' field")
            
            # Reference validation
            if obs_id and obs_id not in valid_obs_ids:
                warnings.append(f"Question #{i} (ID:{q_id}): References unknown observation_id {obs_id}")
            
            # ID range validation
            if q_id and (q_id < 30001 or q_id > 39999):
                warnings.append(f"Question #{i}: ID {q_id} outside recommended range (30001-39999)")
        
        # Print validation results
        if errors:
            print(f"❌ Validation errors ({len(errors)}):")
            for error in errors:
                print(f"   {error}")
            return False
        
        if warnings:
            print(f"⚠️  Validation warnings ({len(warnings)}):")
            for warning in warnings:
                print(f"   {warning}")
        
        print(f"✅ Validated {len(questions)} question templates")
        return True
    
    def generate_sql_schema(self) -> str:
        """Generate the complete SQL schema"""
        questions = self.questions_config.get("questions", [])
        metadata = self.metadata
        
        # Build SQL content
        lines = [
            "-- Auto-generated by scripts/generate_questions.py",
            f"-- Generated from: {QUESTIONS_YAML}",
            f"-- Version: {metadata.get('version', 'unknown')}",
            f"-- Description: {metadata.get('description', 'Question templates for board-level analysis')}",
            f"-- Timestamp: {metadata.get('timestamp', 'unknown')}",
            "",
            "-- =============================================",
            "-- Question Templates Table",
            "-- =============================================",
            "",
            "-- Drop existing table and dependencies",
            "DROP TABLE IF EXISTS question_templates CASCADE;",
            "",
            "-- Create question_templates table with full schema",
            "CREATE TABLE question_templates (",
            "    id INTEGER PRIMARY KEY,",
            "    observation_id INTEGER NOT NULL,",
            "    importance INTEGER NOT NULL DEFAULT 1,",
            "    category TEXT NOT NULL DEFAULT 'general',",
            "    priority TEXT NOT NULL DEFAULT 'medium',",
            "    template TEXT NOT NULL,",
            "    weight NUMERIC DEFAULT 1.0,",
            "    metadata JSONB DEFAULT '{}'::jsonb,",
            "    created_at TIMESTAMP DEFAULT NOW() NOT NULL,",
            "    updated_at TIMESTAMP DEFAULT NOW() NOT NULL",
            ");",
            "",
            "-- Create indexes for performance",
            "CREATE INDEX IF NOT EXISTS idx_question_templates_observation_id ON question_templates(observation_id);",
            "CREATE INDEX IF NOT EXISTS idx_question_templates_category ON question_templates(category);",
            "CREATE INDEX IF NOT EXISTS idx_question_templates_priority ON question_templates(priority);",
            "CREATE INDEX IF NOT EXISTS idx_question_templates_importance ON question_templates(importance DESC);",
            "",
        ]
        
        # Insert question templates if we have any
        if questions:
            lines.extend([
                "-- Insert question templates",
                "INSERT INTO question_templates (",
                "    id, observation_id, importance, category, priority, template, weight, metadata",
                ") VALUES"
            ])
            
            # Build values for each question
            question_values = []
            for question in questions:
                q_id = question["id"]
                obs_id = question["observation_id"]
                importance = question["importance"]
                category = self._sql_escape(question["category"])
                priority = self._sql_escape(question["priority"])
                template = self._sql_escape(question["template"])
                weight = question.get("weight", 1.0)
                
                # Build metadata JSON
                metadata_obj = {}
                for key in ["description", "conditions", "context_variables", "target_audience"]:
                    if key in question:
                        metadata_obj[key] = question[key]
                
                metadata_json = json.dumps(metadata_obj).replace("'", "''")
                
                question_values.append(
                    f"    ({q_id}, {obs_id}, {importance}, '{category}', '{priority}', "
                    f"'{template}', {weight}, '{metadata_json}'::jsonb)"
                )
            
            lines.append(",\n".join(question_values))
            lines.extend([
                "ON CONFLICT (id) DO UPDATE SET",
                "    observation_id = EXCLUDED.observation_id,",
                "    importance = EXCLUDED.importance,",
                "    category = EXCLUDED.category,",
                "    priority = EXCLUDED.priority,",
                "    template = EXCLUDED.template,",
                "    weight = EXCLUDED.weight,",
                "    metadata = EXCLUDED.metadata,",
                "    updated_at = NOW();",
                "",
            ])
        else:
            lines.extend([
                "-- No question templates to insert",
                "",
            ])
        
        # Add configuration table for global settings
        lines.extend([
            "-- =============================================",
            "-- Configuration Storage Table",
            "-- =============================================",
            "",
            "-- Create configuration table if not exists",
            "CREATE TABLE IF NOT EXISTS question_generation_config (",
            "    id SERIAL PRIMARY KEY,",
            "    config_key TEXT NOT NULL UNIQUE,",
            "    config_value JSONB NOT NULL,",
            "    description TEXT,",
            "    created_at TIMESTAMP DEFAULT NOW() NOT NULL,",
            "    updated_at TIMESTAMP DEFAULT NOW() NOT NULL",
            ");",
            "",
        ])
        
        # Insert global configuration from metadata
        config_entries = []
        
        # Store rendering helpers
        if "rendering_helpers" in metadata:
            helpers_json = json.dumps(metadata["rendering_helpers"]).replace("'", "''")
            config_entries.append(
                f"    ('rendering_helpers', '{helpers_json}'::jsonb, 'Available template rendering functions')"
            )
        
        # Store selection logic
        if "selection_logic" in metadata:
            logic_json = json.dumps(metadata["selection_logic"]).replace("'", "''")
            config_entries.append(
                f"    ('selection_logic', '{logic_json}'::jsonb, 'Question selection and ranking logic')"
            )
        
        # Store metadata
        metadata_clean = {k: v for k, v in metadata.items() 
                         if k not in ["rendering_helpers", "selection_logic"]}
        if metadata_clean:
            meta_json = json.dumps(metadata_clean).replace("'", "''")
            config_entries.append(
                f"    ('metadata', '{meta_json}'::jsonb, 'Question template metadata and configuration')"
            )
        
        if config_entries:
            lines.extend([
                "-- Insert configuration data",
                "INSERT INTO question_generation_config (config_key, config_value, description) VALUES",
                ",\n".join(config_entries),
                "ON CONFLICT (config_key) DO UPDATE SET",
                "    config_value = EXCLUDED.config_value,",
                "    description = EXCLUDED.description,",
                "    updated_at = NOW();",
                "",
            ])
        
        # Add summary and statistics
        stats = self._generate_statistics(questions)
        lines.extend([
            "-- =============================================", 
            "-- Generation Summary",
            "-- =============================================",
            "",
            f"-- Generated {stats['total_questions']} question templates",
            f"-- Categories: {', '.join(stats['categories'])}",
            f"-- Priority distribution: {stats['priority_distribution']}",
            f"-- Importance range: {stats['importance_range']}",
            f"-- Linked observations: {stats['linked_observations']}",
            "",
            "-- Schema generation completed successfully",
            ""
        ])
        
        return "\n".join(lines)
    
    def _sql_escape(self, text: str) -> str:
        """Escape SQL string literals"""
        if not isinstance(text, str):
            return str(text)
        return text.replace("'", "''").replace("\n", "\\n").replace("\r", "\\r")
    
    def _generate_statistics(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate statistics about the questions"""
        if not questions:
            return {
                'total_questions': 0,
                'categories': [],
                'priority_distribution': {},
                'importance_range': 'N/A',
                'linked_observations': []
            }
        
        categories = list(set(q.get("category", "unknown") for q in questions))
        priorities = [q.get("priority", "medium") for q in questions]
        priority_dist = {p: priorities.count(p) for p in set(priorities)}
        
        importances = [q.get("importance", 1) for q in questions]
        importance_range = f"{min(importances)}-{max(importances)}"
        
        observations = list(set(q.get("observation_id") for q in questions if q.get("observation_id")))
        
        return {
            'total_questions': len(questions),
            'categories': sorted(categories),
            'priority_distribution': priority_dist,
            'importance_range': importance_range,
            'linked_observations': sorted(observations)
        }
    
    def write_sql_file(self, sql_content: str) -> bool:
        """Write the generated SQL to file"""
        try:
            # Ensure schema directory exists
            SCHEMA_PATH.mkdir(exist_ok=True)
            
            # Write SQL file
            with open(OUT_SQL, 'w', encoding='utf-8') as f:
                f.write(sql_content)
            
            print(f"✅ Generated SQL schema: {OUT_SQL}")
            return True
            
        except Exception as e:
            print(f"❌ Error writing SQL file: {e}")
            return False
    
    def generate(self) -> bool:
        """Main generation method"""
        print("🎯 Starting YAML-driven question templates generation")
        print(f"📁 Reading from: {QUESTIONS_YAML}")
        print(f"📝 Writing to: {OUT_SQL}")
        print()
        
        # Load configurations
        if not self.load_configurations():
            return False
        
        # Validate question structure
        if not self.validate_questions():
            return False
        
        # Generate SQL schema
        try:
            sql_content = self.generate_sql_schema()
        except Exception as e:
            print(f"❌ Error generating SQL schema: {e}")
            return False
        
        # Write SQL file
        if not self.write_sql_file(sql_content):
            return False
        
        # Print success summary
        questions = self.questions_config.get("questions", [])
        stats = self._generate_statistics(questions)
        
        print()
        print("✅ Question template generation completed successfully!")
        print(f"📊 Generated {stats['total_questions']} question templates")
        print(f"📂 Categories: {', '.join(stats['categories'])}")
        print(f"🎯 Priority distribution: {stats['priority_distribution']}")
        print(f"🔗 Linked to {len(stats['linked_observations'])} observations")
        print(f"⚖️  Importance range: {stats['importance_range']}")
        
        return True


def main():
    """Main entry point"""
    try:
        generator = QuestionTemplateGenerator()
        success = generator.generate()
        
        if not success:
            print("\n❌ Generation failed - check errors above")
            sys.exit(1)
        
        print("\n🎉 Ready for CI pipeline: run ci/02_reset_db.sh to apply schema")
        
    except KeyboardInterrupt:
        print("\n⏹️  Generation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()