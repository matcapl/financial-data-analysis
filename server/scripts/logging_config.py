"""
Python Logging Configuration
Provides structured logging for Python scripts matching Node.js logging format
"""

import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent.parent / 'logs'
logs_dir.mkdir(exist_ok=True)

class StructuredFormatter(logging.Formatter):
    """Custom formatter to output structured JSON logs"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log structure
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'service': getattr(record, 'service', 'python-script'),
            'message': record.getMessage()
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_data') and record.extra_data:
            log_data.update(record.extra_data)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for development"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        service = getattr(record, 'service', 'python-script')
        
        log_msg = f"{timestamp} [{color}{record.levelname}{reset}] [{service}] {record.getMessage()}"
        
        # Add extra data if present
        if hasattr(record, 'extra_data') and record.extra_data:
            log_msg += f" {json.dumps(record.extra_data, indent=2)}"
        
        return log_msg

def setup_logger(service_name: str = 'python-script', level: str = 'INFO') -> logging.Logger:
    """
    Setup a structured logger for Python scripts
    
    Args:
        service_name: Name of the service/script
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Avoid duplicate handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Console handler for development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredConsoleFormatter())
    logger.addHandler(console_handler)
    
    # File handler for structured logs
    file_handler = logging.FileHandler(logs_dir / f'{service_name}.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(StructuredFormatter())
    logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.FileHandler(logs_dir / f'{service_name}-error.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    logger.addHandler(error_handler)
    
    return logger

def log_with_context(logger: logging.Logger, level: str, message: str, **context):
    """
    Log a message with additional context data
    
    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **context: Additional context data
    """
    record = logger.makeRecord(
        logger.name, 
        getattr(logging, level.upper()),
        __file__, 
        0, 
        message, 
        (), 
        None
    )
    record.service = getattr(logger, 'name', 'python-script')
    record.extra_data = context
    logger.handle(record)

def log_pipeline_step(logger: logging.Logger, step: str, success: bool, **metadata):
    """Log a pipeline step with structured data"""
    level = 'info' if success else 'error'
    log_with_context(
        logger, 
        level, 
        f"Pipeline Step: {step}",
        step=step,
        success=success,
        **metadata
    )

def log_database_operation(logger: logging.Logger, operation: str, table: str, success: bool, **metadata):
    """Log a database operation with structured data"""
    level = 'info' if success else 'error'
    log_with_context(
        logger,
        level,
        f"Database {operation}",
        operation=operation,
        table=table,
        success=success,
        **metadata
    )

def log_file_operation(logger: logging.Logger, operation: str, file_path: str, success: bool, **metadata):
    """Log a file operation with structured data"""
    level = 'info' if success else 'error'
    log_with_context(
        logger,
        level,
        f"File {operation}",
        operation=operation,
        filePath=Path(file_path).name,  # Only log filename for security
        success=success,
        **metadata
    )

# Pre-configured loggers for common scripts
pipeline_logger = setup_logger('pipeline-processor')
extraction_logger = setup_logger('data-extraction')
normalization_logger = setup_logger('data-normalization')
persistence_logger = setup_logger('data-persistence')
metrics_logger = setup_logger('metrics-calculator')
questions_logger = setup_logger('questions-generator')
report_logger = setup_logger('report-generator')

# Export main functions
__all__ = [
    'setup_logger',
    'log_with_context',
    'log_pipeline_step',
    'log_database_operation',
    'log_file_operation',
    'pipeline_logger',
    'extraction_logger',
    'normalization_logger',
    'persistence_logger',
    'metrics_logger',
    'questions_logger',
    'report_logger'
]