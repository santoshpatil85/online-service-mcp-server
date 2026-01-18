"""Async REST client for downstream service calls."""
import logging
from typing import Any, Optional

import httpx

from src.auth import get_access_token
from src.config import settings
from src.models.errors import ServiceError, TimeoutError

logger = logging.getLogger(__name__)


class RESTClient:
    """Async REST client with Azure AD authentication."""

    def __init__(self) -> None:
        """Initialize REST client."""
        self._client: Optional[httpx.AsyncClient] = None
        self._base_url = settings.server.backend_api_url
        self._timeout = settings.server.backend_api_timeout

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": "mcp-server/1.0"},
            )
        return self._client

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authorization headers with Azure AD token."""
        try:
            token = await get_access_token()
            return {"Authorization": f"Bearer {token}"}
        except Exception as e:
            logger.error(f"Failed to get authorization token: {e}")
            raise ServiceError(f"Authentication failed: {e}") from e

    async def get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make a GET request.
        
        Args:
            path: API path (relative to base URL).
            params: Query parameters.
            
        Returns:
            Response JSON as dictionary.
            
        Raises:
            ServiceError: If request fails.
        """
        try:
            client = await self._get_client()
            auth_headers = await self._get_auth_headers()
            url = f"{self._base_url}{path}"

            logger.debug(f"GET {url}")
            response = await client.get(url, params=params, headers=auth_headers)
            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise TimeoutError(f"Request to {path} timed out") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e}")
            raise ServiceError(
                f"Service error: {e.response.status_code}",
                {
                    "status_code": e.response.status_code,
                    "path": path,
                },
            ) from e
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise ServiceError(f"Request failed: {e}") from e

    async def post(
        self,
        path: str,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make a POST request.
        
        Args:
            path: API path.
            data: Request body data.
            
        Returns:
            Response JSON as dictionary.
            
        Raises:
            ServiceError: If request fails.
        """
        try:
            client = await self._get_client()
            auth_headers = await self._get_auth_headers()
            url = f"{self._base_url}{path}"

            logger.debug(f"POST {url}")
            response = await client.post(url, json=data, headers=auth_headers)
            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise TimeoutError(f"Request to {path} timed out") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e}")
            raise ServiceError(
                f"Service error: {e.response.status_code}",
                {
                    "status_code": e.response.status_code,
                    "path": path,
                },
            ) from e
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise ServiceError(f"Request failed: {e}") from e

    async def health_check(self) -> bool:
        """
        Check if backend service is healthy.
        
        Returns:
            True if service is healthy.
        """
        try:
            response = await self.get("/health")
            return response.get("status") == "healthy"
        except Exception as e:
            logger.warning(f"Backend health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Global REST client instance
_rest_client: Optional[RESTClient] = None


def get_rest_client() -> RESTClient:
    """Get or create the global REST client."""
    global _rest_client
    if _rest_client is None:
        _rest_client = RESTClient()
    return _rest_client


async def close_rest_client() -> None:
    """Close the global REST client."""
    global _rest_client
    if _rest_client is not None:
        await _rest_client.close()
        _rest_client = None
