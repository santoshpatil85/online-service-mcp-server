"""MCP Server configuration management."""
import logging
from typing import Optional

from pydantic_settings import BaseSettings


class AzureSettings(BaseSettings):
    """Azure authentication and service settings."""

    tenant_id: str = ""
    client_id: str = ""
    authority_host: str = "https://login.microsoftonline.com"
    federated_token_file: str = "/var/run/secrets/azure/tokens/token"
    client_secret: Optional[str] = None  # Only for local dev / CI fallback

    class Config:
        env_prefix = "AZURE_"
        case_sensitive = False


class ServerSettings(BaseSettings):
    """FastMCP Server settings."""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"
    
    # Downstream service configuration
    backend_api_url: str = "https://api.example.com"
    backend_api_timeout: int = 10
    
    # OAuth scopes for downstream services
    azure_scopes: list[str] = ["https://management.azure.com/.default"]
    
    # Health check configuration
    readiness_check_backend: bool = True

    class Config:
        env_prefix = ""
        case_sensitive = False


class Settings(BaseSettings):
    """Root settings combining all subsettings."""

    azure: AzureSettings = AzureSettings()
    server: ServerSettings = ServerSettings()

    class Config:
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(settings.server.log_level)
    return logger
