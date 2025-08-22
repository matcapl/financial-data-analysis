#!/usr/bin/env python3
"""
Enhanced Excel/CSV Data Ingestion Module - CORRECTED VERSION

This module integrates with the EXISTING configuration system:
- Uses taxonomy.yaml for field mapping
- Uses periods.yaml for date normalization  
- Preserves existing business logic
- Maintains compatibility with current database schema

Author: Financial Data Analysis Team
Version: 2.1 (Corrected)
"""

import pandas as pd
import numpy as np
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Any
import os
import re
from datetime import datetime
import warnings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExcelCSVIngester:
    """
    Enhanced ingester that INTEGRATES with existing YAML configuration system
    """

    def __init__(self, config_dir: str = "config"):
        """Initialize with existing configuration directory structure"""
        self.config_dir = Path(config_dir)
        self.taxonomy = {}
        self.periods_config = {}
        self.fields_config = {}
        self.observations_config = {}

        self._load_existing_configurations()

    def _load_existing_configurations(self):
        """Load EXISTING configuration files - don't recreate them"""
        try:
            # Load taxonomy.yaml - for field standardization
            taxonomy_file = self.config_dir / 'taxonomy.yaml'
            if taxonomy_file.exists():
                with open(taxonomy_file, 'r') as f:
                    self.taxonomy = yaml.safe_load(f)
                logger.info(f"Loaded existing taxonomy from {taxonomy_file}")

            # Load periods.yaml - for date/period normalization
            periods_file = self.config_dir / 'periods.yaml'  
            if periods_file.exists():
                with open(periods_file, 'r') as f:
                    self.periods_config = yaml.safe_load(f)
                logger.info(f"Loaded existing periods config from {periods_file}")

            # Load fields.yaml - for column recognition
            fields_file = self.config_dir / 'fields.yaml'
            if fields_file.exists():
                with open(fields_file, 'r') as f:
                    self.fields_config = yaml.safe_load(f)
                logger.info(f"Loaded existing fields config from {fields_file}")

            # Load observations.yaml - for validation rules
            observations_file = self.config_dir / 'observations.yaml'
            if observations_file.exists():
                with open(observations_file, 'r') as f:
                    self.observations_config = yaml.safe_load(f)
                logger.info(f"Loaded existing observations config from {observations_file}")

        except Exception as e:
            logger.error(f"Failed to load existing configurations: {e}")
            raise

    def standardize_field_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Use existing taxonomy.yaml to standardize field names
        """
        if not self.taxonomy:
            logger.warning("No taxonomy configuration loaded")
            return df

        try:
            # Use the existing taxonomy structure
            if 'line_items' in self.taxonomy:
                line_items = self.taxonomy['line_items']

                mapping = {}
                for canonical_name, item_config in line_items.items():
                    if 'synonyms' in item_config:
                        for synonym in item_config['synonyms']:
                            # Case-insensitive matching
                            for col in df.columns:
                                if col.lower().strip() == synonym.lower().strip():
                                    mapping[col] = canonical_name
                                    logger.info(f"Mapped '{col}' -> '{canonical_name}' via taxonomy")

                df = df.rename(columns=mapping)

            return df

        except Exception as e:
            logger.error(f"Error applying taxonomy mapping: {e}")
            return df

    def normalize_periods(self, period_series: pd.Series) -> pd.Series:
        """
        Use existing periods.yaml to normalize period formats to ISO canonical
        """
        if not self.periods_config:
            logger.warning("No periods configuration loaded")
            return period_series

        try:
            # Use existing period alias structure
            if 'period_aliases' in self.periods_config:
                period_aliases = self.periods_config['period_aliases']

                def normalize_single_period(raw_period):
                    if pd.isna(raw_period):
                        return raw_period

                    raw_str = str(raw_period).strip()

                    # Direct lookup in existing aliases
                    for canonical, alias_config in period_aliases.items():
                        if 'aliases' in alias_config:
                            for alias in alias_config['aliases']:
                                if raw_str.lower() == alias.lower():
                                    return canonical

                    # If no match found, return original
                    logger.warning(f"Could not normalize period: {raw_period}")
                    return raw_period

                return period_series.apply(normalize_single_period)

            return period_series

        except Exception as e:
            logger.error(f"Error normalizing periods: {e}")
            return period_series

    def validate_with_existing_rules(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Apply existing validation rules from observations.yaml
        """
        validation_results = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }

        if not self.observations_config:
            logger.warning("No observations configuration loaded")
            return validation_results

        try:
            # Apply existing business rules
            if 'business_rules' in self.observations_config:
                rules = self.observations_config['business_rules']

                # Example: Check accounting equation if configured
                if 'accounting_equation' in rules:
                    rule = rules['accounting_equation']
                    if all(col in df.columns for col in ['Total Assets', 'Total Liabilities', 'Total Equity']):
                        assets = df['Total Assets'].dropna()
                        liabilities = df['Total Liabilities'].dropna()
                        equity = df['Total Equity'].dropna()

                        if len(assets) > 0 and len(liabilities) > 0 and len(equity) > 0:
                            # Check if Assets = Liabilities + Equity
                            tolerance = rule.get('tolerance', 0.01)
                            for i in range(min(len(assets), len(liabilities), len(equity))):
                                diff = abs(assets.iloc[i] - (liabilities.iloc[i] + equity.iloc[i]))
                                if diff > tolerance * assets.iloc[i]:
                                    validation_results['warnings'].append(
                                        f"Accounting equation violation at row {i}: "
                                        f"Assets ({assets.iloc[i]}) ≠ Liabilities + Equity ({liabilities.iloc[i] + equity.iloc[i]})"
                                    )

            return validation_results

        except Exception as e:
            logger.error(f"Error in validation: {e}")
            validation_results['errors'].append(f"Validation error: {e}")
            return validation_results

    def read_excel_file(self, file_path: Union[str, Path]) -> Dict[str, pd.DataFrame]:
        """Enhanced Excel reading with comprehensive error handling"""
        file_path = Path(file_path)
        logger.info(f"Reading Excel file: {file_path}")

        try:
            # Read all sheets
            excel_data = pd.read_excel(file_path, sheet_name=None, na_values=['', 'N/A', 'NA'])

            processed_sheets = {}
            for sheet_name, df in excel_data.items():
                if not df.empty:
                    # Clean the dataframe
                    df = df.dropna(how='all').dropna(axis=1, how='all')

                    # Apply existing configuration-based processing
                    df = self.standardize_field_names(df)

                    # Normalize period columns if they exist
                    for col in df.columns:
                        if any(period_term in col.lower() for period_term in ['period', 'date', 'month', 'quarter']):
                            df[col] = self.normalize_periods(df[col])

                    processed_sheets[sheet_name] = df

            return processed_sheets

        except Exception as e:
            logger.error(f"Failed to read Excel file: {e}")
            raise

    def read_csv_file(self, file_path: Union[str, Path]) -> pd.DataFrame:
        """Enhanced CSV reading with encoding detection"""
        file_path = Path(file_path)
        logger.info(f"Reading CSV file: {file_path}")

        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding, na_values=['', 'N/A', 'NA'])

                if not df.empty:
                    # Clean and process
                    df = df.dropna(how='all').dropna(axis=1, how='all')
                    df = self.standardize_field_names(df)

                    # Normalize periods
                    for col in df.columns:
                        if any(period_term in col.lower() for period_term in ['period', 'date', 'month', 'quarter']):
                            df[col] = self.normalize_periods(df[col])

                    logger.info(f"Successfully read CSV with {encoding} encoding")
                    return df

            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Error reading CSV with {encoding}: {e}")
                continue

        raise ValueError(f"Could not read CSV file with any encoding: {encodings}")

    def ingest_file(self, file_path: Union[str, Path]) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
        """
        Main ingestion method that uses existing configuration system
        """
        file_path = Path(file_path)
        start_time = datetime.now()

        logger.info(f"Starting ingestion with existing config system: {file_path}")

        # Determine file type
        extension = file_path.suffix.lower()

        try:
            if extension in ['.xlsx', '.xls']:
                data = self.read_excel_file(file_path)
            elif extension == '.csv':
                df = self.read_csv_file(file_path)
                data = {'Sheet1': df}
            else:
                raise ValueError(f"Unsupported file format: {extension}")

            # Validate using existing rules
            validation_results = {}
            for sheet_name, df in data.items():
                validation_results[sheet_name] = self.validate_with_existing_rules(df)

            # Create metadata
            metadata = {
                'file_path': str(file_path),
                'ingestion_timestamp': datetime.now().isoformat(),
                'processing_time_seconds': (datetime.now() - start_time).total_seconds(),
                'sheets_processed': list(data.keys()),
                'validation_results': validation_results,
                'used_existing_config': True,  # Flag to indicate we used existing system
                'config_files_loaded': {
                    'taxonomy': bool(self.taxonomy),
                    'periods': bool(self.periods_config),
                    'fields': bool(self.fields_config),  
                    'observations': bool(self.observations_config)
                }
            }

            logger.info(f"Ingestion completed using existing config in {metadata['processing_time_seconds']:.2f}s")

            return data, metadata

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            raise


def main():
    """Test the corrected ingester with existing configuration"""
    try:
        # Initialize with existing config directory
        ingester = ExcelCSVIngester(config_dir='config')

        # Test files
        test_files = ['data/financial_data_template.csv', 'data/sample_data.xlsx']

        for file_path in test_files:
            if Path(file_path).exists():
                try:
                    data, metadata = ingester.ingest_file(file_path)
                    print(f"\nProcessed: {file_path}")
                    print(f"Used existing config: {metadata['used_existing_config']}")
                    print(f"Config files loaded: {metadata['config_files_loaded']}")

                except Exception as e:
                    print(f"Failed to process {file_path}: {e}")

    except Exception as e:
        print(f"Failed to initialize ingester: {e}")


if __name__ == "__main__":
    main()