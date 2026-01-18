"""Ticket-related MCP tools."""
import logging
from datetime import datetime

from src.clients import get_rest_client
from src.models.schemas import (
    CreateTicketRequest,
    ListTicketsRequest,
    ListTicketsResponse,
    TicketResponse,
)

logger = logging.getLogger(__name__)


async def create_ticket(request: CreateTicketRequest) -> TicketResponse:
    """
    Create a support ticket in the backend service.
    
    Args:
        request: CreateTicketRequest with ticket details.
        
    Returns:
        TicketResponse with created ticket information.
        
    Raises:
        ServiceError: If backend call fails.
    """
    client = get_rest_client()

    # Prepare request payload
    payload = {
        "title": request.title,
        "description": request.description,
        "priority": request.priority,
    }
    if request.assignee_id:
        payload["assignee_id"] = request.assignee_id

    # Call backend API
    response_data = await client.post("/tickets", data=payload)

    # Map response to TicketResponse
    ticket = TicketResponse(
        id=response_data["id"],
        title=response_data["title"],
        description=response_data["description"],
        priority=response_data["priority"],
        status=response_data["status"],
        created_at=datetime.fromisoformat(response_data["created_at"]),
        updated_at=datetime.fromisoformat(response_data["updated_at"]),
        assignee_id=response_data.get("assignee_id"),
    )

    logger.info(f"Created ticket: {ticket.id}")
    return ticket


async def list_tickets(request: ListTicketsRequest) -> ListTicketsResponse:
    """
    List support tickets from backend service.
    
    Args:
        request: ListTicketsRequest with filter and pagination parameters.
        
    Returns:
        ListTicketsResponse with paginated ticket list.
        
    Raises:
        ServiceError: If backend call fails.
    """
    client = get_rest_client()

    # Build query parameters
    params = {"skip": request.skip, "limit": request.limit}
    if request.status:
        params["status"] = request.status

    # Call backend API
    response_data = await client.get("/tickets", params=params)

    # Map responses to TicketResponse list
    tickets = [
        TicketResponse(
            id=ticket["id"],
            title=ticket["title"],
            description=ticket["description"],
            priority=ticket["priority"],
            status=ticket["status"],
            created_at=datetime.fromisoformat(ticket["created_at"]),
            updated_at=datetime.fromisoformat(ticket["updated_at"]),
            assignee_id=ticket.get("assignee_id"),
        )
        for ticket in response_data["items"]
    ]

    result = ListTicketsResponse(
        total=response_data["total"],
        items=tickets,
    )

    logger.info(f"Retrieved {len(tickets)} tickets (total: {result.total})")
    return result
