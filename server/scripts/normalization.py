# server/scripts/normalization.py - ENHANCED VERSION with better error handling
import os
from datetime import datetime, date
from utils import log_event, clean_numeric_value, parse_period

class EnhancedDataNormalizer:
    """
    ENHANCED: Data cleaning, type conversion, and validation with:
    - Robust error handling for missing periods.yaml
    - Better period parsing fallbacks
    - Improved diagnostic logging
    - Graceful handling of partial data
    """

    def __init__(self, file_path: str = None):
        self.file_path = file_path
        self.source_file = os.path.basename(file_path) if file_path else "unknown"

    def normalize_row(self, mapped_row: dict, row_number: int) -> dict:
        """
        ENHANCED: Normalize a mapped row for database insertion with better error handling
        """

        try:
            # Start with the mapped row and preserve _row_number
            normalized = mapped_row.copy()

            # Ensure row number is preserved
            if '_row_number' not in normalized:
                normalized['_row_number'] = row_number

            # Handle datetime objects in period_label (from existing field_mapper.py logic)
            period_label = mapped_row.get("period_label")
            if hasattr(period_label, 'strftime'):  # datetime object
                period_label = period_label.strftime('%Y-%m-%d')
            elif period_label is None:
                period_label = ""
            else:
                period_label = str(period_label).strip()
            normalized["period_label"] = period_label

            # Handle NaN values in notes (from existing field_mapper.py logic)
            notes = mapped_row.get("notes")
            if notes is None or (hasattr(notes, '__name__') and notes.__name__ == 'nan'):
                notes = ""
            else:
                notes = str(notes)
            normalized["notes"] = notes

            # Clean numeric value using existing utility - DON'T REJECT ON None
            raw_value = mapped_row.get("value")
            cleaned_value = clean_numeric_value(raw_value)
            normalized["value"] = cleaned_value  # Keep even if None

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

            # RELAXED validation - only check line_item and period_label exist
            required_fields = ["line_item", "period_label"]
            missing_fields = []

            for field in required_fields:
                field_value = normalized.get(field)
                if not field_value or str(field_value).strip() == "":
                    missing_fields.append(field)

            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")

            # ENHANCED: Parse period with robust error handling
            period_label_clean = normalized.get("period_label", "").strip()
            period_type = normalized.get("period_type", "Monthly")

            if period_label_clean:
                try:
                    # Try to parse period using enhanced parse_period function
                    period_info = parse_period(period_label_clean, period_type)
                    if period_info:
                        normalized["_period_info"] = period_info
                        log_event("period_parsed_successfully", {
                            "row_number": row_number,
                            "period_label": period_label_clean,
                            "period_info": period_info
                        })
                    else:
                        # Create fallback period info
                        normalized["_period_info"] = {
                            "type": period_type,
                            "label": period_label_clean,
                            "start_date": date.today(),
                            "end_date": date.today()
                        }
                        log_event("period_fallback_created", {
                            "row_number": row_number,
                            "period_label": period_label_clean,
                            "reason": "parse_period returned None"
                        })

                except Exception as e:
                    # ENHANCED: More robust fallback handling
                    log_event("period_parsing_error_with_recovery", {
                        "row_number": row_number,
                        "period_label": period_label_clean,
                        "error": str(e),
                        "recovery_action": "Creating basic period info"
                    })

                    # Create basic period info as fallback - don't fail the entire row
                    normalized["_period_info"] = {
                        "type": period_type,
                        "label": period_label_clean,
                        "start_date": date.today(),
                        "end_date": date.today()
                    }
            else:
                raise ValueError("period_label cannot be empty")

            log_event("row_normalized_success", {
                "row_number": row_number,
                "line_item": normalized.get("line_item"),
                "period_label": normalized.get("period_label"),
                "value": cleaned_value,
                "source_file": self.source_file
            })

            return normalized

        except Exception as e:
            log_event("normalization_error_detailed", {
                "row_number": row_number,
                "error": str(e),
                "raw_data_sample": {
                    "line_item": mapped_row.get("line_item"),
                    "period_label": mapped_row.get("period_label"),
                    "value": mapped_row.get("value")
                },
                "source_file": self.source_file
            })
            # Re-raise to let batch handler decide whether to skip or fail
            raise

    def normalize_batch(self, mapped_rows: list) -> tuple:
        """
        ENHANCED: Normalize a batch of mapped rows with better error recovery
        Returns (normalized_rows, error_count)
        """

        normalized_rows = []
        error_count = 0

        log_event("batch_normalization_started", {
            "total_input_rows": len(mapped_rows),
            "source_file": self.source_file
        })

        for i, mapped_row in enumerate(mapped_rows):
            try:
                row_number = mapped_row.get('_row_number', i + 1)
                normalized_row = self.normalize_row(mapped_row, row_number)
                normalized_rows.append(normalized_row)

            except Exception as e:
                error_count += 1
                log_event("row_normalization_skipped", {
                    "row_number": i + 1,
                    "error": str(e),
                    "source_file": self.source_file,
                    "recovery_action": "Continue processing other rows"
                })
                # Continue processing other rows instead of failing entire batch

        log_event("batch_normalization_completed", {
            "total_input_rows": len(mapped_rows),
            "normalized_rows": len(normalized_rows),
            "error_count": error_count,
            "source_file": self.source_file,
            "success_rate": len(normalized_rows) / len(mapped_rows) if mapped_rows else 0
        })

        return normalized_rows, error_count

def normalize_data(mapped_rows: list, file_path: str = None) -> tuple:
    """
    ENHANCED: Convenience function for backward compatibility
    Returns (rows, error_count) with enhanced normalizer
    """
    normalizer = EnhancedDataNormalizer(file_path)
    return normalizer.normalize_batch(mapped_rows)

if __name__ == "__main__":
    # Test normalization with smoke CSV sample
    sample_mapped_row = {
        "_row_number": 1,
        "line_item": "Revenue",
        "period_label": "Feb 2025",
        "value": "2390873",  # String value like from CSV
        "value_type": "Actual",
        "currency": "USD"
    }

    normalizer = EnhancedDataNormalizer("smoke.csv")
    try:
        result = normalizer.normalize_row(sample_mapped_row, 1)
        print(f"✅ Normalized successfully: {result}")
    except Exception as e:
        print(f"❌ Normalization failed: {e}")
