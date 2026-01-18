"""Unit tests for MCP tools."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from src.models.schemas import (
    GetUserProfileRequest,
    UserProfile,
    ListUsersRequest,
    CreateTicketRequest,
    TicketResponse,
    QueryDataRequest,
)
from src.models.errors import ServiceError
from src.tools import (
    get_user_profile,
    list_users,
    create_ticket,
    list_tickets,
    query_data,
)


@pytest.mark.asyncio
async def test_get_user_profile_success() -> None:
    """Test successful user profile retrieval."""
    request = GetUserProfileRequest(user_id="user-123", include_details=True)
    
    mock_response = {
        "id": "user-123",
        "name": "John Doe",
        "email": "john@example.com",
        "created_at": "2024-01-01T00:00:00",
        "details": {"department": "Engineering"},
    }
    
    with patch("src.tools.user_tools.get_rest_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        
        result = await get_user_profile(request)
        
        assert result.id == "user-123"
        assert result.name == "John Doe"
        assert result.details is not None
        mock_client.get.assert_called_once_with("/users/user-123")


@pytest.mark.asyncio
async def test_list_users_success() -> None:
    """Test successful user list retrieval."""
    request = ListUsersRequest(skip=0, limit=10)
    
    mock_response = {
        "total": 100,
        "items": [
            {
                "id": "user-1",
                "name": "User One",
                "email": "user1@example.com",
                "created_at": "2024-01-01T00:00:00",
            },
            {
                "id": "user-2",
                "name": "User Two",
                "email": "user2@example.com",
                "created_at": "2024-01-02T00:00:00",
            },
        ],
    }
    
    with patch("src.tools.user_tools.get_rest_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        
        result = await list_users(request)
        
        assert result.total == 100
        assert len(result.items) == 2
        mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_create_ticket_success() -> None:
    """Test successful ticket creation."""
    request = CreateTicketRequest(
        title="Test Ticket",
        description="This is a test ticket",
        priority="high",
        assignee_id="user-123",
    )
    
    mock_response = {
        "id": "ticket-456",
        "title": "Test Ticket",
        "description": "This is a test ticket",
        "priority": "high",
        "status": "open",
        "created_at": "2024-01-18T10:00:00",
        "updated_at": "2024-01-18T10:00:00",
        "assignee_id": "user-123",
    }
    
    with patch("src.tools.ticket_tools.get_rest_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        
        result = await create_ticket(request)
        
        assert result.id == "ticket-456"
        assert result.status == "open"
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_query_data_success() -> None:
    """Test successful data query."""
    request = QueryDataRequest(
        dataset="users",
        filters={"active": True},
        limit=50,
    )
    
    mock_response = {
        "data": [
            {"id": "1", "name": "User 1"},
            {"id": "2", "name": "User 2"},
        ],
    }
    
    with patch("src.tools.data_tools.get_rest_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        
        result = await query_data(request)
        
        assert result.dataset == "users"
        assert result.rows == 2
        assert len(result.data) == 2
        mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_profile_service_error() -> None:
    """Test user profile retrieval with service error."""
    request = GetUserProfileRequest(user_id="user-123")
    
    with patch("src.tools.user_tools.get_rest_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ServiceError("Backend unavailable"))
        mock_get_client.return_value = mock_client
        
        with pytest.raises(ServiceError):
            await get_user_profile(request)
