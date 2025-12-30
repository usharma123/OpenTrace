"""Main FastAPI application for OpenTrace API service."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from typing import Optional

from .config import get_settings
from .models import (
    FlowGraph, TraceSummary, TraceSearchParams,
    RecordRequest, RecordResponse, HealthResponse,
    AnalyzeRepoRequest, RepoInfo
)
from .jaeger_client import get_jaeger_client, JaegerClient
from .trace_to_graph import trace_to_reactflow, find_critical_path, find_slowest_spans, find_error_spans
from .static_graph import openapi_to_static_graph
from .record import record_request
from .demo.routes import router as demo_router
from .repo_analyzer import get_repo_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown
    jaeger = get_jaeger_client()
    await jaeger.close()


app = FastAPI(
    title="OpenTrace API",
    description="Live App Flow Investigator - Visualize application traces",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-trace-id", "traceparent"]
)


# Middleware to inject trace ID in response headers
@app.middleware("http")
async def add_trace_id_header(request, call_next):
    response = await call_next(request)

    # Get current trace context
    span = trace.get_current_span()
    if span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            trace_id = format(ctx.trace_id, '032x')
            response.headers["x-trace-id"] = trace_id

    return response


# Include demo routes
app.include_router(demo_router)


# === Health Endpoints ===

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and Jaeger connectivity."""
    jaeger = get_jaeger_client()
    jaeger_connected = await jaeger.health_check()

    return HealthResponse(
        status="healthy",
        service="opentrace-api",
        jaegerConnected=jaeger_connected
    )


# === Flow Endpoints ===

@app.get("/flows/runtime/{trace_id}", response_model=FlowGraph)
async def get_runtime_flow(trace_id: str):
    """
    Get ReactFlow graph for a specific trace.

    Fetches the trace from Jaeger and converts it to ReactFlow format
    with nodes for each span and edges for parent-child relationships.
    """
    jaeger = get_jaeger_client()
    trace_data = await jaeger.get_trace(trace_id)

    if not trace_data:
        raise HTTPException(
            status_code=404,
            detail=f"Trace {trace_id} not found. It may not have been recorded yet or has expired."
        )

    return trace_to_reactflow(trace_data)


@app.get("/flows/static", response_model=FlowGraph)
async def get_static_flow():
    """
    Get static architecture graph from OpenAPI spec.

    Returns a graph showing all API routes grouped by their path prefix.
    """
    return openapi_to_static_graph(app)


# === Trace Endpoints ===

@app.get("/traces/search", response_model=list[TraceSummary])
async def search_traces(
    service: Optional[str] = Query(None, description="Filter by service name"),
    operation: Optional[str] = Query(None, description="Filter by operation name"),
    lookback: str = Query("1h", description="How far back to search (e.g., 1h, 24h)"),
    min_duration_ms: Optional[int] = Query(None, alias="minDurationMs", description="Minimum duration in ms"),
    max_duration_ms: Optional[int] = Query(None, alias="maxDurationMs", description="Maximum duration in ms"),
    limit: int = Query(20, le=100, description="Maximum traces to return")
):
    """
    Search for traces matching the given criteria.

    Returns a list of trace summaries with basic metadata.
    """
    jaeger = get_jaeger_client()

    # Convert ms to microseconds for Jaeger API
    min_duration_us = min_duration_ms * 1000 if min_duration_ms else None
    max_duration_us = max_duration_ms * 1000 if max_duration_ms else None

    traces = await jaeger.search_traces(
        service=service,
        operation=operation,
        lookback=lookback,
        min_duration=min_duration_us,
        max_duration=max_duration_us,
        limit=limit
    )

    summaries = []
    for trace_data in traces:
        spans = trace_data.get("spans", [])
        if not spans:
            continue

        processes = trace_data.get("processes", {})

        # Find root span (usually the first one with no parent)
        root_span = None
        for span in spans:
            refs = span.get("references", [])
            if not any(r.get("refType") == "CHILD_OF" for r in refs):
                root_span = span
                break

        if not root_span:
            root_span = spans[0]

        # Get service name from process
        process_id = root_span.get("processID", "")
        process = processes.get(process_id, {})
        service_name = process.get("serviceName", "unknown")

        # Check for errors
        has_error = any(
            any(t.get("key") == "error" and t.get("value") == True
                for t in s.get("tags", []))
            for s in spans
        )

        # Calculate total duration
        if spans:
            min_start = min(s.get("startTime", 0) for s in spans)
            max_end = max(s.get("startTime", 0) + s.get("duration", 0) for s in spans)
            duration_ms = (max_end - min_start) / 1000
        else:
            duration_ms = 0

        summaries.append(TraceSummary(
            traceId=trace_data.get("traceID", ""),
            serviceName=service_name,
            operationName=root_span.get("operationName", "unknown"),
            durationMs=duration_ms,
            spanCount=len(spans),
            timestamp=root_span.get("startTime", 0),
            hasError=has_error
        ))

    return summaries


@app.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """
    Get raw trace data from Jaeger.

    Returns the full trace with all spans and metadata.
    """
    jaeger = get_jaeger_client()
    trace_data = await jaeger.get_trace(trace_id)

    if not trace_data:
        raise HTTPException(
            status_code=404,
            detail=f"Trace {trace_id} not found"
        )

    return trace_data


@app.get("/traces/{trace_id}/analysis")
async def analyze_trace(trace_id: str):
    """
    Get analysis of a trace including critical path and bottlenecks.
    """
    jaeger = get_jaeger_client()
    trace_data = await jaeger.get_trace(trace_id)

    if not trace_data:
        raise HTTPException(
            status_code=404,
            detail=f"Trace {trace_id} not found"
        )

    critical_path = find_critical_path(trace_data)
    slowest = find_slowest_spans(trace_data, n=5)
    errors = find_error_spans(trace_data)

    return {
        "traceId": trace_id,
        "criticalPath": [f"span:{sid}" for sid in critical_path],
        "slowestSpans": [
            {
                "spanId": s.get("spanID"),
                "operationName": s.get("operationName"),
                "durationMs": s.get("duration", 0) / 1000
            }
            for s in slowest
        ],
        "errorSpans": [
            {
                "spanId": s.get("spanID"),
                "operationName": s.get("operationName")
            }
            for s in errors
        ]
    }


# === Services Endpoints ===

@app.get("/services")
async def list_services():
    """List all services that have reported traces."""
    jaeger = get_jaeger_client()
    services = await jaeger.get_services()
    return {"services": services}


@app.get("/services/{service}/operations")
async def list_operations(service: str):
    """List all operations for a specific service."""
    jaeger = get_jaeger_client()
    operations = await jaeger.get_operations(service)
    return {"service": service, "operations": operations}


# === Record Endpoints ===

@app.post("/record", response_model=RecordResponse)
async def record_trace(request: RecordRequest):
    """
    Record a new trace by making a request to the target application.

    Only paths matching the allowlist patterns are permitted (unless targeting a repo).
    """
    # If recording to a repo container, use that port and skip allowlist
    if request.repo_id:
        repo_manager = get_repo_manager()
        repo = repo_manager.get_repo(request.repo_id)
        if not repo:
            raise HTTPException(
                status_code=404,
                detail=f"Repository {request.repo_id} not found"
            )
        if repo.status != "running":
            raise HTTPException(
                status_code=400,
                detail=f"Repository {request.repo_id} is not running (status: {repo.status})"
            )
        
        # Try container name first (if on same Docker network), then fallback
        from .models import RepoLanguage
        container_name = f"opentrace-{repo.repo_id}"
        internal_port = 8000 if repo.language == RepoLanguage.PYTHON else 3000
        
        # Try container name first
        target_url = f"http://{container_name}:{internal_port}"
        result = await record_request(request, target_url, skip_allowlist=True)
        
        # If connection failed, try host.docker.internal
        if result.error and "Failed to connect" in result.error:
            target_url = f"http://host.docker.internal:{repo.port}"
            result = await record_request(request, target_url, skip_allowlist=True)
        
        return result
    else:
        # Record to self (this API)
        target_url = "http://127.0.0.1:8000"
        return await record_request(request, target_url)


# === Repo Analysis Endpoints ===

@app.post("/repos/analyze", response_model=RepoInfo)
async def analyze_repo(request: AnalyzeRepoRequest):
    """
    Start analyzing a GitHub repository.

    Clones the repo, detects language and framework, finds entry point.
    """
    from .repo_analyzer import get_repo_manager

    repo_manager = get_repo_manager()
    repo_info = await repo_manager.analyze(request.github_url, request.branch)
    return repo_info


@app.get("/repos/{repo_id}", response_model=RepoInfo)
async def get_repo_status(repo_id: str):
    """Get the current status of a repository analysis/run."""
    from .repo_analyzer import get_repo_manager

    repo_manager = get_repo_manager()
    repo = repo_manager.get_repo(repo_id)

    if not repo:
        raise HTTPException(
            status_code=404,
            detail=f"Repository {repo_id} not found"
        )

    return repo


@app.post("/repos/{repo_id}/start", response_model=RepoInfo)
async def start_repo(repo_id: str):
    """Build and start the repository container."""
    from .repo_analyzer import get_repo_manager

    repo_manager = get_repo_manager()
    repo = await repo_manager.start(repo_id)

    if not repo:
        raise HTTPException(
            status_code=404,
            detail=f"Repository {repo_id} not found"
        )

    return repo


@app.post("/repos/{repo_id}/stop", response_model=RepoInfo)
async def stop_repo(repo_id: str):
    """Stop the running repository container."""
    from .repo_analyzer import get_repo_manager

    repo_manager = get_repo_manager()
    repo = await repo_manager.stop(repo_id)

    if not repo:
        raise HTTPException(
            status_code=404,
            detail=f"Repository {repo_id} not found"
        )

    return repo


@app.get("/repos")
async def list_repos():
    """List all analyzed repositories."""
    from .repo_analyzer import get_repo_manager

    repo_manager = get_repo_manager()
    repos = repo_manager.list_repos()
    return {"repos": repos}
