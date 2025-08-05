#!/usr/bin/env python3
"""
Validate config/fields.yaml, config/observations.yaml, and config/questions.yaml
against predefined schemas using Pydantic V2.
"""

import sys
import yaml
from pathlib import Path
from pydantic import BaseModel, field_validator, model_validator, ValidationError
from typing import List, Dict, Optional, Any, Union

# ------------ Pydantic Models ------------

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

# ------------ Validation Logic ------------

def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except Exception as e:
        print(f"Error loading YAML {path}: {e}", file=sys.stderr)
        sys.exit(1)

def validate():
    base = Path(__file__).parent.parent / 'config'

    # Validate fields.yaml
    fdata = load_yaml(base / 'fields.yaml')
    try:
        FieldsYaml.model_validate(fdata)
        print("fields.yaml OK")
    except ValidationError as e:
        print("fields.yaml validation errors:", e, file=sys.stderr)
        sys.exit(1)

    # Validate observations.yaml
    odata = load_yaml(base / 'observations.yaml')
    try:
        ObservationsYaml.model_validate(odata)
        print("observations.yaml OK")
    except ValidationError as e:
        print("observations.yaml validation errors:", e, file=sys.stderr)
        sys.exit(1)

    # Validate questions.yaml
    qdata = load_yaml(base / 'questions.yaml')
    try:
        QuestionsYaml.model_validate(qdata)
        print("questions.yaml OK")
    except ValidationError as e:
        print("questions.yaml validation errors:", e, file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    validate()
