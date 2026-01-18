"""Azure identity for MCP Client (same auth abstraction as server)."""
import logging
import os
from typing import Optional

from azure.core.credentials import TokenCredential
from azure.identity import (
    ClientSecretCredential,
    DefaultAzureCredential,
    WorkloadIdentityCredential,
)

from src.config import get_logger, settings

logger = get_logger(__name__)


class AzureCredentialManager:
    """Unified credential manager (Workload Identity + SPN fallback)."""

    def __init__(self) -> None:
        """Initialize manager."""
        self._credential: Optional[TokenCredential] = None
        self._scopes = ["https://management.azure.com/.default"]

    def _get_credential(self) -> TokenCredential:
        """Get appropriate credential."""
        if self._credential is not None:
            return self._credential

        if self._is_workload_identity_available():
            logger.info("Using WorkloadIdentityCredential")
            self._credential = WorkloadIdentityCredential(
                tenant_id=settings.azure.tenant_id,
                client_id=settings.azure.client_id,
                token_file_path=settings.azure.federated_token_file,
            )
            return self._credential

        if self._is_service_principal_available():
            logger.info("Using ClientSecretCredential")
            self._credential = ClientSecretCredential(
                tenant_id=settings.azure.tenant_id,
                client_id=settings.azure.client_id,
                client_secret=settings.azure.client_secret,
                authority=settings.azure.authority_host,
            )
            return self._credential

        logger.info("Using DefaultAzureCredential")
        self._credential = DefaultAzureCredential(
            authority=settings.azure.authority_host
        )
        return self._credential

    def _is_workload_identity_available(self) -> bool:
        """Check if Workload Identity available."""
        token_file = settings.azure.federated_token_file
        if not os.path.exists(token_file):
            return False
        return bool(settings.azure.tenant_id and settings.azure.client_id)

    def _is_service_principal_available(self) -> bool:
        """Check if Service Principal available."""
        return bool(
            settings.azure.tenant_id
            and settings.azure.client_id
            and settings.azure.client_secret
        )

    async def get_token(self, scopes: Optional[list[str]] = None) -> str:
        """Get access token."""
        try:
            credential = self._get_credential()
            target_scopes = scopes or self._scopes
            token = credential.get_token(*target_scopes)
            return token.token
        except Exception as e:
            logger.error(f"Token acquisition failed: {e}")
            raise RuntimeError(f"Azure token acquisition failed: {e}") from e

    async def validate_authentication(self) -> bool:
        """Validate authentication works."""
        try:
            await self.get_token()
            return True
        except Exception as e:
            logger.error(f"Auth validation failed: {e}")
            return False


_credential_manager: Optional[AzureCredentialManager] = None


def get_credential_manager() -> AzureCredentialManager:
    """Get or create credential manager."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = AzureCredentialManager()
    return _credential_manager


async def get_access_token(scopes: Optional[list[str]] = None) -> str:
    """Get access token."""
    manager = get_credential_manager()
    return await manager.get_token(scopes)


async def validate_azure_auth() -> bool:
    """Validate Azure auth."""
    manager = get_credential_manager()
    return await manager.validate_authentication()
