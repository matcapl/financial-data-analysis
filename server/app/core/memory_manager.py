"""
Memory management utilities for large file processing
"""

import gc
import psutil
import functools
from typing import Any, Callable
from ..utils.logging_config import setup_logger

logger = setup_logger('memory-manager')


def memory_monitor(func: Callable) -> Callable:
    """Decorator to monitor memory usage of functions"""
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        # Get initial memory
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Get final memory and log if significant increase
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            if memory_increase > 50:  # Log if >50MB increase
                logger.warning(f"High memory usage in {func.__name__}", extra={
                    "function": func.__name__,
                    "initial_memory_mb": round(initial_memory, 2),
                    "final_memory_mb": round(final_memory, 2),
                    "memory_increase_mb": round(memory_increase, 2)
                })
            
            # Force garbage collection for large operations
            if memory_increase > 100:  # >100MB
                gc.collect()
                logger.info(f"Forced garbage collection after {func.__name__}")
    
    return wrapper


def check_memory_availability(required_mb: int = 100) -> bool:
    """Check if sufficient memory is available"""
    memory = psutil.virtual_memory()
    available_mb = memory.available / 1024 / 1024
    
    if available_mb < required_mb:
        logger.warning("Low memory availability", extra={
            "available_mb": round(available_mb, 2),
            "required_mb": required_mb,
            "memory_percent": memory.percent
        })
        return False
    
    return True


def cleanup_memory():
    """Force garbage collection and memory cleanup"""
    collected = gc.collect()
    logger.info(f"Memory cleanup completed, collected {collected} objects")