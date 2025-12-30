"""Convert Jaeger trace data to ReactFlow graph format."""

from typing import Any, Optional
from .models import (
    FlowGraph, FlowNode, FlowEdge, FlowMeta,
    NodeData, EdgeData
)


def extract_tag_value(tags: list[dict], key: str) -> Optional[Any]:
    """Extract a tag value from a list of Jaeger tags."""
    for tag in tags:
        if tag.get("key") == key:
            return tag.get("value")
    return None


def has_error(span: dict) -> bool:
    """Check if a span has an error tag."""
    tags = span.get("tags", [])
    error_tag = extract_tag_value(tags, "error")
    if error_tag is True:
        return True

    # Check for HTTP 5xx status codes
    http_status = extract_tag_value(tags, "http.status_code")
    if http_status and int(http_status) >= 500:
        return True

    # Check for otel.status_code = ERROR
    otel_status = extract_tag_value(tags, "otel.status_code")
    if otel_status == "ERROR":
        return True

    return False


def get_parent_span_id(span: dict) -> Optional[str]:
    """Get the parent span ID from references."""
    references = span.get("references", [])
    for ref in references:
        if ref.get("refType") == "CHILD_OF":
            return ref.get("spanID")
    return None


def tags_to_dict(tags: list[dict]) -> dict[str, Any]:
    """Convert Jaeger tags list to a dictionary."""
    result = {}
    for tag in tags:
        key = tag.get("key", "")
        value = tag.get("value")
        # Filter out internal OTel tags that aren't useful to display
        if not key.startswith("otel.") and not key.startswith("telemetry."):
            result[key] = value
    return result


def trace_to_reactflow(trace_data: dict) -> FlowGraph:
    """
    Convert Jaeger trace format to ReactFlow nodes and edges.

    Jaeger trace structure:
    {
        "traceID": "abc123...",
        "spans": [
            {
                "traceID": "abc123...",
                "spanID": "span1",
                "operationName": "HTTP GET /api/users",
                "references": [{"refType": "CHILD_OF", "spanID": "parent1"}],
                "startTime": 1234567890123456,  # microseconds
                "duration": 150000,  # microseconds
                "tags": [{"key": "http.status_code", "value": 200}],
                "logs": [],
                "processID": "p1"
            }
        ],
        "processes": {
            "p1": {"serviceName": "my-service", "tags": []}
        }
    }
    """
    trace_id = trace_data.get("traceID", "unknown")
    spans = trace_data.get("spans", [])
    processes = trace_data.get("processes", {})

    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []
    services: set[str] = set()

    # Track min/max times for duration calculation
    min_time = float("inf")
    max_time = 0

    for span in spans:
        span_id = span.get("spanID", "")
        process_id = span.get("processID", "")
        process = processes.get(process_id, {})
        service_name = process.get("serviceName", "unknown")
        services.add(service_name)

        operation_name = span.get("operationName", "unknown")
        start_time = span.get("startTime", 0)  # microseconds
        duration = span.get("duration", 0)  # microseconds
        tags = span.get("tags", [])

        # Update time bounds
        min_time = min(min_time, start_time)
        max_time = max(max_time, start_time + duration)

        # Determine status
        status = "error" if has_error(span) else "success"

        # Create node
        node_data = NodeData(
            spanId=span_id,
            operationName=operation_name,
            serviceName=service_name,
            duration=duration / 1000,  # Convert to milliseconds
            startTime=start_time,
            status=status,
            tags=tags_to_dict(tags)
        )

        node = FlowNode(
            id=f"span:{span_id}",
            type="span",
            position={"x": 0, "y": 0},  # Will be calculated by dagre on frontend
            data=node_data
        )
        nodes.append(node)

        # Create edge from parent
        parent_span_id = get_parent_span_id(span)
        if parent_span_id:
            edge = FlowEdge(
                id=f"edge:{parent_span_id}-{span_id}",
                source=f"span:{parent_span_id}",
                target=f"span:{span_id}",
                data=EdgeData(type="childOf"),
                animated=status == "error"  # Animate error edges
            )
            edges.append(edge)

    # Calculate total duration
    total_duration_ms = (max_time - min_time) / 1000 if spans else 0

    meta = FlowMeta(
        traceId=trace_id,
        totalDurationMs=total_duration_ms,
        spanCount=len(spans),
        serviceCount=len(services)
    )

    return FlowGraph(nodes=nodes, edges=edges, meta=meta)


def find_root_spans(trace_data: dict) -> list[dict]:
    """Find spans that have no parent (root spans)."""
    spans = trace_data.get("spans", [])
    root_spans = []

    for span in spans:
        parent_id = get_parent_span_id(span)
        if parent_id is None:
            root_spans.append(span)

    return root_spans


def find_critical_path(trace_data: dict) -> list[str]:
    """
    Find the critical path through the trace (longest path by duration).
    Returns list of span IDs in order from root to leaf.
    """
    spans = trace_data.get("spans", [])
    if not spans:
        return []

    # Build span lookup and children map
    span_map = {s["spanID"]: s for s in spans}
    children_map: dict[str, list[str]] = {}

    for span in spans:
        span_id = span["spanID"]
        parent_id = get_parent_span_id(span)
        if parent_id:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(span_id)

    def get_path_duration(span_id: str, visited: set) -> tuple[float, list[str]]:
        """Recursively find the longest path from this span."""
        if span_id in visited:
            return 0, []
        visited.add(span_id)

        span = span_map.get(span_id)
        if not span:
            return 0, []

        duration = span.get("duration", 0)
        children = children_map.get(span_id, [])

        if not children:
            return duration, [span_id]

        # Find child with longest path
        max_child_duration = 0
        max_child_path: list[str] = []

        for child_id in children:
            child_duration, child_path = get_path_duration(child_id, visited.copy())
            if child_duration > max_child_duration:
                max_child_duration = child_duration
                max_child_path = child_path

        return duration + max_child_duration, [span_id] + max_child_path

    # Find root spans and get longest path from each
    root_spans = find_root_spans(trace_data)
    longest_path: list[str] = []
    max_duration = 0

    for root in root_spans:
        duration, path = get_path_duration(root["spanID"], set())
        if duration > max_duration:
            max_duration = duration
            longest_path = path

    return longest_path


def find_slowest_spans(trace_data: dict, n: int = 5) -> list[dict]:
    """Find the N slowest spans by duration."""
    spans = trace_data.get("spans", [])
    sorted_spans = sorted(spans, key=lambda s: s.get("duration", 0), reverse=True)
    return sorted_spans[:n]


def find_error_spans(trace_data: dict) -> list[dict]:
    """Find all spans with errors."""
    spans = trace_data.get("spans", [])
    return [s for s in spans if has_error(s)]
