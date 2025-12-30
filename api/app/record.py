"""Record requests to target applications and capture traces."""

import re
import httpx
from typing import Optional
from opentelemetry import trace
from .config import get_settings
from .models import RecordRequest, RecordResponse


def is_path_allowed(path: str) -> bool:
    """Check if a path is in the allowlist for recording."""
    settings = get_settings()
    for pattern in settings.record_allowlist:
        if re.match(pattern, path):
            return True
    return False


async def record_request(
    request: RecordRequest,
    target_base_url: str = "http://127.0.0.1:8000",
    skip_allowlist: bool = False
) -> RecordResponse:
    """
    Execute a request against a target application and capture the trace ID.

    Args:
        request: The request specification
        target_base_url: Base URL of the target application
        skip_allowlist: If True, skip the path allowlist check (used for repo recording)

    Returns:
        RecordResponse with status, trace_id, and response body
    """
    settings = get_settings()

    # Validate path is allowed (skip for repo recordings)
    if not skip_allowlist and not is_path_allowed(request.path):
        return RecordResponse(
            status=403,
            error=f"Path '{request.path}' is not in the allowlist for recording"
        )

    # Build the full URL
    url = f"{target_base_url.rstrip('/')}{request.path}"

    # Prepare headers - include any custom headers from request
    headers = dict(request.headers or {})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if request.method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif request.method.upper() == "POST":
                response = await client.post(
                    url,
                    headers=headers,
                    json=request.body
                )
            elif request.method.upper() == "PUT":
                response = await client.put(
                    url,
                    headers=headers,
                    json=request.body
                )
            elif request.method.upper() == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                return RecordResponse(
                    status=400,
                    error=f"Unsupported HTTP method: {request.method}"
                )

            # Extract trace ID from response headers
            # OpenTelemetry uses 'traceparent' header in W3C format:
            # traceparent: 00-{trace_id}-{span_id}-{flags}
            trace_id = None
            traceparent = response.headers.get("traceparent")
            if traceparent:
                parts = traceparent.split("-")
                if len(parts) >= 2:
                    trace_id = parts[1]

            # Also check for x-trace-id header (custom header we'll add)
            if not trace_id:
                trace_id = response.headers.get("x-trace-id")

            # Try to parse response body
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text

            return RecordResponse(
                status=response.status_code,
                traceId=trace_id,
                responseBody=response_body
            )

    except httpx.ConnectError as e:
        return RecordResponse(
            status=503,
            error=f"Failed to connect to target application: {str(e)}"
        )
    except httpx.TimeoutException:
        return RecordResponse(
            status=504,
            error="Request to target application timed out"
        )
    except Exception as e:
        return RecordResponse(
            status=500,
            error=f"Unexpected error: {str(e)}"
        )


async def record_to_repo(
    request: RecordRequest,
    repo_port: int
) -> RecordResponse:
    """
    Record a request to a running repository container.

    Args:
        request: The request specification
        repo_port: Port where the repo container is listening

    Returns:
        RecordResponse with status, trace_id, and response body
    """
    target_url = f"http://127.0.0.1:{repo_port}"
    return await record_request(request, target_url)
