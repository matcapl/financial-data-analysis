"""
Application Configuration
Centralized configuration management with environment validation
"""

import os
from typing import List, Optional
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings
from pathlib import Path


class DatabaseSettings(BaseSettings):
    """Database configuration settings"""
    url: str = "postgresql://localhost:5432/financial_data"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False
    
    model_config = {"env_prefix": "DATABASE_"}


class FileUploadSettings(BaseSettings):
    """File upload configuration"""
    max_size_mb: int = 10
    allowed_extensions: List[str] = [".csv", ".xlsx", ".pdf"]
    upload_directory: str = "uploads"
    data_directory: str = "data"
    reports_directory: str = "reports"
    
    @field_validator("max_size_mb")
    def validate_max_size(cls, v):
        if v <= 0:
            raise ValueError("max_size_mb must be positive")
        return v
    
    @property
    def max_size_bytes(self) -> int:
        return self.max_size_mb * 1024 * 1024


class SecuritySettings(BaseSettings):
    """Security configuration"""
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]


class AppSettings(BaseSettings):
    """Main application settings"""
    title: str = "Financial Data Analysis API"
    description: str = "Unified FastAPI backend for financial data processing and analysis"
    version: str = "2.0.0"
    debug: bool = False
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 4000
    
    # Subsystem configurations
    database: DatabaseSettings = DatabaseSettings()
    files: FileUploadSettings = FileUploadSettings()
    security: SecuritySettings = SecuritySettings()
    
    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}
    
    @field_validator("environment")
    def validate_environment(cls, v):
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v
    
    @property
    def project_root(self) -> Path:
        """Get the project root directory"""
        return Path(__file__).resolve().parent.parent.parent.parent
    
    @property
    def config_dir(self) -> Path:
        """Get the config directory path"""
        return self.project_root / "config"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Global settings instance
settings = AppSettings()