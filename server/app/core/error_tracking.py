"""
Centralized Error Tracking and Management
"""

import logging
import json
import traceback
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
from threading import Lock

from .monitoring import metrics, correlation_id, user_id

@dataclass
class ErrorEvent:
    """Structured error event"""
    error_id: str
    timestamp: datetime
    correlation_id: str
    user_id: str
    error_type: str
    error_message: str
    module: str
    function: str
    line_number: int
    stack_trace: str
    context: Dict[str, Any]
    severity: str = 'ERROR'
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

class ErrorTracker:
    """Centralized error tracking and analytics"""
    
    def __init__(self):
        self.errors: Dict[str, ErrorEvent] = {}
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_patterns: Dict[str, List[str]] = defaultdict(list)
        self.lock = Lock()
        
        # Setup error log files
        self.logs_dir = Path(__file__).parent.parent.parent.parent / 'logs'
        self.logs_dir.mkdir(exist_ok=True)
        self.error_log = self.logs_dir / 'errors.jsonl'
        self.alert_log = self.logs_dir / 'alerts.jsonl'
        
        # Error thresholds for alerting
        self.error_thresholds = {
            'error_rate_per_minute': 10,
            'same_error_count': 5,
            'critical_error_count': 1
        }
    
    def generate_error_id(self, error_type: str, message: str, module: str, function: str) -> str:
        """Generate unique error ID based on error characteristics"""
        error_signature = f"{error_type}:{module}:{function}:{message[:100]}"
        return hashlib.md5(error_signature.encode()).hexdigest()[:12]
    
    def track_error(
        self,
        exception: Exception,
        context: Dict[str, Any] = None,
        severity: str = 'ERROR',
        module: str = None,
        function: str = None
    ) -> str:
        """
        Track an error event
        
        Args:
            exception: The exception that occurred
            context: Additional context information
            severity: Error severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            module: Module where error occurred
            function: Function where error occurred
        
        Returns:
            Error ID for tracking
        """
        # Extract error information
        error_type = type(exception).__name__
        error_message = str(exception)
        
        # Get stack trace information
        tb = traceback.extract_tb(exception.__traceback__)
        if tb:
            last_frame = tb[-1]
            module = module or last_frame.filename.split('/')[-1]
            function = function or last_frame.name
            line_number = last_frame.lineno
        else:
            module = module or 'unknown'
            function = function or 'unknown'
            line_number = 0
        
        stack_trace = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        
        # Generate error ID
        error_id = self.generate_error_id(error_type, error_message, module, function)
        
        # Create error event
        error_event = ErrorEvent(
            error_id=error_id,
            timestamp=datetime.utcnow(),
            correlation_id=correlation_id.get(''),
            user_id=user_id.get(''),
            error_type=error_type,
            error_message=error_message,
            module=module,
            function=function,
            line_number=line_number,
            stack_trace=stack_trace,
            context=context or {},
            severity=severity
        )
        
        with self.lock:
            # Store error event
            self.errors[error_id] = error_event
            self.error_counts[error_id] += 1
            self.error_patterns[error_type].append(error_id)
            
            # Write to error log
            self._write_error_log(error_event)
            
            # Record metrics
            metrics.increment_counter('errors.total', 1, {
                'error_type': error_type,
                'module': module,
                'severity': severity
            })
            
            # Check for alert conditions
            self._check_alert_conditions(error_event)
        
        return error_id
    
    def _write_error_log(self, error_event: ErrorEvent):
        """Write error event to log file"""
        try:
            with open(self.error_log, 'a') as f:
                f.write(json.dumps(error_event.to_dict(), default=str) + '\n')
        except Exception as e:
            logging.error(f"Failed to write error log: {e}")
    
    def _write_alert_log(self, alert_data: Dict[str, Any]):
        """Write alert to alert log"""
        try:
            alert_data['timestamp'] = datetime.utcnow().isoformat()
            with open(self.alert_log, 'a') as f:
                f.write(json.dumps(alert_data, default=str) + '\n')
        except Exception as e:
            logging.error(f"Failed to write alert log: {e}")
    
    def _check_alert_conditions(self, error_event: ErrorEvent):
        """Check if error conditions warrant alerting"""
        error_id = error_event.error_id
        error_type = error_event.error_type
        
        # Check same error count threshold
        if self.error_counts[error_id] >= self.error_thresholds['same_error_count']:
            self._create_alert(
                'REPEATED_ERROR',
                f"Error {error_id} occurred {self.error_counts[error_id]} times",
                {
                    'error_id': error_id,
                    'error_type': error_type,
                    'count': self.error_counts[error_id],
                    'latest_occurrence': error_event.to_dict()
                }
            )
        
        # Check critical error
        if error_event.severity == 'CRITICAL':
            self._create_alert(
                'CRITICAL_ERROR',
                f"Critical error occurred: {error_event.error_message}",
                {
                    'error_event': error_event.to_dict()
                }
            )
        
        # Check error rate
        recent_errors = self._get_recent_error_count(minutes=1)
        if recent_errors >= self.error_thresholds['error_rate_per_minute']:
            self._create_alert(
                'HIGH_ERROR_RATE',
                f"High error rate: {recent_errors} errors in the last minute",
                {
                    'error_count': recent_errors,
                    'time_window_minutes': 1
                }
            )
    
    def _create_alert(self, alert_type: str, message: str, context: Dict[str, Any]):
        """Create an alert"""
        alert_data = {
            'alert_type': alert_type,
            'message': message,
            'context': context,
            'correlation_id': correlation_id.get(''),
            'severity': 'HIGH'
        }
        
        self._write_alert_log(alert_data)
        
        # Record alert metric
        metrics.increment_counter('alerts.total', 1, {
            'alert_type': alert_type
        })
        
        # Log alert
        logging.critical(f"ALERT: {alert_type} - {message}", extra={'alert_data': alert_data})
    
    def _get_recent_error_count(self, minutes: int = 60) -> int:
        """Get count of errors in the last N minutes"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        count = 0
        
        for error_event in self.errors.values():
            if error_event.timestamp >= cutoff:
                count += 1
        
        return count
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the last N hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        with self.lock:
            recent_errors = [
                error for error in self.errors.values()
                if error.timestamp >= cutoff
            ]
            
            if not recent_errors:
                return {
                    'total_errors': 0,
                    'unique_errors': 0,
                    'error_types': {},
                    'top_errors': [],
                    'time_range_hours': hours
                }
            
            # Count by error type
            error_type_counts = Counter(error.error_type for error in recent_errors)
            
            # Get top errors by occurrence
            error_id_counts = Counter(error.error_id for error in recent_errors)
            top_errors = [
                {
                    'error_id': error_id,
                    'count': count,
                    'error_info': self.errors[error_id].to_dict()
                }
                for error_id, count in error_id_counts.most_common(10)
            ]
            
            return {
                'total_errors': len(recent_errors),
                'unique_errors': len(set(error.error_id for error in recent_errors)),
                'error_types': dict(error_type_counts),
                'top_errors': top_errors,
                'time_range_hours': hours,
                'generated_at': datetime.utcnow().isoformat()
            }
    
    def get_error_details(self, error_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific error"""
        with self.lock:
            if error_id not in self.errors:
                return None
            
            error_event = self.errors[error_id]
            return {
                'error_details': error_event.to_dict(),
                'occurrence_count': self.error_counts[error_id],
                'first_seen': error_event.timestamp.isoformat(),
                'related_errors': [
                    err_id for err_id in self.error_patterns[error_event.error_type]
                    if err_id != error_id
                ][:5]  # Limit to 5 related errors
            }
    
    def mark_error_resolved(self, error_id: str) -> bool:
        """Mark an error as resolved"""
        with self.lock:
            if error_id in self.errors:
                self.errors[error_id].resolved = True
                return True
        return False
    
    def clear_old_errors(self, days: int = 30):
        """Clear errors older than N days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        with self.lock:
            old_error_ids = [
                error_id for error_id, error_event in self.errors.items()
                if error_event.timestamp < cutoff
            ]
            
            for error_id in old_error_ids:
                error_event = self.errors.pop(error_id)
                self.error_counts.pop(error_id, None)
                
                # Remove from patterns
                if error_event.error_type in self.error_patterns:
                    try:
                        self.error_patterns[error_event.error_type].remove(error_id)
                    except ValueError:
                        pass
            
            return len(old_error_ids)

# Global error tracker instance
error_tracker = ErrorTracker()

def track_exception(exception: Exception, context: Dict[str, Any] = None, severity: str = 'ERROR') -> str:
    """
    Convenience function to track an exception
    
    Args:
        exception: The exception to track
        context: Additional context information
        severity: Error severity level
    
    Returns:
        Error ID for reference
    """
    return error_tracker.track_error(exception, context, severity)

def error_handler(func):
    """Decorator to automatically track errors in functions"""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Track the error
            track_exception(
                e,
                context={
                    'function': func.__name__,
                    'module': func.__module__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
            )
            # Re-raise the exception
            raise
    
    return wrapper

# Export main functionality
__all__ = [
    'error_tracker',
    'track_exception',
    'error_handler',
    'ErrorEvent',
    'ErrorTracker'
]