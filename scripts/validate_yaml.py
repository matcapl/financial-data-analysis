#!/usr/bin/env python3
"""
Validate all YAML configs in config/:
 - fields.yaml against FieldsYaml model
 - observations.yaml against ObservationsYaml model
 - questions.yaml against QuestionsYaml model
 - periods.yaml, taxonomy.yaml, tables.yaml for syntax
"""
import sys
from pathlib import Path
import yaml
from pydantic import BaseModel, field_validator, ValidationError
from typing import List, Dict, Optional, Any, Union

# --- Pydantic Models for strict validation ---

class FieldConfig(BaseModel):
    id: int
    sql_type: str
    synonyms: List[str]
    description: str

    @field_validator('sql_type')
    @classmethod
    def check_sql_type(cls, v):
        allowed = {'TEXT', 'NUMERIC', 'DATE', 'INT'}
        if v not in allowed:
            raise ValueError(f"Invalid sql_type '{v}', must be one of {allowed}")
        return v

class LineItemConfig(BaseModel):
    id: int
    name: str
    aliases: List[str]
    description: str

class ObservParams(BaseModel):
    lookback: Optional[Union[int, str]] = None
    window: Optional[int] = None
    reference: Optional[str] = None

class ObservationConfig(BaseModel):
    id: int
    name: str
    description: str
    formula: str
    params: ObservParams
    materiality: Optional[float]

class QuestionTemplate(BaseModel):
    id: int
    observation_id: int
    importance: int
    template: str

    @field_validator('importance')
    @classmethod
    def check_importance(cls, v):
        if not (1 <= v <= 5):
            raise ValueError("importance must be between 1 and 5")
        return v

class FieldsYaml(BaseModel):
    fields: Dict[str, FieldConfig]
    line_items: List[LineItemConfig]

class ObservationsYaml(BaseModel):
    observations: List[ObservationConfig]

class QuestionsYaml(BaseModel):
    questions: List[QuestionTemplate]

# --- Helper to load any YAML file ---

def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except Exception as e:
        print(f"❌ Error loading YAML {path.name}: {e}", file=sys.stderr)
        sys.exit(1)

# --- Validation steps ---

def main():
    cfg = Path(__file__).parent.parent / 'config'

    # 1. fields.yaml
    data = load_yaml(cfg / 'fields.yaml')
    try:
        FieldsYaml.model_validate(data)
        print("✅ fields.yaml OK")
    except ValidationError as e:
        print("❌ fields.yaml errors:\n", e, file=sys.stderr)
        sys.exit(1)

    # 2. observations.yaml
    data = load_yaml(cfg / 'observations.yaml')
    try:
        ObservationsYaml.model_validate(data)
        print("✅ observations.yaml OK")
    except ValidationError as e:
        print("❌ observations.yaml errors:\n", e, file=sys.stderr)
        sys.exit(1)

    # 3. questions.yaml
    data = load_yaml(cfg / 'questions.yaml')
    try:
        QuestionsYaml.model_validate(data)
        print("✅ questions.yaml OK")
    except ValidationError as e:
        print("❌ questions.yaml errors:\n", e, file=sys.stderr)
        sys.exit(1)

    # 4. periods.yaml syntax only
    _ = load_yaml(cfg / 'periods.yaml')
    print("✅ periods.yaml syntactically valid")

    # 5. taxonomy.yaml syntax only
    _ = load_yaml(cfg / 'taxonomy.yaml')
    print("✅ taxonomy.yaml syntactically valid")

    # 6. tables.yaml syntax only
    _ = load_yaml(cfg / 'tables.yaml')
    print("✅ tables.yaml syntactically valid")

if __name__ == '__main__':
    main()
