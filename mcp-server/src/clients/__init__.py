"""Clients module initialization."""
from src.clients.rest_client import (
    close_rest_client,
    get_rest_client,
)

__all__ = [
    "get_rest_client",
    "close_rest_client",
]
