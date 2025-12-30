"""Main FastAPI application for OpenTrace Agent service."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

from .config import get_settings
from .models import ChatRequest, AgentResponse
from .planner import get_agent_planner


app = FastAPI(
    title="OpenTrace Agent",
    description="AI-powered trace analysis agent",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Check agent service health."""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "opentrace-agent",
        "llm_available": bool(settings.openrouter_api_key),
        "llm_model": settings.openrouter_model if settings.openrouter_api_key else "fallback"
    }


@app.post("/chat", response_model=AgentResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message and return agent response with analysis.

    The agent can:
    - Analyze traces for bottlenecks and errors
    - Explain what happened in a trace
    - Highlight relevant spans in the UI
    - Request actions (like recording new traces) with approval
    """
    planner = get_agent_planner()
    return await planner.process_message(request)


@app.post("/execute-action")
async def execute_action(action: dict):
    """
    Execute an approved action.

    This endpoint is called after the user approves an action request.
    """
    settings = get_settings()
    action_type = action.get("actionType")
    params = action.get("params", {})

    if action_type == "record":
        # Execute the record request
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.api_url}/record",
                    json=params
                )
                return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to execute action: {str(e)}"
            )

    raise HTTPException(
        status_code=400,
        detail=f"Unknown action type: {action_type}"
    )
