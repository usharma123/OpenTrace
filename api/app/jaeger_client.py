"""Client for interacting with Jaeger Query API."""

import httpx
from typing import Optional
from .config import get_settings


class JaegerClient:
    """Client for Jaeger Query API."""

    def __init__(self, base_url: Optional[str] = None):
        settings = get_settings()
        self.base_url = base_url or settings.jaeger_query_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> bool:
        """Check if Jaeger is accessible."""
        try:
            client = await self._get_client()
            response = await client.get("/")
            return response.status_code == 200
        except Exception:
            return False

    async def get_services(self) -> list[str]:
        """Get list of all services that have reported traces."""
        client = await self._get_client()
        response = await client.get("/api/services")
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

    async def get_operations(self, service: str) -> list[str]:
        """Get list of operations for a service."""
        client = await self._get_client()
        response = await client.get(f"/api/services/{service}/operations")
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

    async def search_traces(
        self,
        service: Optional[str] = None,
        operation: Optional[str] = None,
        tags: Optional[dict[str, str]] = None,
        lookback: str = "1h",
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        limit: int = 20
    ) -> list[dict]:
        """
        Search for traces matching the given criteria.

        Args:
            service: Filter by service name
            operation: Filter by operation name
            tags: Filter by span tags (key=value format)
            lookback: How far back to search (e.g., "1h", "24h")
            min_duration: Minimum trace duration in microseconds
            max_duration: Maximum trace duration in microseconds
            limit: Maximum number of traces to return

        Returns:
            List of trace data dictionaries
        """
        client = await self._get_client()

        params = {"limit": limit, "lookback": lookback}

        if service:
            params["service"] = service
        if operation:
            params["operation"] = operation
        if min_duration:
            params["minDuration"] = f"{min_duration}us"
        if max_duration:
            params["maxDuration"] = f"{max_duration}us"
        if tags:
            # Jaeger expects tags as repeated query params or JSON
            params["tags"] = str(tags)

        response = await client.get("/api/traces", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

    async def get_trace(self, trace_id: str) -> Optional[dict]:
        """
        Get a specific trace by ID.

        Args:
            trace_id: The trace ID (32 hex characters)

        Returns:
            Trace data dictionary or None if not found
        """
        client = await self._get_client()

        try:
            response = await client.get(f"/api/traces/{trace_id}")
            response.raise_for_status()
            data = response.json()
            traces = data.get("data", [])
            return traces[0] if traces else None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_trace_raw(self, trace_id: str) -> Optional[dict]:
        """Get raw trace data as returned by Jaeger."""
        return await self.get_trace(trace_id)


# Global client instance
_jaeger_client: Optional[JaegerClient] = None


def get_jaeger_client() -> JaegerClient:
    """Get the global Jaeger client instance."""
    global _jaeger_client
    if _jaeger_client is None:
        _jaeger_client = JaegerClient()
    return _jaeger_client
