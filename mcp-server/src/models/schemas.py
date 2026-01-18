"""Data models and schemas for MCP Server."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# User Tools
# ============================================================================


class GetUserProfileRequest(BaseModel):
    """Request to retrieve user profile."""

    user_id: str = Field(..., description="Unique user identifier")
    include_details: bool = Field(
        default=False, description="Include detailed profile information"
    )


class UserProfile(BaseModel):
    """User profile response."""

    id: str = Field(..., description="User unique identifier")
    name: str = Field(..., description="User full name")
    email: str = Field(..., description="User email address")
    created_at: datetime = Field(..., description="Account creation timestamp")
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Additional profile details"
    )


class ListUsersRequest(BaseModel):
    """Request to list users."""

    skip: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=10, ge=1, le=100, description="Number of records to return")


class ListUsersResponse(BaseModel):
    """Response for list users."""

    total: int = Field(..., description="Total number of users")
    items: list[UserProfile] = Field(..., description="List of user profiles")


# ============================================================================
# Ticket Tools
# ============================================================================


class CreateTicketRequest(BaseModel):
    """Request to create a support ticket."""

    title: str = Field(..., min_length=1, max_length=200, description="Ticket title")
    description: str = Field(
        ..., min_length=10, max_length=5000, description="Ticket description"
    )
    priority: str = Field(
        default="medium",
        description="Ticket priority (low, medium, high, critical)",
        pattern="^(low|medium|high|critical)$",
    )
    assignee_id: Optional[str] = Field(default=None, description="Assignee user ID")


class TicketResponse(BaseModel):
    """Ticket response."""

    id: str = Field(..., description="Ticket unique identifier")
    title: str = Field(..., description="Ticket title")
    description: str = Field(..., description="Ticket description")
    priority: str = Field(..., description="Ticket priority")
    status: str = Field(..., description="Ticket status (open, in_progress, closed)")
    created_at: datetime = Field(..., description="Ticket creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    assignee_id: Optional[str] = Field(default=None, description="Assignee user ID")


class ListTicketsRequest(BaseModel):
    """Request to list tickets."""

    status: Optional[str] = Field(
        default=None,
        description="Filter by status (open, in_progress, closed)",
    )
    skip: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=10, ge=1, le=100, description="Number of records to return")


class ListTicketsResponse(BaseModel):
    """Response for list tickets."""

    total: int = Field(..., description="Total number of tickets")
    items: list[TicketResponse] = Field(..., description="List of tickets")


# ============================================================================
# Data Query Tools
# ============================================================================


class QueryDataRequest(BaseModel):
    """Request to query data."""

    dataset: str = Field(..., description="Dataset name to query")
    filters: Optional[dict[str, Any]] = Field(
        default=None, description="Query filters"
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Result limit")


class QueryDataResponse(BaseModel):
    """Response for data query."""

    dataset: str = Field(..., description="Dataset name")
    rows: int = Field(..., description="Number of rows returned")
    data: list[dict[str, Any]] = Field(..., description="Query results")


# ============================================================================
# Health Check
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status (alive, ready)")
    timestamp: datetime = Field(..., description="Health check timestamp")
    service_version: str = Field(..., description="Service version")
    dependencies: dict[str, str] = Field(
        default_factory=dict, description="Dependency health status"
    )
