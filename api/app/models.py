"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


# === Flow/Graph Models ===

class NodeData(BaseModel):
    """Data attached to a ReactFlow node."""
    span_id: str = Field(..., alias="spanId")
    operation_name: str = Field(..., alias="operationName")
    service_name: str = Field(..., alias="serviceName")
    duration_ms: float = Field(..., alias="duration")
    start_time: int = Field(..., alias="startTime")
    status: str = "success"
    tags: dict[str, Any] = {}

    class Config:
        populate_by_name = True


class FlowNode(BaseModel):
    """A node in the ReactFlow graph."""
    id: str
    type: str = "span"
    position: dict[str, float] = {"x": 0, "y": 0}
    data: NodeData


class EdgeData(BaseModel):
    """Data attached to a ReactFlow edge."""
    type: str = "childOf"
    latency_ms: Optional[float] = Field(None, alias="latencyMs")

    class Config:
        populate_by_name = True


class FlowEdge(BaseModel):
    """An edge in the ReactFlow graph."""
    id: str
    source: str
    target: str
    data: EdgeData = EdgeData(type="childOf")
    animated: bool = False


class FlowMeta(BaseModel):
    """Metadata about the flow graph."""
    trace_id: Optional[str] = Field(None, alias="traceId")
    total_duration_ms: Optional[float] = Field(None, alias="totalDurationMs")
    span_count: int = Field(0, alias="spanCount")
    service_count: int = Field(0, alias="serviceCount")
    version: Optional[str] = None

    class Config:
        populate_by_name = True


class FlowGraph(BaseModel):
    """Complete ReactFlow graph with nodes, edges, and metadata."""
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    meta: FlowMeta


# === Trace Models ===

class TraceSearchParams(BaseModel):
    """Parameters for searching traces."""
    service: Optional[str] = None
    operation: Optional[str] = None
    tags: Optional[dict[str, str]] = None
    lookback: str = "1h"
    min_duration_ms: Optional[int] = Field(None, alias="minDurationMs")
    max_duration_ms: Optional[int] = Field(None, alias="maxDurationMs")
    limit: int = 20

    class Config:
        populate_by_name = True


class TraceSummary(BaseModel):
    """Summary of a trace for listing."""
    trace_id: str = Field(..., alias="traceId")
    service_name: str = Field(..., alias="serviceName")
    operation_name: str = Field(..., alias="operationName")
    duration_ms: float = Field(..., alias="durationMs")
    span_count: int = Field(..., alias="spanCount")
    timestamp: int
    has_error: bool = Field(False, alias="hasError")

    class Config:
        populate_by_name = True


# === Record Models ===

class RecordRequest(BaseModel):
    """Request to record a new trace."""
    method: str = "GET"
    path: str
    body: Optional[dict[str, Any]] = None
    headers: Optional[dict[str, str]] = None
    repo_id: Optional[str] = Field(None, alias="repoId")

    class Config:
        populate_by_name = True


class RecordResponse(BaseModel):
    """Response from recording a trace."""
    status: int
    trace_id: Optional[str] = Field(None, alias="traceId")
    response_body: Optional[Any] = Field(None, alias="responseBody")
    error: Optional[str] = None

    class Config:
        populate_by_name = True


# === Repo Analysis Models ===

class RepoLanguage(str, Enum):
    """Detected programming language of a repository."""
    PYTHON = "python"
    NODEJS = "nodejs"
    UNKNOWN = "unknown"


class RepoFramework(str, Enum):
    """Detected web framework."""
    FASTAPI = "fastapi"
    FLASK = "flask"
    DJANGO = "django"
    EXPRESS = "express"
    FASTIFY = "fastify"
    NESTJS = "nestjs"
    UNKNOWN = "unknown"


class RepoStatus(str, Enum):
    """Status of a repository analysis/run."""
    ANALYZING = "analyzing"
    READY = "ready"
    BUILDING = "building"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class AnalyzeRepoRequest(BaseModel):
    """Request to analyze a GitHub repository."""
    github_url: str = Field(..., alias="githubUrl")
    branch: Optional[str] = None

    class Config:
        populate_by_name = True


class RepoInfo(BaseModel):
    """Information about an analyzed repository."""
    repo_id: str = Field(..., alias="repoId")
    github_url: str = Field(..., alias="githubUrl")
    status: RepoStatus
    language: Optional[RepoLanguage] = None
    framework: Optional[RepoFramework] = None
    entrypoint: Optional[str] = None
    port: int = 8000
    endpoints: list[str] = []
    container_id: Optional[str] = Field(None, alias="containerId")
    error_message: Optional[str] = Field(None, alias="errorMessage")

    class Config:
        populate_by_name = True


# === Health Models ===

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    service: str = "opentrace-api"
    jaeger_connected: bool = Field(False, alias="jaegerConnected")

    class Config:
        populate_by_name = True
