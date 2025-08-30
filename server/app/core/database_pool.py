"""
Database connection pooling for improved performance
"""

import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from typing import Generator
import os
from ..utils.logging_config import setup_logger

logger = setup_logger('database-pool')


class DatabasePool:
    """PostgreSQL connection pool manager"""
    
    def __init__(self):
        self._pool = None
        self._setup_pool()
    
    def _setup_pool(self):
        """Initialize connection pool"""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL environment variable not set")
            
            # Create connection pool (5 min, 20 max connections)
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=5,
                maxconn=20,
                dsn=database_url,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            
            logger.info("Database connection pool initialized", extra={
                "min_connections": 5,
                "max_connections": 20
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Get connection from pool with automatic cleanup"""
        connection = None
        try:
            connection = self._pool.getconn()
            if connection:
                connection.autocommit = True
                yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if connection:
                self._pool.putconn(connection)
    
    def close_all_connections(self):
        """Close all connections in the pool"""
        if self._pool:
            self._pool.closeall()
            logger.info("All database connections closed")


# Global connection pool instance
db_pool = DatabasePool()