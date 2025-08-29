"""
Enhanced Monitoring and Logging with Correlation IDs and Metrics
"""

import logging
import json
import time
import uuid
import psutil
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
from contextvars import ContextVar
from functools import wraps
from dataclasses import dataclass, asdict

# Context variables for correlation tracking
correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')
request_start_time: ContextVar[float] = ContextVar('request_start_time', default=0.0)
user_id: ContextVar[str] = ContextVar('user_id', default='')

@dataclass
class MetricEvent:
    """Structured metric event"""
    name: str
    value: float
    unit: str = 'count'
    tags: Dict[str, str] = None
    timestamp: datetime = None
    correlation_id: str = ''
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.tags is None:
            self.tags = {}
        if not self.correlation_id:
            self.correlation_id = correlation_id.get('')

class CorrelationFormatter(logging.Formatter):
    """Enhanced formatter with correlation IDs and request tracking"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Get correlation context
        correlation = correlation_id.get('')
        start_time = request_start_time.get(0.0)
        user = user_id.get('')
        
        # Calculate request duration if available
        duration_ms = None
        if start_time > 0:
            duration_ms = round((time.time() - start_time) * 1000, 2)
        
        # Build structured log
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'service': getattr(record, 'service', 'financial-api'),
            'message': record.getMessage(),
            'correlation_id': correlation,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add user context if available
        if user:
            log_data['user_id'] = user
        
        # Add request duration if available
        if duration_ms is not None:
            log_data['duration_ms'] = duration_ms
        
        # Add extra fields
        if hasattr(record, 'extra_data') and record.extra_data:
            log_data.update(record.extra_data)
        
        # Add exception info
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            log_data['stack_trace'] = self.formatStack(record.stack_info) if record.stack_info else None
        
        return json.dumps(log_data, default=str)

class MetricsCollector:
    """Collects and manages application metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, list] = {}
        self.lock = threading.Lock()
        self.logs_dir = Path(__file__).parent.parent.parent.parent / 'logs'
        self.logs_dir.mkdir(exist_ok=True)
        self.metrics_file = self.logs_dir / 'metrics.jsonl'
    
    def record_metric(self, event: MetricEvent):
        """Record a metric event"""
        with self.lock:
            if event.name not in self.metrics:
                self.metrics[event.name] = []
            
            self.metrics[event.name].append(event)
            
            # Write to metrics file
            try:
                with open(self.metrics_file, 'a') as f:
                    f.write(json.dumps(asdict(event), default=str) + '\n')
            except Exception as e:
                logging.error(f"Failed to write metric: {e}")
    
    def increment_counter(self, name: str, value: float = 1, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        event = MetricEvent(name=name, value=value, unit='count', tags=tags or {})
        self.record_metric(event)
    
    def record_timing(self, name: str, duration_ms: float, tags: Dict[str, str] = None):
        """Record a timing metric"""
        event = MetricEvent(name=name, value=duration_ms, unit='milliseconds', tags=tags or {})
        self.record_metric(event)
    
    def record_gauge(self, name: str, value: float, unit: str = 'value', tags: Dict[str, str] = None):
        """Record a gauge metric"""
        event = MetricEvent(name=name, value=value, unit=unit, tags=tags or {})
        self.record_metric(event)
    
    def get_metrics_summary(self, name: str = None, minutes: int = 60) -> Dict[str, Any]:
        """Get metrics summary for the last N minutes"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        summary = {}
        
        with self.lock:
            metrics_to_check = [name] if name else self.metrics.keys()
            
            for metric_name in metrics_to_check:
                if metric_name not in self.metrics:
                    continue
                
                recent_events = [
                    event for event in self.metrics[metric_name]
                    if event.timestamp >= cutoff
                ]
                
                if recent_events:
                    values = [event.value for event in recent_events]
                    summary[metric_name] = {
                        'count': len(values),
                        'sum': sum(values),
                        'avg': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'recent_events': len(recent_events)
                    }
        
        return summary

# Global metrics collector
metrics = MetricsCollector()

def setup_enhanced_logger(service_name: str = 'financial-api', level: str = 'INFO') -> logging.Logger:
    """Setup enhanced logger with correlation IDs"""
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    logs_dir = Path(__file__).parent.parent.parent.parent / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Enhanced file handler
    file_handler = logging.FileHandler(logs_dir / f'{service_name}-enhanced.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(CorrelationFormatter())
    logger.addHandler(file_handler)
    
    # Error handler
    error_handler = logging.FileHandler(logs_dir / f'{service_name}-error-enhanced.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(CorrelationFormatter())
    logger.addHandler(error_handler)
    
    return logger

def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())[:8]

def set_correlation_context(corr_id: str = None, user: str = None):
    """Set correlation context for the current request"""
    if corr_id is None:
        corr_id = generate_correlation_id()
    
    correlation_id.set(corr_id)
    request_start_time.set(time.time())
    
    if user:
        user_id.set(user)
    
    return corr_id

def clear_correlation_context():
    """Clear correlation context"""
    correlation_id.set('')
    request_start_time.set(0.0)
    user_id.set('')

def timed_operation(metric_name: str = None, tags: Dict[str, str] = None):
    """Decorator to time operations and record metrics"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                success = True
                error_type = None
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Record timing metric
                operation_tags = (tags or {}).copy()
                operation_tags.update({
                    'function': func.__name__,
                    'success': str(success)
                })
                if error_type:
                    operation_tags['error_type'] = error_type
                
                metrics.record_timing(f"{name}.duration", duration_ms, operation_tags)
                metrics.increment_counter(f"{name}.calls", 1, operation_tags)
            
            return result
        return wrapper
    return decorator

def log_with_correlation(logger: logging.Logger, level: str, message: str, **extra_data):
    """Log with correlation context"""
    record = logger.makeRecord(
        logger.name,
        getattr(logging, level.upper()),
        __file__,
        0,
        message,
        (),
        None
    )
    record.service = logger.name
    record.extra_data = extra_data
    logger.handle(record)

class SystemMetricsCollector:
    """Collect system-level metrics"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.running = False
        self.thread = None
    
    def start(self, interval_seconds: int = 60):
        """Start collecting system metrics"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._collect_loop, args=(interval_seconds,))
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Stop collecting system metrics"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def _collect_loop(self, interval_seconds: int):
        """Main collection loop"""
        while self.running:
            try:
                self._collect_system_metrics()
            except Exception as e:
                logging.error(f"Error collecting system metrics: {e}")
            
            time.sleep(interval_seconds)
    
    def _collect_system_metrics(self):
        """Collect current system metrics"""
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        self.metrics.record_gauge('system.cpu_percent', cpu_percent, 'percent')
        
        # Memory metrics
        memory = psutil.virtual_memory()
        self.metrics.record_gauge('system.memory_percent', memory.percent, 'percent')
        self.metrics.record_gauge('system.memory_used_mb', memory.used / 1024 / 1024, 'megabytes')
        self.metrics.record_gauge('system.memory_available_mb', memory.available / 1024 / 1024, 'megabytes')
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        self.metrics.record_gauge('system.disk_percent', (disk.used / disk.total) * 100, 'percent')
        self.metrics.record_gauge('system.disk_used_gb', disk.used / 1024 / 1024 / 1024, 'gigabytes')
        self.metrics.record_gauge('system.disk_free_gb', disk.free / 1024 / 1024 / 1024, 'gigabytes')

# Global instances
enhanced_logger = setup_enhanced_logger()
system_metrics = SystemMetricsCollector(metrics)

# Context managers
class CorrelationContext:
    """Context manager for correlation tracking"""
    
    def __init__(self, correlation_id: str = None, user_id: str = None):
        self.correlation_id = correlation_id
        self.user_id = user_id
        self.previous_correlation = None
        self.previous_user = None
    
    def __enter__(self):
        self.previous_correlation = correlation_id.get('')
        self.previous_user = user_id.get('')
        return set_correlation_context(self.correlation_id, self.user_id)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        correlation_id.set(self.previous_correlation)
        user_id.set(self.previous_user)
        if exc_type:
            metrics.increment_counter('errors.context_exit', 1, {
                'exception_type': exc_type.__name__,
                'correlation_id': correlation_id.get('')
            })

# Export main functionality
__all__ = [
    'metrics',
    'enhanced_logger',
    'system_metrics',
    'setup_enhanced_logger',
    'set_correlation_context',
    'clear_correlation_context',
    'generate_correlation_id',
    'timed_operation',
    'log_with_correlation',
    'CorrelationContext',
    'MetricEvent',
    'MetricsCollector'
]