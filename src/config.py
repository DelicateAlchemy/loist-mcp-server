"""
Configuration management for Music Library MCP Server
Centralized configuration using environment variables with sensible defaults
"""
import os
import logging
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    """Server configuration with environment variable support"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Server Identity
    server_name: str = "Music Library MCP"
    server_version: str = "0.1.0"
    server_instructions: str = (
        "MCP server for audio ingestion and embedding. "
        "Use health_check to verify server status. "
        "Future capabilities will include audio file processing and embedding generation."
    )
    
    # Server Runtime
    server_host: str = "0.0.0.0"
    server_port: int = 8080
    server_transport: Literal["stdio", "http", "sse"] = "stdio"
    
    # Authentication
    bearer_token: str | None = None
    auth_enabled: bool = False
    
    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"
    
    # MCP Protocol
    mcp_protocol_version: str = "2024-11-05"
    include_fastmcp_meta: bool = True
    
    # Duplicate Handling Policies
    on_duplicate_tools: Literal["error", "warn", "replace", "ignore"] = "error"
    on_duplicate_resources: Literal["error", "warn", "replace", "ignore"] = "warn"
    on_duplicate_prompts: Literal["error", "warn", "replace", "ignore"] = "replace"
    
    # Performance
    max_workers: int = 4
    request_timeout: int = 30
    
    # Storage (for future implementation)
    storage_path: str = "./storage"
    max_file_size: int = 104857600  # 100MB
    
    # CORS Configuration
    enable_cors: bool = True
    cors_origins: str = "*"  # Comma-separated origins in production
    cors_allow_credentials: bool = True
    cors_allow_methods: str = "GET,POST,OPTIONS"
    cors_allow_headers: str = "Authorization,Content-Type,Range,X-Requested-With,Accept,Origin"
    cors_expose_headers: str = "Content-Range,Accept-Ranges,Content-Length,Content-Type"
    
    # Feature Flags
    enable_metrics: bool = False
    enable_healthcheck: bool = True
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into list"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    @property
    def cors_allow_methods_list(self) -> list[str]:
        """Parse CORS methods string into list"""
        return [method.strip() for method in self.cors_allow_methods.split(",") if method.strip()]
    
    @property
    def cors_allow_headers_list(self) -> list[str]:
        """Parse CORS headers string into list"""
        return [header.strip() for header in self.cors_allow_headers.split(",") if header.strip()]
    
    @property
    def cors_expose_headers_list(self) -> list[str]:
        """Parse CORS expose headers string into list"""
        return [header.strip() for header in self.cors_expose_headers.split(",") if header.strip()]
    
    @property
    def log_level_int(self) -> int:
        """Convert log level string to logging constant"""
        return getattr(logging, self.log_level.upper(), logging.INFO)
    
    def configure_logging(self) -> None:
        """Configure application logging based on settings"""
        if self.log_format == "json":
            # JSON format for structured logging
            log_format = '{"timestamp":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","message":"%(message)s","module":"%(module)s","function":"%(funcName)s","line":%(lineno)d}'
        else:
            # Text format for human-readable logs
            log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
        
        logging.basicConfig(
            level=self.log_level_int,
            format=log_format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Set specific log levels for noisy libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


# Global configuration instance
config = ServerConfig()

