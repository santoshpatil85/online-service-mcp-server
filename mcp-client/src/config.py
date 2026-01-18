"""MCP Client configuration management."""
import logging
from typing import Optional

from pydantic_settings import BaseSettings


class AzureSettings(BaseSettings):
    """Azure authentication settings."""

    tenant_id: str = ""
    client_id: str = ""
    authority_host: str = "https://login.microsoftonline.com"
    federated_token_file: str = "/var/run/secrets/azure/tokens/token"
    client_secret: Optional[str] = None

    class Config:
        env_prefix = "AZURE_"
        case_sensitive = False


class ClientSettings(BaseSettings):
    """MCP Client settings."""

    mcp_server_url: str = "http://mcp-server:8000"
    log_level: str = "INFO"
    request_timeout: int = 30
    discovery_timeout: int = 10

    class Config:
        env_prefix = ""
        case_sensitive = False


class Settings(BaseSettings):
    """Root settings."""

    azure: AzureSettings = AzureSettings()
    client: ClientSettings = ClientSettings()

    class Config:
        case_sensitive = False


settings = Settings()


def get_logger(name: str) -> logging.Logger:
    """Get configured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(settings.client.log_level)
    return logger
