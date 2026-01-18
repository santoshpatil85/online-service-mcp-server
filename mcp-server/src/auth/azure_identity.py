"""Azure identity management with Workload Identity (AWI) and Service Principal (SPN) fallback."""
import logging
import os
from typing import Optional

import httpx
from azure.core.credentials import TokenCredential
from azure.identity import (
    ClientSecretCredential,
    DefaultAzureCredential,
    WorkloadIdentityCredential,
)

from src.config import get_logger, settings

logger = get_logger(__name__)


class AzureCredentialManager:
    """
    Unified Azure credential manager supporting multiple authentication methods.
    
    Priority:
    1. WorkloadIdentityCredential (AKS with Workload Identity)
    2. ClientSecretCredential (Service Principal for local dev / CI)
    3. DefaultAzureCredential (fallback - Azure CLI, managed identity, etc.)
    """

    def __init__(self) -> None:
        """Initialize the credential manager."""
        self._credential: Optional[TokenCredential] = None
        self._token_cache: Optional[str] = None
        self._scopes = settings.server.azure_scopes

    def _get_credential(self) -> TokenCredential:
        """Get the appropriate Azure credential based on environment."""
        if self._credential is not None:
            return self._credential

        # Priority 1: Workload Identity (for AKS)
        if self._is_workload_identity_available():
            logger.info("Using WorkloadIdentityCredential for Azure auth")
            self._credential = WorkloadIdentityCredential(
                tenant_id=settings.azure.tenant_id,
                client_id=settings.azure.client_id,
                token_file_path=settings.azure.federated_token_file,
            )
            return self._credential

        # Priority 2: Service Principal (for local dev / CI)
        if self._is_service_principal_available():
            logger.info("Using ClientSecretCredential (Service Principal) for Azure auth")
            self._credential = ClientSecretCredential(
                tenant_id=settings.azure.tenant_id,
                client_id=settings.azure.client_id,
                client_secret=settings.azure.client_secret,
                authority=settings.azure.authority_host,
            )
            return self._credential

        # Priority 3: Default credential (fallback)
        logger.info("Using DefaultAzureCredential for Azure auth")
        self._credential = DefaultAzureCredential(
            authority=settings.azure.authority_host
        )
        return self._credential

    def _is_workload_identity_available(self) -> bool:
        """Check if Workload Identity is available."""
        # Check if federated token file exists (injected by AKS Workload Identity webhook)
        token_file = settings.azure.federated_token_file
        if not os.path.exists(token_file):
            logger.debug(f"Federated token file not found: {token_file}")
            return False

        if not settings.azure.tenant_id or not settings.azure.client_id:
            logger.debug("AZURE_TENANT_ID or AZURE_CLIENT_ID not set")
            return False

        logger.debug("Workload Identity is available")
        return True

    def _is_service_principal_available(self) -> bool:
        """Check if Service Principal credentials are available."""
        if (
            not settings.azure.tenant_id
            or not settings.azure.client_id
            or not settings.azure.client_secret
        ):
            logger.debug("Service Principal credentials incomplete")
            return False

        logger.debug("Service Principal credentials are available")
        return True

    async def get_token(self, scopes: Optional[list[str]] = None) -> str:
        """
        Get an Azure AD access token.
        
        Args:
            scopes: Optional list of scopes. Defaults to configured scopes.
            
        Returns:
            Access token string.
            
        Raises:
            RuntimeError: If token acquisition fails.
        """
        try:
            credential = self._get_credential()
            target_scopes = scopes or self._scopes

            if not target_scopes:
                raise ValueError("No scopes provided for token acquisition")

            logger.debug(f"Acquiring token for scopes: {target_scopes}")
            
            # azure-identity handles token caching internally
            token = credential.get_token(*target_scopes)
            logger.debug("Token acquired successfully")
            return token.token

        except Exception as e:
            logger.error(f"Failed to acquire Azure AD token: {e}")
            raise RuntimeError(f"Azure token acquisition failed: {e}") from e

    async def validate_authentication(self) -> bool:
        """
        Validate that authentication can be performed.
        
        Returns:
            True if authentication is valid, False otherwise.
        """
        try:
            await self.get_token()
            return True
        except Exception as e:
            logger.error(f"Authentication validation failed: {e}")
            return False


# Global credential manager instance
_credential_manager: Optional[AzureCredentialManager] = None


def get_credential_manager() -> AzureCredentialManager:
    """Get or create the global credential manager."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = AzureCredentialManager()
    return _credential_manager


async def get_access_token(scopes: Optional[list[str]] = None) -> str:
    """
    Helper function to get an access token.
    
    Args:
        scopes: Optional list of scopes.
        
    Returns:
        Access token string.
    """
    manager = get_credential_manager()
    return await manager.get_token(scopes)


async def validate_azure_auth() -> bool:
    """
    Validate Azure authentication is working.
    
    Returns:
        True if authentication is valid.
    """
    manager = get_credential_manager()
    return await manager.validate_authentication()
