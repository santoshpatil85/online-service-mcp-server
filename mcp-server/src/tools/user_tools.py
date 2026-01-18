"""User-related MCP tools."""
import logging
from datetime import datetime

from src.clients import get_rest_client
from src.models.schemas import (
    GetUserProfileRequest,
    ListUsersRequest,
    ListUsersResponse,
    UserProfile,
)

logger = logging.getLogger(__name__)


async def get_user_profile(request: GetUserProfileRequest) -> UserProfile:
    """
    Retrieve user profile from backend service.
    
    Uses Azure Workload Identity to authenticate the downstream REST call.
    
    Args:
        request: GetUserProfileRequest with user_id and optional include_details.
        
    Returns:
        UserProfile with user information.
        
    Raises:
        ServiceError: If backend call fails.
    """
    logger.info_with_context = logger.info  # Fallback for structured logging
    client = get_rest_client()

    # Call backend API
    response_data = await client.get(f"/users/{request.user_id}")

    # Map response to UserProfile
    profile = UserProfile(
        id=response_data["id"],
        name=response_data["name"],
        email=response_data["email"],
        created_at=datetime.fromisoformat(response_data["created_at"]),
        details=response_data.get("details") if request.include_details else None,
    )

    logger.info(f"Retrieved user profile: {profile.id}")
    return profile


async def list_users(request: ListUsersRequest) -> ListUsersResponse:
    """
    List users from backend service.
    
    Args:
        request: ListUsersRequest with pagination parameters.
        
    Returns:
        ListUsersResponse with paginated user list.
        
    Raises:
        ServiceError: If backend call fails.
    """
    client = get_rest_client()

    # Call backend API with pagination
    response_data = await client.get(
        "/users",
        params={"skip": request.skip, "limit": request.limit},
    )

    # Map responses to UserProfile list
    users = [
        UserProfile(
            id=user["id"],
            name=user["name"],
            email=user["email"],
            created_at=datetime.fromisoformat(user["created_at"]),
        )
        for user in response_data["items"]
    ]

    result = ListUsersResponse(
        total=response_data["total"],
        items=users,
    )

    logger.info(f"Retrieved {len(users)} users (total: {result.total})")
    return result
