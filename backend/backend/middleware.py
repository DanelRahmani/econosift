"""Custom ASGI middleware for EconoSift."""
from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class DeduplicationMiddleware(BaseHTTPMiddleware):
    """
    Stub for request deduplication — passes all requests through unchanged.

    A full implementation that collapses identical in-flight GET requests into
    a single backend call is architecturally complex with streaming ASGI
    responses (the response body can only be consumed once). This stub keeps
    the middleware slot in the stack so the deduplication logic can be wired
    in transparently later without touching main.py or any router.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        return await call_next(request)
