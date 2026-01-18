"""Data query MCP tools."""
import logging
from typing import Any

from src.clients import get_rest_client
from src.models.schemas import QueryDataRequest, QueryDataResponse

logger = logging.getLogger(__name__)


async def query_data(request: QueryDataRequest) -> QueryDataResponse:
    """
    Query data from backend service.
    
    Supports filtered queries on multiple datasets with result limiting.
    
    Args:
        request: QueryDataRequest with dataset name, filters, and limit.
        
    Returns:
        QueryDataResponse with query results.
        
    Raises:
        ServiceError: If backend call fails.
    """
    client = get_rest_client()

    # Prepare query parameters
    params: dict[str, Any] = {"limit": request.limit}
    if request.filters:
        params["filters"] = request.filters

    # Call backend API
    response_data = await client.get(f"/query/{request.dataset}", params=params)

    result = QueryDataResponse(
        dataset=request.dataset,
        rows=len(response_data.get("data", [])),
        data=response_data.get("data", []),
    )

    logger.info(f"Queried dataset '{request.dataset}': {result.rows} rows returned")
    return result
