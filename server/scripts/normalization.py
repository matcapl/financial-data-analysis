# server/scripts/normalization.py - Data cleaning and validation layer
import os
from datetime import datetime, date
from decimal import Decimal
from utils import log_event, clean_numeric_value, parse_period


class DataNormalizer:
    """Handles data cleaning, type conversion, and validation"""
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path
        self.source_file = os.path.basename(file_path) if file_path else "unknown"
        
    def normalize_row(self, mapped_row: dict, row_number: int) -> dict:
        """
        Normalize a mapped row for database insertion
        Uses existing utility functions from utils.py
        """
        
        try:
            # Start with the mapped row
            normalized = mapped_row.copy()
            
            # Handle datetime objects in period_label (from existing field_mapper.py logic)
            period_label = mapped_row.get("period_label")
            if hasattr(period_label, 'strftime'):  # datetime object
                period_label = period_label.strftime('%Y-%m-%d')
            elif period_label is None:
                period_label = ""
            else:
                period_label = str(period_label)
            normalized["period_label"] = period_label
            
            # Handle NaN values in notes (from existing field_mapper.py logic)
            notes = mapped_row.get("notes")
            if notes is None or (hasattr(notes, '__name__') and notes.__name__ == 'nan'):
                notes = ""
            else:
                notes = str(notes)
            normalized["notes"] = notes
            
            # Clean numeric value using existing utility
            raw_value = mapped_row.get("value")
            cleaned_value = clean_numeric_value(raw_value)
            normalized["value"] = cleaned_value
            
            # Set defaults (consistent with existing ingest_xlsx.py defaults)
            defaults = {
                "statement_type": None,
                "category": None,
                "value_type": normalized.get("value_type") or "Actual",
                "frequency": normalized.get("frequency") or normalized.get("period_type") or "Monthly",
                "currency": normalized.get("currency") or "USD",
                "source_file": self.source_file,
                "source_page": int(mapped_row.get("source_page", 1)),
                "source_type": "Raw"
            }
            
            for key, default_value in defaults.items():
                if not normalized.get(key):
                    normalized[key] = default_value
                    
            # Validate required fields
            required_fields = ["line_item", "period_label", "value"]
            missing_fields = [field for field in required_fields if not normalized.get(field)]
            
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
                
            # Parse period using existing utility
            if normalized.get("period_label"):
                period_info = parse_period(normalized["period_label"], normalized.get("period_type", "Monthly"))
                if period_info:
                    normalized["_period_info"] = period_info  # Store for persistence layer
                    
            log_event("row_normalized", {
                "row_number": row_number,
                "line_item": normalized.get("line_item"),
                "period_label": normalized.get("period_label"),
                "value": cleaned_value,
                "source_file": self.source_file
            })
            
            return normalized
            
        except Exception as e:
            log_event("normalization_error", {
                "row_number": row_number,
                "error": str(e),
                "raw_data": mapped_row,
                "source_file": self.source_file
            })
            raise ValueError(f"Row {row_number} normalization failed: {e}")
            
    def normalize_batch(self, mapped_rows: list) -> list:
        """Normalize a batch of mapped rows, filtering out invalid ones"""
        
        normalized_rows = []
        error_count = 0
        
        for i, mapped_row in enumerate(mapped_rows):
            try:
                row_number = mapped_row.get('_row_number', i + 1)
                normalized_row = self.normalize_row(mapped_row, row_number)
                normalized_rows.append(normalized_row)
            except ValueError as e:
                error_count += 1
                log_event("row_normalization_skipped", {
                    "row_number": i + 1,
                    "error": str(e),
                    "source_file": self.source_file
                })
                # Skip invalid rows rather than failing the entire batch
                continue
                
        log_event("batch_normalization_completed", {
            "total_input_rows": len(mapped_rows),
            "normalized_rows": len(normalized_rows),
            "error_count": error_count,
            "source_file": self.source_file
        })
        
        return normalized_rows


def normalize_data(mapped_rows: list, file_path: str = None) -> list:
    """Convenience function for backward compatibility"""
    normalizer = DataNormalizer(file_path)
    return normalizer.normalize_batch(mapped_rows)


if __name__ == "__main__":
    # Test normalization with sample data
    sample_mapped_row = {
        "line_item": "Revenue",
        "period_label": "Feb 2025",
        "value": "1,000,000",
        "value_type": "Actual",
        "currency": "USD"
    }
    
    normalizer = DataNormalizer("test.csv")
    try:
        result = normalizer.normalize_row(sample_mapped_row, 1)
        print(f"Normalized: {result}")
    except Exception as e:
        print(f"Normalization failed: {e}")