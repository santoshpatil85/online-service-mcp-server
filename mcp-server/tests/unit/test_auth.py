"""Unit tests for authentication module."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from azure.core.exceptions import ClientAuthenticationError

from src.auth.azure_identity import (
    AzureCredentialManager,
    get_credential_manager,
    get_access_token,
    validate_azure_auth,
)


@pytest.mark.asyncio
async def test_get_access_token_with_workload_identity() -> None:
    """Test token acquisition with Workload Identity."""
    manager = AzureCredentialManager()
    
    with patch.object(manager, "_is_workload_identity_available", return_value=True):
        with patch.object(manager, "_get_credential") as mock_get_cred:
            mock_cred = MagicMock()
            mock_cred.get_token.return_value = MagicMock(token="test-token")
            mock_get_cred.return_value = mock_cred
            
            token = await manager.get_token()
            assert token == "test-token"


@pytest.mark.asyncio
async def test_get_access_token_with_service_principal() -> None:
    """Test token acquisition with Service Principal."""
    manager = AzureCredentialManager()
    
    with patch.object(manager, "_is_workload_identity_available", return_value=False):
        with patch.object(manager, "_is_service_principal_available", return_value=True):
            with patch.object(manager, "_get_credential") as mock_get_cred:
                mock_cred = MagicMock()
                mock_cred.get_token.return_value = MagicMock(token="sp-token")
                mock_get_cred.return_value = mock_cred
                
                token = await manager.get_token()
                assert token == "sp-token"


@pytest.mark.asyncio
async def test_validate_authentication_success() -> None:
    """Test successful authentication validation."""
    manager = AzureCredentialManager()
    
    with patch.object(manager, "get_token", return_value="test-token"):
        result = await manager.validate_authentication()
        assert result is True


@pytest.mark.asyncio
async def test_validate_authentication_failure() -> None:
    """Test failed authentication validation."""
    manager = AzureCredentialManager()
    
    with patch.object(manager, "get_token", side_effect=RuntimeError("Auth failed")):
        result = await manager.validate_authentication()
        assert result is False


def test_get_credential_manager_singleton() -> None:
    """Test credential manager is a singleton."""
    manager1 = get_credential_manager()
    manager2 = get_credential_manager()
    assert manager1 is manager2


@pytest.mark.asyncio
async def test_get_access_token_helper() -> None:
    """Test get_access_token helper function."""
    with patch("src.auth.azure_identity.get_credential_manager") as mock_get_mgr:
        mock_mgr = MagicMock()
        mock_mgr.get_token = AsyncMock(return_value="helper-token")
        mock_get_mgr.return_value = mock_mgr
        
        token = await get_access_token()
        assert token == "helper-token"


@pytest.mark.asyncio
async def test_validate_azure_auth_helper() -> None:
    """Test validate_azure_auth helper function."""
    with patch("src.auth.azure_identity.get_credential_manager") as mock_get_mgr:
        mock_mgr = MagicMock()
        mock_mgr.validate_authentication = AsyncMock(return_value=True)
        mock_get_mgr.return_value = mock_mgr
        
        result = await validate_azure_auth()
        assert result is True
