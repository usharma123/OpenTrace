"""Fallback analyzer for when no LLM is available."""

import re
from typing import Optional
from .models import AgentResponse, Evidence, UIHints, ActionRequest


def analyze_query(query: str) -> dict:
    """
    Analyze the user's query to understand intent.

    Returns dict with:
    - intent: 'slow', 'error', 'explain', 'record', 'list', 'unknown'
    - parameters: any extracted parameters
    """
    query_lower = query.lower()

    # Check for recording intent
    if any(word in query_lower for word in ["record", "capture", "create trace", "make request"]):
        # Try to extract path
        path_match = re.search(r'/\w+(?:/\w+)*', query)
        path = path_match.group(0) if path_match else "/demo/slow"
        return {"intent": "record", "parameters": {"path": path}}

    # Check for slowness analysis
    if any(word in query_lower for word in ["slow", "bottleneck", "performance", "latency", "duration"]):
        return {"intent": "slow", "parameters": {}}

    # Check for error analysis
    if any(word in query_lower for word in ["error", "fail", "exception", "500", "bug"]):
        return {"intent": "error", "parameters": {}}

    # Check for listing traces
    if any(word in query_lower for word in ["list", "show", "recent", "traces", "what traces"]):
        return {"intent": "list", "parameters": {}}

    # Check for explanation
    if any(word in query_lower for word in ["explain", "what", "how", "why", "describe", "summary"]):
        return {"intent": "explain", "parameters": {}}

    return {"intent": "unknown", "parameters": {}}


def analyze_trace_for_slowness(trace_data: dict) -> AgentResponse:
    """Analyze a trace for slow spans."""
    spans = trace_data.get("spans", [])

    if not spans:
        return AgentResponse(
            answer="No spans found in this trace.",
            evidence=Evidence(traceId=trace_data.get("traceID")),
            ui=UIHints()
        )

    # Sort spans by duration
    sorted_spans = sorted(spans, key=lambda s: s.get("duration", 0), reverse=True)
    top_slow = sorted_spans[:5]

    # Calculate total trace duration
    if spans:
        min_start = min(s.get("startTime", 0) for s in spans)
        max_end = max(s.get("startTime", 0) + s.get("duration", 0) for s in spans)
        total_duration_ms = (max_end - min_start) / 1000
    else:
        total_duration_ms = 0

    # Build answer
    answer = f"**Trace Analysis: Slowest Operations**\n\n"
    answer += f"Total trace duration: {total_duration_ms:.1f}ms with {len(spans)} spans.\n\n"
    answer += "**Top 5 slowest operations:**\n"

    highlight_nodes = []
    for i, span in enumerate(top_slow, 1):
        duration_ms = span.get("duration", 0) / 1000
        op_name = span.get("operationName", "unknown")
        span_id = span.get("spanID", "")

        # Calculate percentage of total
        pct = (duration_ms / total_duration_ms * 100) if total_duration_ms > 0 else 0

        answer += f"{i}. **{op_name}**: {duration_ms:.1f}ms ({pct:.1f}% of total)\n"
        highlight_nodes.append(f"span:{span_id}")

    answer += "\n*Highlighted spans are shown in the graph.*"

    return AgentResponse(
        answer=answer,
        evidence=Evidence(
            traceId=trace_data.get("traceID"),
            spanIds=[s.get("spanID") for s in top_slow]
        ),
        ui=UIHints(highlightNodes=highlight_nodes)
    )


def analyze_trace_for_errors(trace_data: dict) -> AgentResponse:
    """Analyze a trace for error spans."""
    spans = trace_data.get("spans", [])

    # Find error spans
    error_spans = []
    for span in spans:
        tags = span.get("tags", [])
        has_error = False

        for tag in tags:
            key = tag.get("key", "")
            value = tag.get("value")

            if key == "error" and value is True:
                has_error = True
            elif key == "http.status_code" and isinstance(value, int) and value >= 500:
                has_error = True
            elif key == "otel.status_code" and value == "ERROR":
                has_error = True

        if has_error:
            error_spans.append(span)

    if not error_spans:
        return AgentResponse(
            answer="**No errors found in this trace.**\n\nAll spans completed successfully without error tags or HTTP 5xx status codes.",
            evidence=Evidence(traceId=trace_data.get("traceID")),
            ui=UIHints()
        )

    # Build answer
    answer = f"**Trace Analysis: Errors Found**\n\n"
    answer += f"Found {len(error_spans)} error(s) in this trace:\n\n"

    highlight_nodes = []
    for i, span in enumerate(error_spans, 1):
        op_name = span.get("operationName", "unknown")
        span_id = span.get("spanID", "")

        # Get error details from tags
        tags = {t.get("key"): t.get("value") for t in span.get("tags", [])}
        status_code = tags.get("http.status_code", "N/A")
        error_msg = tags.get("error.message", tags.get("exception.message", ""))

        answer += f"{i}. **{op_name}**\n"
        answer += f"   - Status code: {status_code}\n"
        if error_msg:
            answer += f"   - Message: {error_msg[:100]}\n"
        answer += "\n"

        highlight_nodes.append(f"span:{span_id}")

    answer += "*Error spans are highlighted in red in the graph.*"

    return AgentResponse(
        answer=answer,
        evidence=Evidence(
            traceId=trace_data.get("traceID"),
            spanIds=[s.get("spanID") for s in error_spans]
        ),
        ui=UIHints(highlightNodes=highlight_nodes)
    )


def explain_trace(trace_data: dict) -> AgentResponse:
    """Provide a general explanation of a trace."""
    spans = trace_data.get("spans", [])
    processes = trace_data.get("processes", {})

    if not spans:
        return AgentResponse(
            answer="No spans found in this trace.",
            evidence=Evidence(traceId=trace_data.get("traceID")),
            ui=UIHints()
        )

    # Gather statistics
    services = set()
    operations = []
    total_duration_ms = 0

    for span in spans:
        process_id = span.get("processID", "")
        process = processes.get(process_id, {})
        services.add(process.get("serviceName", "unknown"))
        operations.append(span.get("operationName", "unknown"))

    if spans:
        min_start = min(s.get("startTime", 0) for s in spans)
        max_end = max(s.get("startTime", 0) + s.get("duration", 0) for s in spans)
        total_duration_ms = (max_end - min_start) / 1000

    # Find root span
    root_span = None
    for span in spans:
        refs = span.get("references", [])
        if not any(r.get("refType") == "CHILD_OF" for r in refs):
            root_span = span
            break

    # Build answer
    answer = f"**Trace Summary**\n\n"
    answer += f"- **Trace ID**: `{trace_data.get('traceID', 'unknown')}`\n"
    answer += f"- **Total duration**: {total_duration_ms:.1f}ms\n"
    answer += f"- **Spans**: {len(spans)}\n"
    answer += f"- **Services**: {', '.join(services)}\n\n"

    if root_span:
        answer += f"**Entry point**: {root_span.get('operationName', 'unknown')}\n\n"

    answer += "**Operations in this trace:**\n"
    for op in operations[:10]:
        answer += f"- {op}\n"

    if len(operations) > 10:
        answer += f"- ... and {len(operations) - 10} more\n"

    # Highlight root span
    highlight_nodes = []
    if root_span:
        highlight_nodes.append(f"span:{root_span.get('spanID')}")

    return AgentResponse(
        answer=answer,
        evidence=Evidence(traceId=trace_data.get("traceID")),
        ui=UIHints(highlightNodes=highlight_nodes)
    )


def generate_record_action(path: str) -> AgentResponse:
    """Generate a record action request."""
    return AgentResponse(
        answer=f"I can record a trace by making a request to `{path}`. This action requires your approval.\n\nClick 'Approve' below to proceed.",
        evidence=Evidence(),
        ui=UIHints(),
        actions=[
            ActionRequest(
                actionType="record",
                description=f"Record GET request to {path}",
                params={"method": "GET", "path": path},
                requiresApproval=True
            )
        ]
    )


def no_trace_response() -> AgentResponse:
    """Response when no trace is selected."""
    return AgentResponse(
        answer="**No trace selected.**\n\nPlease select a trace from the list on the left, or click 'Record' to create a new one.\n\nI can help you:\n- Analyze slow spans and bottlenecks\n- Find errors in traces\n- Explain what happened in a request flow",
        evidence=Evidence(),
        ui=UIHints()
    )


def unknown_intent_response() -> AgentResponse:
    """Response for unknown queries."""
    return AgentResponse(
        answer="I'm not sure what you're asking. Here are some things I can help with:\n\n"
               "- **\"What's slow?\"** - Find bottlenecks in the selected trace\n"
               "- **\"Any errors?\"** - Find error spans\n"
               "- **\"Explain this trace\"** - Get a summary of what happened\n"
               "- **\"Record /demo/slow\"** - Create a new trace\n"
               "- **\"List traces\"** - Show recent traces",
        evidence=Evidence(),
        ui=UIHints()
    )
