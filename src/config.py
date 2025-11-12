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
        # Read .env file if it exists (local dev), gracefully ignore if missing (production)
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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
    # Cloud Run sets PORT automatically, fallback to 8080 for local development
    server_port: int = int(os.getenv("PORT", "8080"))
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
    
    # Google Cloud Storage Configuration
    gcs_bucket_name: str | None = None
    gcs_project_id: str | None = None
    gcs_region: str = "us-central1"
    gcs_signed_url_expiration: int = 900  # 15 minutes in seconds
    gcs_service_account_email: str | None = None
    google_application_credentials: str | None = None  # Path to service account key
    gcs_signer_mode: str = "auto"  # auto, iam, keyfile - signing method for GCS URLs
    
    # Database Configuration
    db_host: str | None = None
    db_port: int = 5432
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None
    db_connection_name: str | None = None  # For Cloud SQL Proxy
    db_min_connections: int = 2
    db_max_connections: int = 10
    db_command_timeout: int = 30
    
    # CORS Configuration
    enable_cors: bool = True
    cors_origins: str = "*"  # Comma-separated origins in production
    cors_allow_credentials: bool = True
    cors_allow_methods: str = "GET,POST,OPTIONS"
    cors_allow_headers: str = "Authorization,Content-Type,Range,X-Requested-With,Accept,Origin"
    cors_expose_headers: str = "Content-Range,Accept-Ranges,Content-Length,Content-Type"
    
    # Embed Configuration
    embed_base_url: str = "https://loist.io"  # Base URL for embed links (configurable for local dev)

    # Task Queue Configuration
    task_queue_mode: str = "cloud"  # "cloud" or "local" for development
    allowed_task_queues: str = "audio-processing-queue"  # Comma-separated list of allowed queue names
    cloud_tasks_strict_auth: bool = True  # Require service account validation in production

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
    def allowed_task_queues_list(self) -> list[str]:
        """Parse allowed task queues string into list"""
        return [queue.strip() for queue in self.allowed_task_queues.split(",") if queue.strip()]
    
    @property
    def log_level_int(self) -> int:
        """Convert log level string to logging constant"""
        return getattr(logging, self.log_level.upper(), logging.INFO)
    
    @property
    def gcs_credentials_path(self) -> str | None:
        """
        Get GCS credentials path from config or environment.
        Checks GOOGLE_APPLICATION_CREDENTIALS env var as fallback.
        """
        if self.google_application_credentials:
            return self.google_application_credentials
        return os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    @property
    def is_gcs_configured(self) -> bool:
        """Check if GCS is properly configured"""
        return bool(
            self.gcs_bucket_name and 
            self.gcs_project_id and
            (self.gcs_credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        )
    
    @property
    def is_database_configured(self) -> bool:
        """Check if database is properly configured"""
        # Can use either direct connection or Cloud SQL Proxy
        has_direct = bool(self.db_host and self.db_name and self.db_user and self.db_password)
        has_proxy = bool(self.db_connection_name and self.db_connection_name.strip() and self.db_name and self.db_user and self.db_password)
        return has_direct or has_proxy
    
    @property
    def database_url(self) -> str | None:
        """
        Generate PostgreSQL connection URL.
        Returns None if database is not configured.
        """
        # Check for explicit DATABASE_URL first (for Cloud Run with secrets)
        explicit_url = os.getenv("DATABASE_URL")
        if explicit_url:
            return explicit_url

        if not self.is_database_configured:
            return None

        if self.db_connection_name and self.db_connection_name.strip():
            # Cloud SQL Proxy connection
            # Format: postgresql://user:password@/dbname?host=/cloudsql/connection_name
            return f"postgresql://{self.db_user}:{self.db_password}@/{self.db_name}?host=/cloudsql/{self.db_connection_name}"
        else:
            # Direct connection
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def validate_credentials(self) -> dict[str, bool]:
        """
        Validate that all required credentials are available.
        Returns a dict showing which services are properly configured.
        """
        return {
            "gcs": self.is_gcs_configured,
            "database": self.is_database_configured,
            "auth": bool(self.bearer_token) if self.auth_enabled else True,
        }
    
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

# Debug logging for environment variable loading (temporary for troubleshooting)
import sys
if config.log_level.upper() == "DEBUG":
    print(f"[CONFIG DEBUG] embed_base_url = {config.embed_base_url}", file=sys.stderr)
    print(f"[CONFIG DEBUG] EMBED_BASE_URL env var = {os.getenv('EMBED_BASE_URL', 'NOT SET')}", file=sys.stderr)
    print(f"[CONFIG DEBUG] .env file exists = {os.path.exists('.env')}", file=sys.stderr)

