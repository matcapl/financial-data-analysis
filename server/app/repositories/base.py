"""
Base repository interface
Abstract base class for all repository implementations
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, TypeVar, Generic

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository for CRUD operations"""
    
    @abstractmethod
    def create(self, entity: T) -> T:
        """Create a new entity"""
        pass
    
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[T]:
        """Get entity by ID"""
        pass
    
    @abstractmethod
    def get_all(self) -> List[T]:
        """Get all entities"""
        pass
    
    @abstractmethod
    def update(self, id: int, entity: T) -> Optional[T]:
        """Update entity by ID"""
        pass
    
    @abstractmethod
    def delete(self, id: int) -> bool:
        """Delete entity by ID"""
        pass
    
    @abstractmethod
    def exists(self, id: int) -> bool:
        """Check if entity exists"""
        pass