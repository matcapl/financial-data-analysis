"""
Performance Monitoring and Profiling
"""

import time
import psutil
import asyncio
import functools
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from threading import Lock
import cProfile
import pstats
import io
from contextlib import contextmanager

from .monitoring import metrics, correlation_id

@dataclass
class PerformanceMetric:
    """Performance measurement data point"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    correlation_id: str = ''
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if not self.correlation_id:
            self.correlation_id = correlation_id.get('')

@dataclass
class DatabaseQueryMetric:
    """Database query performance metric"""
    query_hash: str
    query_type: str  # SELECT, INSERT, UPDATE, DELETE
    execution_time_ms: float
    rows_affected: int
    timestamp: datetime
    correlation_id: str = ''
    
    def __post_init__(self):
        if not self.correlation_id:
            self.correlation_id = correlation_id.get('')

class PerformanceProfiler:
    """Advanced performance profiling and monitoring"""
    
    def __init__(self):
        self.metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        self.query_metrics: List[DatabaseQueryMetric] = []
        self.slow_operations: List[Dict[str, Any]] = []
        self.lock = Lock()
        
        # Performance thresholds (in milliseconds)
        self.thresholds = {
            'slow_query': 1000,      # 1 second
            'slow_request': 5000,    # 5 seconds
            'slow_operation': 2000,  # 2 seconds
            'memory_warning': 80,    # 80% memory usage
            'cpu_warning': 80        # 80% CPU usage
        }
        
        # Ring buffers for recent metrics (last 1000 entries)
        self.recent_metrics = defaultdict(lambda: deque(maxlen=1000))
        
        # Profiling state
        self.profiling_enabled = False
        self.profiler = None
    
    def start_profiling(self):
        """Start code profiling"""
        if not self.profiling_enabled:
            self.profiler = cProfile.Profile()
            self.profiler.enable()
            self.profiling_enabled = True
    
    def stop_profiling(self) -> str:
        """Stop profiling and return results"""
        if self.profiling_enabled and self.profiler:
            self.profiler.disable()
            self.profiling_enabled = False
            
            # Get profiling results
            s = io.StringIO()
            stats = pstats.Stats(self.profiler, stream=s)
            stats.sort_stats('cumulative')
            stats.print_stats(20)  # Top 20 functions
            
            return s.getvalue()
        return "Profiling not active"
    
    @contextmanager
    def profile_block(self, block_name: str):
        """Context manager for profiling code blocks"""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss
        
        try:
            yield
        finally:
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss
            
            duration_ms = (end_time - start_time) * 1000
            memory_delta = end_memory - start_memory
            
            self.record_performance_metric(
                f"profile.{block_name}.duration",
                duration_ms,
                "milliseconds"
            )
            
            self.record_performance_metric(
                f"profile.{block_name}.memory_delta",
                memory_delta / 1024 / 1024,  # Convert to MB
                "megabytes"
            )
            
            # Check for slow operations
            if duration_ms > self.thresholds['slow_operation']:
                self._record_slow_operation(block_name, duration_ms, {
                    'memory_delta_mb': memory_delta / 1024 / 1024
                })
    
    def record_performance_metric(self, name: str, value: float, unit: str, tags: Dict[str, str] = None):
        """Record a performance metric"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )
        
        with self.lock:
            self.metrics[name].append(metric)
            self.recent_metrics[name].append(metric)
        
        # Also record in global metrics system
        metrics.record_gauge(f"performance.{name}", value, unit, tags)
    
    def record_database_query(self, query_hash: str, query_type: str, 
                            execution_time_ms: float, rows_affected: int = 0):
        """Record database query performance"""
        query_metric = DatabaseQueryMetric(
            query_hash=query_hash,
            query_type=query_type,
            execution_time_ms=execution_time_ms,
            rows_affected=rows_affected,
            timestamp=datetime.utcnow()
        )
        
        with self.lock:
            self.query_metrics.append(query_metric)
        
        # Record in metrics system
        metrics.record_timing(f"database.query.{query_type.lower()}", execution_time_ms, {
            'query_type': query_type
        })
        
        # Check for slow queries
        if execution_time_ms > self.thresholds['slow_query']:
            self._record_slow_operation(f"slow_query_{query_type}", execution_time_ms, {
                'query_hash': query_hash,
                'rows_affected': rows_affected
            })
    
    def _record_slow_operation(self, operation: str, duration_ms: float, context: Dict[str, Any]):
        """Record a slow operation for investigation"""
        slow_op = {
            'operation': operation,
            'duration_ms': duration_ms,
            'timestamp': datetime.utcnow().isoformat(),
            'correlation_id': correlation_id.get(''),
            'context': context
        }
        
        with self.lock:
            self.slow_operations.append(slow_op)
            
            # Keep only recent slow operations (last 100)
            if len(self.slow_operations) > 100:
                self.slow_operations = self.slow_operations[-100:]
        
        # Record metric
        metrics.increment_counter('performance.slow_operations', 1, {
            'operation': operation
        })
    
    def get_performance_summary(self, minutes: int = 60) -> Dict[str, Any]:
        """Get performance summary for the last N minutes"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        with self.lock:
            # Filter recent metrics
            recent_perf_metrics = {}
            for name, metric_list in self.metrics.items():
                recent = [m for m in metric_list if m.timestamp >= cutoff]
                if recent:
                    values = [m.value for m in recent]
                    recent_perf_metrics[name] = {
                        'count': len(values),
                        'avg': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'latest': values[-1]
                    }
            
            # Filter recent query metrics
            recent_queries = [q for q in self.query_metrics if q.timestamp >= cutoff]
            query_summary = {}
            if recent_queries:
                by_type = defaultdict(list)
                for q in recent_queries:
                    by_type[q.query_type].append(q.execution_time_ms)
                
                for query_type, times in by_type.items():
                    query_summary[query_type] = {
                        'count': len(times),
                        'avg_time_ms': sum(times) / len(times),
                        'min_time_ms': min(times),
                        'max_time_ms': max(times)
                    }
            
            # Recent slow operations
            recent_slow_ops = [
                op for op in self.slow_operations
                if datetime.fromisoformat(op['timestamp']) >= cutoff
            ]
            
            return {
                'time_range_minutes': minutes,
                'performance_metrics': recent_perf_metrics,
                'database_queries': query_summary,
                'slow_operations': recent_slow_ops,
                'generated_at': datetime.utcnow().isoformat()
            }
    
    def get_top_slow_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the slowest operations recorded"""
        with self.lock:
            sorted_ops = sorted(
                self.slow_operations,
                key=lambda x: x['duration_ms'],
                reverse=True
            )
            return sorted_ops[:limit]
    
    def monitor_system_resources(self) -> Dict[str, float]:
        """Monitor current system resource usage"""
        process = psutil.Process()
        
        # CPU and memory
        cpu_percent = process.cpu_percent()
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        
        # System-wide metrics
        system_cpu = psutil.cpu_percent(interval=0.1)
        system_memory = psutil.virtual_memory()
        
        resource_metrics = {
            'process_cpu_percent': cpu_percent,
            'process_memory_mb': memory_info.rss / 1024 / 1024,
            'process_memory_percent': memory_percent,
            'system_cpu_percent': system_cpu,
            'system_memory_percent': system_memory.percent,
            'system_memory_available_mb': system_memory.available / 1024 / 1024
        }
        
        # Record metrics
        for name, value in resource_metrics.items():
            self.record_performance_metric(f"system.{name}", value, "percent" if "percent" in name else "value")
        
        # Check thresholds
        if memory_percent > self.thresholds['memory_warning']:
            metrics.increment_counter('performance.warnings.high_memory', 1)
        
        if cpu_percent > self.thresholds['cpu_warning']:
            metrics.increment_counter('performance.warnings.high_cpu', 1)
        
        return resource_metrics

# Global performance profiler
profiler = PerformanceProfiler()

def performance_monitor(operation_name: str = None, threshold_ms: float = None):
    """Decorator for monitoring function performance"""
    def decorator(func: Callable) -> Callable:
        name = operation_name or f"{func.__module__}.{func.__name__}"
        threshold = threshold_ms or profiler.thresholds['slow_operation']
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss
                
                try:
                    result = await func(*args, **kwargs)
                    success = True
                except Exception as e:
                    success = False
                    raise
                finally:
                    end_time = time.time()
                    end_memory = psutil.Process().memory_info().rss
                    
                    duration_ms = (end_time - start_time) * 1000
                    memory_delta = end_memory - start_memory
                    
                    # Record performance metrics
                    profiler.record_performance_metric(
                        f"{name}.duration",
                        duration_ms,
                        "milliseconds",
                        {'success': str(success)}
                    )
                    
                    profiler.record_performance_metric(
                        f"{name}.memory_delta",
                        memory_delta / 1024 / 1024,
                        "megabytes",
                        {'success': str(success)}
                    )
                    
                    # Check threshold
                    if duration_ms > threshold:
                        profiler._record_slow_operation(name, duration_ms, {
                            'function_type': 'async',
                            'memory_delta_mb': memory_delta / 1024 / 1024,
                            'success': success
                        })
                
                return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss
                
                try:
                    result = func(*args, **kwargs)
                    success = True
                except Exception as e:
                    success = False
                    raise
                finally:
                    end_time = time.time()
                    end_memory = psutil.Process().memory_info().rss
                    
                    duration_ms = (end_time - start_time) * 1000
                    memory_delta = end_memory - start_memory
                    
                    # Record performance metrics
                    profiler.record_performance_metric(
                        f"{name}.duration",
                        duration_ms,
                        "milliseconds",
                        {'success': str(success)}
                    )
                    
                    profiler.record_performance_metric(
                        f"{name}.memory_delta",
                        memory_delta / 1024 / 1024,
                        "megabytes",
                        {'success': str(success)}
                    )
                    
                    # Check threshold
                    if duration_ms > threshold:
                        profiler._record_slow_operation(name, duration_ms, {
                            'function_type': 'sync',
                            'memory_delta_mb': memory_delta / 1024 / 1024,
                            'success': success
                        })
                
                return result
            return sync_wrapper
    return decorator

# Database query monitoring decorator
def monitor_database_query(query_type: str = None):
    """Decorator for monitoring database queries"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import hashlib
            
            # Generate query hash (simplified)
            func_signature = f"{func.__module__}.{func.__name__}"
            query_hash = hashlib.md5(func_signature.encode()).hexdigest()[:8]
            
            start_time = time.time()
            rows_affected = 0
            
            try:
                result = func(*args, **kwargs)
                
                # Try to extract rows affected from result if possible
                if hasattr(result, 'rowcount'):
                    rows_affected = result.rowcount
                elif isinstance(result, (list, tuple)):
                    rows_affected = len(result)
                
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                q_type = query_type or 'UNKNOWN'
                
                profiler.record_database_query(
                    query_hash,
                    q_type,
                    duration_ms,
                    rows_affected
                )
        
        return wrapper
    return decorator

# Export main functionality
__all__ = [
    'profiler',
    'performance_monitor',
    'monitor_database_query',
    'PerformanceProfiler',
    'PerformanceMetric',
    'DatabaseQueryMetric'
]