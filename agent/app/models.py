"""Pydantic models for Agent service."""

from pydantic import BaseModel, Field
from typing import Optional, Any


class ChatRequest(BaseModel):
    """Request to chat with the agent."""
    message: str
    selected_trace_id: Optional[str] = Field(None, alias="selectedTraceId")
    selected_flow_id: Optional[str] = Field(None, alias="selectedFlowId")
    ui_state: Optional[dict[str, Any]] = Field(None, alias="uiState")

    class Config:
        populate_by_name = True


class Evidence(BaseModel):
    """Evidence supporting an agent response."""
    trace_id: Optional[str] = Field(None, alias="traceId")
    span_ids: list[str] = Field(default_factory=list, alias="spanIds")

    class Config:
        populate_by_name = True


class UIHints(BaseModel):
    """UI hints for highlighting and filtering."""
    highlight_nodes: list[str] = Field(default_factory=list, alias="highlightNodes")
    highlight_edges: list[str] = Field(default_factory=list, alias="highlightEdges")
    suggested_filters: list[str] = Field(default_factory=list, alias="suggestedFilters")

    class Config:
        populate_by_name = True


class ActionRequest(BaseModel):
    """Request for an action that requires approval."""
    action_type: str = Field(..., alias="actionType")
    description: str
    params: dict[str, Any]
    requires_approval: bool = Field(True, alias="requiresApproval")

    class Config:
        populate_by_name = True


class AgentResponse(BaseModel):
    """Response from the agent."""
    answer: str
    evidence: Evidence = Field(default_factory=Evidence)
    ui: UIHints = Field(default_factory=UIHints)
    actions: list[ActionRequest] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class ToolCall(BaseModel):
    """A tool call made by the agent."""
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result from executing a tool."""
    name: str
    result: Any
    error: Optional[str] = None
